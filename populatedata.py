import concurrent.futures
import pandas as pd

import yfinance as yf
import numpy as np
import time as t
from csvdataframe import balancesheetref, cashflowref, earningsref, financialsref, everyref

import requests_cache
#TEMP FOR TESTING
maindf = pd.read_csv("stockdata.csv")
maindf = maindf.set_index('Symbol')

medsymbollist = maindf.index[:24]
bigsymbollist = maindf.index

session = requests_cache.CachedSession('yfinance.cache')
session.headers['User-agent'] = 'balancesheetparser'

nodata = []
foreign = []

def settingfinancialdata(symbol, financials, i):
    try:
        f = financials.loc[i]   
        if f.isnull().any() == False: #check if the data has any NaN or None
            maindf.at[symbol, i] = np.mean(f)
            return None
    except KeyError:
        return None
def settingearningsdata(symbol, earnings, i):
    try:
        e = earnings[i]
        print(f'{e}\n{symbol}') #to know if its delivering consistant data and not empty dfs    
        if e.isnull().any() == False: #check if the the data has any NaN or None #IMPORTANT some have size with NaN!
            maindf.at[symbol, i] = np.mean(e)
            return None
    except KeyError:
        return None
def settingbalancesheetdata(symbol, sheet, i):
    try:
        b = sheet.loc[i]    
        if b.isnull().any() == False:
            maindf.at[symbol, i] = np.mean(b)
            return None 
    except KeyError:
        return None
def settingcashflowdata(symbol, cashflow, i):
    try:
        c = cashflow.loc[i] 
        if c.isnull().any() == False: 
            maindf.at[symbol, i] = np.mean(c)
            return None
    except KeyError:
        return None

def bulkdownload(symbol):

    '''
    bulk download of the data
    '''
    stock = yf.Ticker(symbol ,session=session)
    try:
        if stock.info['financialCurrency'] != 'USD':
            foreign.append(symbol) # we only want usd so that we can normalize the data
        else:
            earnings = stock.earnings
            financials = stock.financials
            cashflow = stock.cashflow
            sheet = stock.balance_sheet 
            #financials
            if financials.size == 0 or cashflow.size == 0: #checking if the request returns no data
                nodata.append(symbol)
            for i in financialsref:
                settingfinancialdata(symbol, financials, i)
            #cashflow   
            for i in cashflowref:
                settingcashflowdata(symbol, cashflow, i)
            #sheet  
            for i in balancesheetref:
                settingbalancesheetdata(symbol, sheet, i)
            #earnings (the columns and rows are swapped for this yfinance call so we use no ".loc" when selecting columns)
            for i in earningsref:
                settingearningsdata(symbol, earnings, i)
    except KeyError:
        pass
    t.sleep(6)

def threadhandler(method, stocklist: list):
    
    with concurrent.futures.ThreadPoolExecutor() as exe:
        t1 = t.time()
        exe.map(method, stocklist)  #use bigsymbollist when doing entire set

     #THIS IS UNSETTING 'SYMBOL' IN INDEX AND PUTTING IT BACK AS COLUMN! IMPORTANT FOR REPEATING
    for i in nodata: #clear out the empty's
        maindf.drop(i, inplace = True)

    maindf.reset_index()
    #maindf.to_csv("finaldb1.csv") # index=False optional arg
    #maindf.to_csv("backupfinaldb.csv") #extra just in case you mess up the first one :}
    t2 = t.time()
    print(f'Took about --> {t2-t1} seconds')
    
def normalizedf():
    '''
    normalize each value by equity. making a ratio for each reporting elements. 
    '''
    findata = pd.read_csv("finaldb.csv")

    zeroequity = findata[findata['Total Stockholder Equity'].eq(0)]
    
    for i in zeroequity.index:
        findata.drop(i, inplace=True)
        
    findata = findata.reset_index(drop=True)

    for i in everyref: # columns
        if i == 'Total Stockholder Equity': # dont want to normalize total stockholder equity by itself :}
            continue
        else:
            idx = 0
            equity = findata.at [idx, 'Total Stockholder Equity'] #getting equity value

            for x in findata[i]: # elements in each column

                ratio = x / equity
                findata.at[idx, i] = ratio
                idx += 1

    #findata.reset_index() ?
    findata.to_csv("normalizeddb.csv", index=False)

if __name__ == '__main__':
    pass
