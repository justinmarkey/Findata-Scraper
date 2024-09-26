from concurrent.futures import ThreadPoolExecutor
import yfinance 
import requests_cache
import time
import pandas as pd

session = requests_cache.CachedSession('test.cache')

def add (symbol):
    stock = yfinance.Ticker(symbol, session=session)
    print(stock)
    time.sleep(1)


def threadhandler (method = add):
       
    financials_df = pd.read_csv("data/csv/stockdata.csv")
    symbols = financials_df["Symbol"]
    
    with ThreadPoolExecutor() as tpe:
        tpe.map(method, symbols)
        
    print("done")
        
        
threadhandler()
session.cache.clear()
