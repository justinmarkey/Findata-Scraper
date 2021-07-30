import concurrent.futures
import pandas as pd
import yfinance as yf
import statistics as s
import time as t

from csvdataframe import balancesheetref
from csvdataframe import cashflowref
from csvdataframe import earningsref
from csvdataframe import financialsref

from nullticker import emptytickers
#TEMP FOR TESTING
maindf = pd.read_csv("stockdata.csv")
maindf = maindf.set_index('Symbol')

nodata = []

medsymbollist = maindf.index[:12]
bigsymbollist = [x for x in maindf.index]


def populatedata(symbol):

    '''
    bulk download of the data
    '''
    stock = yf.Ticker(symbol)
    
    earnings = stock.earnings
    financials = stock.financials
    cashflow = stock.cashflow
    sheet = stock.balance_sheet

    #financials

    if financials.size == 0:
        nodata.append(symbol)
    
    for i in financialsref:
        try:
            f = financials.loc[i]
            
            if f.isnull().any() == False: #check if the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(f)
                
        except KeyError:
            continue
    #cashflow

    for i in cashflowref:
        try:
            c = cashflow.loc[i]
            
            if c.isnull().any() == False: 
                maindf.loc[symbol, i] = s.mean(c)
                
        except KeyError:
            continue
    #sheet

    for i in balancesheetref:
        try:
            b = sheet.loc[i]
            
            if b.isnull().any() == False:
                maindf.loc[symbol, i] = s.mean(b)
                
        except KeyError:
            continue

    #earnings (the columns and rows are swapped for this yfinance call so we use no ".loc" when selecting columns)
    for i in earningsref:
        try:
            e = earnings[i]
            print(e) #to know if its delivering consistant data and not empty df's
            print(symbol) #to find out how deep we are into the df
            if e.isnull().any() == False: #check if the the data has any NaN or None #IMPORTANT some have size with NaN!
                maindf.loc[symbol, i] = s.mean(e)
                
        except KeyError:
            continue
    
    t.sleep(30) #the use of shorter sleep times runs the risk of the program stopping hours in. Its safe to use 30 seconds from over 25 testing settings
def populatefinancials(symbol):
    financials = yf.Ticker(symbol).financials
    
    if financials.size == 0:
        nodata.append(symbol)
    for i in financialsref:
        try:
            f = financials.loc[i]
            
            if f.isnull().any() == False: #check if the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(f)
                print(f'ticker {symbol} -> {maindf.loc[symbol, i]}')
        except KeyError:
            continue
    t.sleep(20) #30 seconds is safe, but slow

def populatecashflow(symbol):
    cashflow = yf.Ticker(symbol).cashflow

    if cashflow.size == 0:
        nodata.append(symbol)
    for i in cashflowref:
        try:
            c = cashflow.loc[i]
            
            if c.isnull().any() == False: #check if the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(c)
                print(f'ticker {symbol} -> {maindf.loc[symbol, i]}')
        except KeyError:
            continue
    t.sleep(20) #30 seconds is safe, but slow

def populatebalancesheet(symbol):
    sheet = yf.Ticker(symbol).balance_sheet

    if sheet.size == 0:
        nodata.append(symbol)
    for i in balancesheetref:
        try:
            b = sheet.loc[i]
            
            if b.isnull().any() == False: #check if the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(b)
                print(f'ticker {symbol} -> {maindf.loc[symbol, i]}')
        except KeyError:
            continue
    t.sleep(20) #30 seconds is safe, but slow

def populateearnings(symbol):

    earnings = yf.Ticker(symbol).earnings
    
    if earnings.size == 0: #check for empty dataframe
        nodata.append(symbol)
    for i in earningsref:
        try: # TO CATCH ANY UNSUPPORTED REFS GIVEN BY THE YAHOO API
            e = earnings[i]
            
            if e.isnull().any() == False: #check if the the data has any NaN or None #IMPORTANT some have size with NaN!
                maindf.loc[symbol, i] = s.mean(e)
                print(f'ticker {symbol} -> {maindf.loc[symbol, i]}')
        except KeyError:
            continue
        
    t.sleep(20) #try 30 seconds to throttle api requests so that we dont get blocked off
def initthreads(method):
    
    with concurrent.futures.ThreadPoolExecutor() as exe:
        t1 = t.time()
        exe.map(method, bigsymbollist)  #use bigsymbollist when doing entire set

    maindf.reset_index() #THIS IS UNSETTING 'SYMBOL' IN INDEX AND PUTTING IT BACK AS COLUMN! IMPORTANT FOR REPEATING
    maindf.to_csv("finaldb1.csv") # index=False optional arg
    maindf.to_csv("backupfinaldb.csv") #extra just in case you mess up the second one :}
    t2 = t.time()
    print(f'Took about --> {t2-t1} seconds')
    print(nodata)
    
initthreads(populatedata)


def retrypopulate(): #retry for possibly missed data from repeated calls

    '''
    recalls all tickers in nodata and tries to find data for them :(
    '''

    df = pd.read_csv("finaldb.csv")

    for symbol in emptytickers:

        stock = yf.Ticker(symbol)
        earnings = stock.earnings
        financials = stock.financials
        cashflow = stock.cashflow
        sheet = stock.balance_sheet

        for i in financialsref:
            try:
                f = financials.loc[i]
                
                if f.isnull().any() == False: #check if the data has any NaN or None
                    df.loc[symbol, i] = s.mean(f)
            except KeyError:
                continue
        for i in cashflowref:
            try:
                c = cashflow.loc[i]
                
                if c.isnull().any() == False: 
                    df.loc[symbol, i] = s.mean(c)
                    
            except KeyError:
                continue
        for i in balancesheetref:
            try:
                b = sheet.loc[i]
                
                if b.isnull().any() == False:
                    df.loc[symbol, i] = s.mean(b)
                    
            except KeyError:
                continue
        
        for i in earningsref:
            try:
                e = earnings[i]
    
                if e.isnull().any() == False: #check if the the data has any NaN or None #IMPORTANT some have size with NaN!
                    df.loc[symbol, i] = s.mean(e)
                    
            except KeyError:
                continue

    df.to_csv("updatedfinaldb.csv")
#                                                                             cd ../../Projects/Python/'.\BalanceSheet Parser\'/
# using populatedata, it took 11900 seconds to complete or 3.5 hours