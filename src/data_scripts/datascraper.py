import pandas as pd
import time
import json
import yfinance
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import requests_cache

from src.utils.jsonhelper import *
from src.utils.jsonencoder import CustomEncoder

from src.utils.datapaths import INFO_JSONPATH, CALENDAR_JSONPATH, EARNINGS_JSONPATH

t1 = time.time()
#threading lock object for the json file
dict_lock = Lock()
cache_lock = Lock()



info_dict = {}
calendars_dict = {}
earnings_dict = {}

session = requests_cache.install_cache('yfinance_cache', expire_after=10800)  # Cache expires after 3 hours


#use this to store the tickers to retry if theres a 429 API block
retry_ticker_set = set()

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
    print(f"Estimated Minutes: {list_len//8*10//60}") # num of threads = 8, num of seconds to wait = 10
    
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
        download_controller (symbol_list=temp)
               
#download_controller()
