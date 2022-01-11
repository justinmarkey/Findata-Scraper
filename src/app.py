#from industrycalc import *
import json
import pandas as pd
import yfinance as yf

tickers = json.loads(open('tickers.json').read())
def viewAll():
    if len(tickers) > 5:
        return "Too many tickers requested!"
    
    for i in tickers:
        balancesheet = yf.Ticker(i).balance_sheet
        cashflow = yf.Ticker(i).cashflow
        earnings = yf.Ticker(i).earnings
        financials = yf.Ticker(i).financials
        data = pd.DataFrame(balancesheet, cashflow, earnings, financials)
        print(data)
        #data = pd.DataFrame(balancesheet, cashflow, earnings, financials)
        # data.to_csv(f'{i}_findata.csv') #convert to csv
def viewBalanancesheet():
    for i in tickers:
        balancesheet = yf.Ticker(i).balance_sheet
        print(balancesheet)

def viewCashflow():
    for i in tickers:
        balancesheet = yf.Ticker(i).cashflow

def viewEarnings():
    for i in tickers:
        balancesheet = yf.Ticker(i).earnings

def viewFinancials():

    for i in tickers:
        balancesheet = yf.Ticker(i).financials

def sortBalancesheet():
    pass
def sortCashflow():
    pass
def sortFinancials():
    pass
def sortEarnings():
    pass

#viewAll()