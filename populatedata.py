import concurrent.futures
import pandas as pd
import yfinance as yf
import statistics as s
import numpy as np
import time as t

from csvdataframe import balancesheetref
from csvdataframe import cashflowref
from csvdataframe import earningsref
from csvdataframe import financialsref


symbollist = ['AACG', 'AACQ', 'AAL','AAPL','FB','HD'] #TEMP FOR TESTING
maindf = pd.read_csv("stockdata.csv")
maindf = maindf.set_index('Symbol')


medsymbollist = maindf.index[:12]
bigsymbollist = [x for x in maindf.index]


def populatedata(symbol):

    '''
    bulk download of the data
    '''   
    earnings = yf.Ticker(symbol).earnings
    financials = yf.Ticker(symbol).financials
    cashflow = yf.Ticker(symbol).cashflow
    sheet = yf.Ticker(symbol).balance_sheet
    
    for i in earningsref:
        try:
            e = earnings[i]
            if e.isnull().any() == False: #check if the the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(e)
            else:
                pass
        except KeyError:
            continue
    
    for i in financialsref:
        try:
            f = financials.loc[i]
            if f.isnull().any() == False:
                maindf.loc[symbol, i] = s.mean(f)
            else:
                pass
        except KeyError:
            continue
    for i in cashflowref:
        try:
            c = cashflow.loc[i]
            if c.isnull().any() == False:
                maindf.loc[symbol, i] = s.mean(c)
            else:
                pass
        except KeyError:
            continue
    for i in balancesheetref:
        try:
            b = sheet.loc[i]
            if b.isnull().any() == False:
                maindf.loc[symbol, i] = s.mean(b)
            else:
                pass
        except KeyError:
            continue

nodata = []
referror = []

def populatefinancials(symbol):
    financials = yf.Ticker(symbol).financials

    for i in financialsref:
        try:
            f = financials.loc[i]
            if f.isnull().any() == False: #check if the the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(f)
            else:
                pass
        except KeyError:
            continue
    maindf.to_csv("test.csv", index=False)

def populatecashflow(symbol):
    cashflow = yf.Ticker(symbol).cashflow

    for i in cashflowref:
        try:
            c = cashflow.loc[i]
            if c.isnull().any() == False: #check if the the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(c)
            else:
                pass
        except KeyError:
            continue
    maindf.to_csv("test.csv", index=False)

def populatebalancesheet(symbol):
    sheet = yf.Ticker(symbol).balance_sheet

    for i in balancesheetref:
        try:
            b = sheet.loc[i]
            if b.isnull().any() == False: #check if the the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(b)
            else:
                pass
        except KeyError:
            continue
    maindf.to_csv("test.csv", index=False)

def populateearnings(symbol):
    counter = 0
    earnings = yf.Ticker(symbol).earnings
    while counter < 200: 
        if earnings.size == 0: #check for empty dataframe
            nodata.append(symbol)

        for i in earningsref:
            try: # TO CATCH ANY UNSUPPORTED REFS GIVEN BY THE API
                e = earnings[i]
                print(e)
                if e.isnull().any() == False: #check if the the data has any NaN or None #IMPORTANT some have size with NaN!
                    maindf.loc[symbol, i] = s.mean(e)
                    print(f'ticker {symbol} -> {maindf.loc[symbol, i]}')

            except KeyError:
                referror.append(symbol)
                continue
        counter += 1

    t.sleep(250) #try 30 seconds to throttle api requests so that we dont get blocked off
    counter = 0
def initthreads(method):
    
    with concurrent.futures.ThreadPoolExecutor() as exe:
        t1 = t.time()
        exe.map(method, medsymbollist)  #use bigsymbollist when doing entire set

    #maindf.to_csv("test1.csv", index=False)
    t2 = t.time()
    print('finished')
    print(f'Took about --> {t2-t1} seconds')
    print(nodata)
    print(referror)

initthreads(populateearnings)

#                                                                           cd ../../Projects/Python/Balancesheet Parser/


#600 or 4 requests a second over 150 seconds caused empty db error
#resets after 600 second wait?

#371 or 4 requests a second over 90 seconds caused empty db error