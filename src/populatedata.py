import concurrent.futures
import pandas as pd

import yfinance as yf
import numpy as np
import time as t
from columnreferences import *

import requests_cache

financials_df = pd.read_csv("../data/stockdata.csv")
financials_df = financials_df.set_index('Symbol')

stockinfo_df = pd.read_csv("../data/stockdata.csv")
stockinfo_df = stockinfo_df.set_index('Symbol')

medsymbollist = financials_df.index[:24]
bigsymbollist = financials_df.index

session = requests_cache.CachedSession('yfinance.cache', backend='sqlite', expire_after=3600)
session.headers['User-agent'] = 'balancesheetparser'


def setting_financial_data(symbol, financials, ref):
    try:
        f = financials.loc[ref]   
        if f.isnull().any() == False: #check if the data has any NaN or None
            financials_df.at[symbol, ref] = np.mean(f)
            return None
    except KeyError:
        return None
    
    
def setting_earnings_data(symbol, earnings, ref):
    try:
        e = earnings[ref]
        print(f'{e}\n{symbol}') #to know if its delivering consistant data and not empty dfs    
        if e.isnull().any() == False: #check if the the data has any NaN or None #IMPORTANT some have size with NaN!
            financials_df.at[symbol, ref] = np.mean(e)
            return None
    except KeyError:
        return None


def setting_balancesheet_data(symbol, sheet, ref):
    try:
        b = sheet.loc[ref]    
        if b.isnull().any() == False:
            financials_df.at[symbol, ref] = np.mean(b)
            return None 
    except KeyError:
        return None

    
def setting_cashflow_data(symbol, cashflow, ref):
    try:
        c = cashflow.loc[ref] 
        if c.isnull().any() == False: 
            financials_df.at[symbol, ref] = np.mean(c)
            return None
    except KeyError:
        return None


def setting_tickerinfo_data(symbol, info, ref):
    try:
        i = info.values().loc[ref]
        stockinfo_df.at[symbol, ref] = i
        return None
    except KeyError:
        return None


nonUSD_symbols = []
nodata_symbols = []

def bulkdownload(symbol, sleepTimer: int = 6):

    '''
    bulk download of the data
    '''
    
    stock = yf.Ticker(symbol, session=session)
    
    #confirm USD denominated securities
    if stock.info['financialCurrency'] != 'USD':
        nonUSD_symbols.append(symbol)
    
    #confirm if data returned from API is 0  
    elif financials.size == 0 or cashflow.size == 0: #checking if the request returns no data
        nodata_symbols.append(symbol)

    else:
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
        #earnings (the columns and rows are swapped for this yfinance call so we use no ".loc" when selecting columns)
        for ref in earningsref:
            setting_earnings_data(symbol, earnings, ref)

    #to avoid exhausting the Yahoo Finance API limit. 6 seconds seems to be
    t.sleep(sleepTimer)



def threadhandler(method, stocklist):
    
    with concurrent.futures.ThreadPoolExecutor() as exe:
        t1 = t.time()
        exe.map(method, stocklist)  #use bigsymbollist when doing entire set

     #THIS IS UNSETTING 'SYMBOL' IN INDEX AND PUTTING IT BACK AS COLUMN. IMPORTANT FOR REPEATING
    for i in nodata_symbols: #clear out the empty's
        financials_df.drop(i, inplace = True)

    financials_df.reset_index()
    #main_df.to_csv("finaldb1.csv") # index=False optional arg
    #main_df.to_csv("backupfinaldb.csv") #extra just in case you mess up the first one :}
    t2 = t.time()
    print(f'Took about --> {t2-t1} seconds')
    
    
def normalizedf():
    '''
    normalize each value by equity. making a ratio for each reporting elements. 
    '''
    findata = pd.read_csv("../data/finaldb.csv")

    zeroequity = findata[findata['Total Stockholder Equity'].eq(0)]
    
    for i in zeroequity.index:
        findata.drop(i, inplace=True)
        
    findata = findata.reset_index(drop=True)

    for i in everyref: # columns
        if i != 'Total Stockholder Equity':

            idx = 0
            equity = findata.at [idx,'Total Stockholder Equity'] #getting equity value

            for x in findata[i]: # elements in each column

                ratio = x / equity
                findata.at[idx, i] = ratio
                idx += 1

    #findata.reset_index() ?
    findata.to_csv("../data/normalizeddb.csv", index=False)

    n(x) - looping for columns, dictionary the column with the row elements, 
    x^2 - double for loop