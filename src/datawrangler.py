import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor

import yfinance
import requests_cache

from columnreferences import *

#read into memory stockdata
financials_df = pd.read_csv("data/stockdata.csv")

financials_df = financials_df.set_index('Symbol')


#read into memory stockinfo data
#this must be loaded as dtype 'object' as the columns contain a mix of strs and ints
info_df = pd.read_csv("data/stockinfo.csv",dtype= 'object')

info_df = info_df.set_index('Symbol')

test_symbol_list = financials_df.index[:24]

symbol_list = financials_df.index

session = requests_cache.CachedSession('yfinance.cache')


def setting_financial_data(symbol, financials, ref):
    try:
        fin_col = financials[ref]
        if fin_col.isnull().any() == False: #check if the data has any NaN or None
            financials_df.at[symbol, ref] = np.mean(fin_col)
        
    except Exception as err:
        print(f"setting fin data error: {err} \n data = {financials} \n fincol = {fin_col} \n symbol = {symbol} \n ref = {ref}")


def setting_balancesheet_data(symbol, sheet, ref):
    try:
        balancesheet_col = sheet[ref]    
        if balancesheet_col.isnull().any() == False:
            financials_df.at[symbol, ref] = np.mean(balancesheet_col)
            
    except Exception as err:
        print(f"{err}")

    
def setting_cashflow_data(symbol, cashflow, ref):
    try:
        cashflow_col = cashflow[ref] 
        if cashflow_col.isnull().any() == False: 
            financials_df.at[symbol, ref] = np.mean(cashflow_col)
 
    except Exception as err:
        print(f"{err}")


def setting_tickerinfo_data(symbol, info, ref):
    try:
        info_col = info[ref]

        info_df.at[symbol, ref] = info_col

    except Exception as err:
        print(f"setting fin data error: {err} \n data = {info} \n fincol = {info_col} \n symbol = {symbol} \n ref = {ref}")

nonUSD_symbols = []
nodata_symbols = []

def download_stockdata(symbol, api_sleep_timer: int = 0.2):

    '''
    bulk download of the data
    '''
    try:
        stock = yfinance.Ticker(symbol, session=session)

        
        #confirm USD denominated securities
        if stock.info['financialCurrency'] != 'USD':
            nonUSD_symbols.append(symbol)
        #confirm if data returned from API is 0
        if stock.financials.size == 0 and stock.cashflow.size == 0:
            nodata_symbols.append(symbol)

        financials = stock.financials
        financials = financials.transpose()

        cashflow = stock.cashflow
        cashflow = cashflow.transpose()

        sheet = stock.balance_sheet
        sheet = sheet.transpose()

        info = stock.info

        for ref in inforef:
            setting_tickerinfo_data(symbol=symbol, info=info, ref=ref)

        for ref in financialsref:
            setting_financial_data(symbol, financials, ref)
        #cashflow   
        for ref in cashflowref:
            setting_cashflow_data(symbol, cashflow, ref)
        #sheet  
        for ref in balancesheetref:
            setting_balancesheet_data(symbol, sheet, ref)

        print(symbol)
        #to avoid exhausting the Yahoo Finance API limit.
        
        time.sleep(api_sleep_timer)

    except Exception as e:
        print (f"{symbol} caused {e}")

def threadhandler(method=download_stockdata, stocklist=test_symbol_list):

    #clear cache
    requests_cache.clear()

    with ThreadPoolExecutor(max_workers=1) as exe:
        exe.map(method, stocklist)

    #clear out empty's
    [financials_df.drop(x, inplace = True) for x in nodata_symbols]

    #reset the "Symbol" column as index
    financials_df.reset_index()
    info_df.reset_index()

    financials_df.to_csv("data/populated_data.csv")
    info_df.to_csv("data/populated_info.csv")
    
    
def normalizedf():

    '''
    normalize each value by equity. making a ratio for each reporting elements. 
    '''

    findata = pd.read_csv("data/populated_data.csv")

    zeroequity = findata[findata['Total Stockholder Equity'].eq(0)]
    
    [findata.drop(idx, inplace=True) for idx in zeroequity.index]
    #for idx in zeroequity.index:
        #findata.drop(idx, inplace=True)
        
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

if __name__ == '__main__':
    
    get_col_refs(ticker="AAPL")
    threadhandler()