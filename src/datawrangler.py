import concurrent.futures
import pandas as pd

import yfinance as yf
import numpy as np
import timeit as t
from columnreferences import *


import requests_cache

#read into memory stockdata
financials_df = pd.read_csv("data/stockdata.csv")

financials_df = financials_df.set_index('Symbol')


#read into memory stockinfo data
stockinfo_df = pd.read_csv("data/stockinfo.csv")

stockinfo_df = stockinfo_df.set_index('Symbol')

test_symbol_list = financials_df.index[:24]
symbol_list = financials_df.index

session = requests_cache.CachedSession('yfinance.cache', expire_after=1800)

def setting_financial_data(symbol, financials, ref):
    try:
        fin_col = financials.loc[ref]
        print(fin_col)
        if fin_col.isnull().any() == False: #check if the data has any NaN or None
            financials_df.at[symbol, ref] = np.mean(fin_col)
        
    except KeyError as e:
        print(f"Symbol - {symbol} KeyError: {e}")

def setting_balancesheet_data(symbol, sheet, ref):
    try:
        bal_col = sheet.loc[ref]    
        if bal_col.isnull().any() == False:
            financials_df.at[symbol, ref] = np.mean(bal_col)
            return None 
    except KeyError:
        return None

    
def setting_cashflow_data(symbol, cashflow, ref):
    try:
        cashflow_col = cashflow[cashflow[ref]] 
        print(cashflow)
        if cashflow_col.isnull().any() == False: 
            financials_df.at[symbol, ref] = np.mean(cashflow_col)
            return None
    except KeyError:
        return None


def setting_tickerinfo_data(symbol, info, ref):
    try:
        info_col = info.values().loc[ref]

        stockinfo_df.at[symbol, ref] = info_col
        return None
    except KeyError:
        return None


nonUSD_symbols = []
nodata_symbols = []

def bulkdownload(symbol, api_sleep_timer: int = 6):

    '''
    bulk download of the data
    '''
    
    stock = yf.Ticker(symbol, session=session)
    
    #confirm USD denominated securities
    if stock.info['financialCurrency'] != 'USD':
        nonUSD_symbols.append(symbol)
    #confirm if data returned from API is 0  
    if financials.size == 0 or cashflow.size == 0:
        nodata_symbols.append(symbol)

        earnings = stock.earnings
        financials = stock.financials
        cashflow = stock.cashflow
        sheet = stock.balance_sheet
        info = stock.info

    for ref in inforef:
        setting_tickerinfo_data(symbol, info, ref)
        
    for ref in financialsref:
        setting_financial_data(symbol, financials, ref)
    #cashflow   
    for ref in cashflowref:
        setting_cashflow_data(symbol, cashflow, ref)
    #sheet  
    for ref in balancesheetref:
        setting_balancesheet_data(symbol, sheet, ref)

    #to avoid exhausting the Yahoo Finance API limit. 6 seconds seems to be the optimal time
    print(symbol)
    t.sleep(api_sleep_timer)

def threadhandler(method, stocklist):

    with concurrent.futures.ThreadPoolExecutor() as exe:

        exe.map(method, stocklist)

    #clear out empty's
    for i in nodata_symbols:
        financials_df.drop(i, inplace = True)

    #reset the "Symbol" column as index
    financials_df.reset_index()
    stockinfo_df.reset_index()

    financials_df.to_csv("data/populated_data.csv")
    stockinfo_df.to_csv("data/populated_info.csv")
    
    
def normalizedf():

    '''
    normalize each value by equity. making a ratio for each reporting elements. 
    '''

    findata = pd.read_csv("data/populated_data.csv")

    zeroequity = findata[findata['Total Stockholder Equity'].eq(0)]
    
    for idx in zeroequity.index:
        findata.drop(idx, inplace=True)
        
    findata = findata.reset_index(drop=True)

    for ref in everyref: # columns
        if ref != 'Total Stockholder Equity':

            idx = 0
            equity = findata.at [idx,'Total Stockholder Equity'] #getting equity value

            for x in findata[ref]: # elements in each column

                ratio = x / equity
                findata.at[idx, ref] = ratio
                idx += 1

    findata.to_csv("data/stockdata_normalized.csv", index=False)


#threadhandler(bulkdownload, symbol_list)
#t.timeit(threadhandler)