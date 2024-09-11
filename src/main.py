import pandas as pd
import time
import json

import yfinance
import requests_cache

from columnreferences import *
from makedirectory import makedirectory

financials_df = pd.read_csv("data/stockdata.csv")

symbols = financials_df["Symbol"]

session = requests_cache.CachedSession('yfinance.cache')

stock_calenders = []

def download_stockdata(symbol, session=session, api_sleep_timer=0.2) -> None:
    """
    downloads the stockdata by using the yfinance library and places the data into an sql table
    """
    
    stock = yfinance.Ticker(symbol, session=session)
    
    #confirm USD denominated securities
    if stock.info.get('financialCurrency') != 'USD':
        return
        
    financials = stock.financials.transpose()
    cashflow = stock.cashflow.transpose()
    sheet = stock.balancesheet.transpose()
    
    aggregated_df = pd.concat([financials, cashflow, sheet], axis=1)
    
    stock = stock.calendar
    stock["Symbol"] = symbol
    print(stock)
    stock_calenders.append(stock)
    
    time.sleep(api_sleep_timer)
  
download_stockdata("AAPL")

path = makedirectory("data/json/calenders")
with open(f'{path} + stock_calenders.json', 'w') as file:
    json.dump(stock_calenders, file, indent=4)