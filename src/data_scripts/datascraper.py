import pandas as pd
import time
import json
import yfinance

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from utils.jsonencoder import CustomEncoder

#threading lock object for the hdf5 file
hdf5_lock = Lock()

t1 = time.time()

stock_calenders = {}
stock_info = {}


def download_earnings (symbol):
    """
    downloads the stockdata by using the yfinance library and places the data
    into an sql table
    """
    
    stock = yfinance.Ticker(symbol)
    
    #confirm USD denominated earnings data
    if stock.info.get('financialCurrency') != 'USD':
        print(f"{symbol} is non USD denominated\n")
        return
        
    #swap the datetime and the financial reference
    financials = stock.financials.transpose()
    cashflow = stock.cashflow.transpose()
    sheet = stock.balancesheet.transpose()
    
    calender = stock.calendar
    info = stock.info  
    
    if len(info) == 0:
        t3 = time.time()
        print(f"\nPossible API block at {t3-t1}")
    
    #concat along the datetime index axis
    aggregated_df = pd.concat([financials, cashflow, sheet], axis=1)
    
    #fill dictionaries (later to be stored as JSON files)
    stock_calenders[symbol] = calender
    stock_info[symbol] = info
    
    #change dtype from "object" to "float64" as hdf5 format does not support ambigious types
    aggregated_df = aggregated_df.astype({col: 'float64' for col in aggregated_df.select_dtypes(include=['object']).columns})
    
    hdf5_path = "../data/hdf5/earningsdata.h5"
    
    with hdf5_lock:
        with pd.HDFStore(path=hdf5_path, mode='a') as store:
            if symbol in store.keys():
                """
                HDF5 does not have a simple way of dealing with duplicated data - 
                so manual deduplication is required.
                """

                df_existing = pd.read_hdf(hdf5_path, key=symbol)

                df_combined = pd.concat([df_existing, aggregated_df], axis=1)

                df_combined.drop_duplicates(inplace=True)

                # Overwrite the HDF5 file with the deduplicated data
                df_combined.to_hdf(hdf5_path, index= True, key=symbol, mode='w',
                                   format='table', complevel=9, complib='blosc')
            else:
                aggregated_df.to_hdf (hdf5_path, key=symbol, mode='a', index=True, 
                                      format='table', complevel=9, complib='blosc')
    
    print(f"{symbol}\n")
    time.sleep(0.42)
    return
    
def download_controller (method = download_earnings):
    """
    Master script for controlling downloads
    """
    
    financials_df = pd.read_csv("data/csv/stockdata.csv")
    symbols = financials_df["Symbol"].to_list()
    
    list_len = len(symbols)
    
    print(f"Downloading started for {list_len}\n")
    
    with ThreadPoolExecutor(max_workers=8) as tpe:
        tpe.map(method, symbols)
        
    t2 = time.time()
    print(f"Download Fin Statement Data took {t2-t1} seconds")

    #CustomEncoder is used change Datetime "Date" objs into compatible JSON strings
    with open(f'data/json/calenders.json', 'w') as file:
        json.dump(stock_calenders, file, cls=CustomEncoder, indent=4)

    with open(f'data/json/info.json', 'w') as file:
        json.dump(stock_info, file, cls=CustomEncoder, indent=4)

download_controller()
