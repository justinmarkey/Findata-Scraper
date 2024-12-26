import pandas as pd
import time
import json
import yfinance
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import requests_cache
from src.utils.jsonencoder import CustomEncoder

t1 = time.time()
#threading lock object for the json file
dict_lock = Lock()
cache_lock = Lock()

CALENDAR_JSONPATH = "data/json/calendar.json"
INFO_JSONPATH = "data/json/info.json"
EARNINGS_JSONPATH = "data/json/earningsdata.json"

info_dict = {}
calendars_dict = {}
earnings_dict = {}

session = requests_cache.install_cache('yfinance_cache', expire_after=10800)  # Cache expires after 3 hours


#use this to store the tickers to retry if theres a 429 API block
retry_ticker_set = set()


def read_json_file(file_path: str) -> dict:
    
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
            return data
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
       print(f"OK Rebuilding dict because {e}")  # Optional logging for debugging
       return {}
   

def write_json_file(file_path: str, data: dict) -> None:
    
    with open(file_path, "w") as file:
        #CustomEncoder is used change Datetime "Date" objs into compatible JSON strings
        json.dump(data, file, indent=4, cls=CustomEncoder)    

def update_json_info(db_path: str, new_data: dict) -> None:
    
    info = read_json_file(db_path)
    
    for ticker, value in new_data.items():
        info.setdefault(ticker, {})
        info[ticker].update(value)
        
    write_json_file(file_path=INFO_JSONPATH, data=info)
    
def update_json_calendars(db_path: str, new_data: dict) -> None:
    
    calendars = read_json_file(db_path)
    
    for ticker, value in new_data.items():
        calendars.setdefault(ticker, {})
        calendars[ticker].update(value)

    write_json_file(file_path=CALENDAR_JSONPATH, data=calendars)


def update_json_earnings(db_path: str, new_data: dict) -> None:
    """
    Updates the JSON earnings data file with new earnings data.
    
    Args:
        db_path (str): Path to the JSON file storing current earnings data.
        new_data (dict): New earnings data to merge, with the format:
            {ticker: {date: {values}}}
    """

    current_data = read_json_file(db_path)
    
    for ticker, new_earnings in new_data.items():
        
        if ticker not in current_data:
            # Add the new ticker symbol
            current_data[ticker] = new_earnings
            
        else:
            for date, values in new_earnings.items():
                if date in current_data[ticker]:
                    # update earnings data for the date key
                    current_data[ticker][date].update(values)
                    
                else:
                    # Add the new date key
                    current_data[ticker][date] = values

    write_json_file(file_path=db_path, data=current_data)

def download_earnings (symbol:str) -> None:
    """
    downloads the stockdata by using the yfinance library and places the data
    into JSON files
    """
    
    stock = yfinance.Ticker(symbol, session=session)
    
    #confirm USD-denominated earnings data
    with cache_lock:
        try:    
            info = stock.get_info()
    
            if info.get('financialCurrency') != 'USD':
                print(f"{symbol} is a non USD-denominated security\n")
                return
    
            calendar = stock.get_calendar()
            financials = stock.get_income_stmt(as_dict=False,freq="quarterly")
            cashflow = stock.get_cash_flow(as_dict=False,freq="quarterly")
            sheet = stock.get_balance_sheet(as_dict=False,freq="quarterly")
        except Exception:
            retry_ticker_set.add(symbol)
        
    #concatenate Findata along the rows
    #convert the pandas Datetime type columns to a string types to allowing for JSON encode
    
    aggregated_df = pd.concat([financials, cashflow, sheet], axis=0)
    aggregated_df.columns = aggregated_df.columns.strftime('%Y-%m-%d')
    
    #prep the data to be stored in JSON. Store in a dict temporarily and write to JSON once.
    #using threading.Lock() to prevent data races
        
    aggregated_df = aggregated_df.to_dict(orient="index")
    
    with dict_lock:

        calendars_dict[symbol] = calendar
        info_dict[symbol] = info
        earnings_dict[symbol] = aggregated_df
        
    t2 = time.time()  
    print(f"{symbol}\n -> {t2-t1} seconds")
    
    #sleep the thread to avoid API limit
    time.sleep(10)
    
    return


def download_controller (method: object = download_earnings, symbol_list: list = None) -> None:
    """
    Master script for controlling downloads.
    
    Attempts to download all tickers in the symbol_list. If theres an API block (see download_earnings,
    it will store the symbol in a global list (protected by a Lock() object for thread access protection).
    
    after looping the original list, it will retry looping through the blocked list (download_earnings has a
    try/except block to always add the ticker if the API blocks). The retry logic will recursively call the 
    retry_list and empty it until all tickers in the original fetching were successfully returned.
    """
    
    #if no symbols are provided in arg, the default will be to download the entire list noted below.
    if not symbol_list:
        financials_df = pd.read_csv("data/csv/stockdata.csv")
        symbol_list = financials_df["Symbol"].to_list()
    
    list_len = len(symbol_list)
    print(f"Downloading started for {list_len}\n")
    print(f"Estimated Minutes: {list_len//8*10//60}")
    
    #create the thread mapping to the download_earnings function
    with ThreadPoolExecutor(max_workers=8) as tpe:
        tpe.map(method, symbol_list)
    
    #write the dictionary's to the JSON files
    update_json_info(db_path=INFO_JSONPATH, new_data=info_dict)
    update_json_calendars(db_path=CALENDAR_JSONPATH, new_data=calendars_dict)
    update_json_earnings(db_path=EARNINGS_JSONPATH, new_data=earnings_dict)
    
    #retry logic -> Recursively call until all symbols are fetched from the API. Uses the retry global list. 
    #Need to temporarily store the retry list so that you can reset the global list to empty.
    global retry_ticker_set
    if len(retry_ticker_set) != 0:
        
        print(f"Retrying API requests for {retry_ticker_set}\nwaiting 5 minutes")
        temp = retry_ticker_set
        retry_ticker_set = set()
        time.sleep(300)
        download_controller (method= download_earnings, symbol_list=temp)
               
download_controller()
