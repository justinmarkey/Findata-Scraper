import pandas as pd
import time
import json
import yfinance

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from src.utils.jsonencoder import CustomEncoder

#threading lock object for the json file
json_lock = Lock()

t1 = time.time()

CALENDAR_JSONPATH = "data/json/calendar.json"
INFO_JSONPATH = "data/json/info.json"
EARNINGS_JSONPATH = "data/json/earningsdata.json"

info_dict = {}
calendars_dict = {}
earnings_dict = {}

def read_json_file(file_path: str) -> dict:
    
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
        
    except FileNotFoundError:
        data = {}
    
    except json.JSONDecodeError as e:
        print (f"JSON Decoding Error:{e}\nRebuilding json db...")
        data = {}
        
    return data

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
        # Initialize ticker if it does not exist
        current_data.setdefault(ticker, {})

        for date, values in new_earnings.items():
            # Initialize date if it does not exist, then update values
            current_data[ticker].setdefault(date, {}).update(values)

    write_json_file(file_path=db_path, data=current_data)


def download_earnings (symbol):
    """
    downloads the stockdata by using the yfinance library and places the data
    into JSON files
    """
    
    stock = yfinance.Ticker(symbol)
    
    #confirm USD-denominated earnings data
    if stock.info.get('financialCurrency') != 'USD':
        print(f"{symbol} is a non USD-denominated security\n")
        return
    
    #swap the datetime and the financial reference so dates are the rows
    financials = stock.financials.transpose()
    cashflow = stock.cashflow.transpose()
    sheet = stock.balancesheet.transpose()

    #concatenate along the columns
    aggregated_df = pd.concat([financials, cashflow, sheet], axis=1)
    
    #change dtype from "object" to "float64"
    aggregated_df = aggregated_df.astype({col: 'float64' for col in aggregated_df.select_dtypes(include=['object']).columns})
    
    #using threading.Lock() to prevent data races
    with json_lock:
        calendars_dict[symbol] = stock.calendar
        info_dict[symbol] = stock.info
        earnings_dict[symbol] = aggregated_df
        
    print(f"{symbol}\n")
    #sleep the thread to avoid API block
    time.sleep(0.42)
    
    return
    

def download_controller (method = download_earnings, symbol_list = None):
    """
    Master script for controlling downloads
    """
    if not symbol_list:
        financials_df = pd.read_csv("data/csv/stockdata.csv")
        symbol_list = financials_df["Symbol"].to_list()
    
    list_len = len(symbol_list)
    
    print(f"Downloading started for {list_len}\n")
    
    with ThreadPoolExecutor(max_workers=8) as tpe:
        tpe.map(method, symbol_list[0])
        
    t2 = time.time()
    print(f"Download Fin Statement Data took {t2-t1} seconds")

    update_json_info(db_path=INFO_JSONPATH, new_data=info_dict)
    update_json_calendars(db_path=CALENDAR_JSONPATH, new_data=calendars_dict)
    update_json_earnings(db_path=EARNINGS_JSONPATH, new_data=earnings_dict)
    
    
download_controller()
