import concurrent.futures
import pandas as pd
import yfinance as yf
import statistics as s
import numpy as np

balancesheetref = (
"Intangible Assets",
"Capital Surplus",
'Total Liab',
'Total Stockholder Equity',
"Minority Interest",
'Other Current Liab',
'Total Assets',
"Other Current Assets",
'Common Stock',
'Retained Earnings',
'Other Liab',
"Good Will",
'Treasury Stock',
'Other Assets',
'Cash',
'Total Current Liabilities',
'Other Stockholder Equity',
'Property Plant Equipment',
'Total Current Assets',
'Long Term Investments',
'Net Tangible Assets',
'Short Term Investments',
'Long Term Debt',
'Inventory',
'Accounts Payable',
"Deferred Long Term Asset Charges",
"Net Receivables",
'Short Long Term Debt',
)

financialsref = (
    'Research Development',
    'Income Before Tax',
    'Net Income',
    'Selling General Administrative',
    'Gross Profit',
    'Ebit',
    'Operating Income',
    'Operating Income',
    'Other Operating Expenses',
    'Interest Expense',
    'Income Tax Expense',
    'Total Revenue',
    'Total Operating Expenses',
    'Cost Of Revenue',
    'Total Other Income Expense Net',
    'Discontinued Operations',
    'Net Income From Continuing Ops',
    'Net Income Applicable To Common Shares',
)

cashflowref = (
    'Investments',
    'Change To Liabilities',
    'Total Cashflows From Investing Activities',
    'Net Borrowings',
    'Total Cash From Financing Activities',
    'Change To Operating Activities',
    'Net Income',
    'Change In Cash',
    'Repurchase Of Stock',
    'Total Cash From Operating Activities',
    'Depreciation',
    'Other Cashflows From Investing Activities',
    'Dividends Paid',
    'Change To Inventory',
    'Change To Account Receivables',
    'Other Cashflows From Financing Activities',
    'Change To Netincome',
    'Effect Of Exchange Rate',
    'Capital Expenditures',
    'Issuance Of Stock',
)

earningsref = (
    'Revenue',
    'Earnings',
)

symbollist = ['AACG', 'AACQ', 'AAL']
maindf = pd.read_csv("stockdata.csv")
maindf = maindf.set_index('Symbol')

def populateearnings():
    for symbol in symbollist:
        earnings = yf.Ticker(symbol).earnings
        for i in earningsref:
            try:
                e = earnings[i]
                if e.isnull().any() == False: #check if the the data has any NaN or None
                    maindf.loc[symbol, i] = s.mean(e)
                else:
                    pass
            except KeyError:
                continue


def populatefin():
    for symbol in symbollist:
        financials = yf.Ticker(symbol).financials
        for i in financialsref:
            try:
                f = financials.loc[i]
                if f.isnull().any() == False:
                    maindf.loc[symbol, i] = s.mean(f)
                    print(maindf.loc[symbol, i])
                else:
                    pass
            except KeyError:
                continue
def populatecashflow():
    for symbol in symbollist:
        cashflow = yf.Ticker(symbol).cashflow
        for i in cashflowref:
            try:
                c = cashflow.loc[i]
                if c.isnull().any() == False:
                    maindf.loc[symbol, i] = s.mean(c)
                    print(maindf.loc[symbol, i])
                else:
                    pass
            except KeyError:
                continue
        
def populatesheet():
    for symbol in symbollist:
        sheet = yf.Ticker(symbol).balance_sheet
        for i in balancesheetref:
            try:
                b = sheet.loc[i]
                if b.isnull().any() == False:
                    maindf.loc[symbol, i] = s.mean(b)
                else:
                    pass
            except KeyError:
                continue

        
#def populatedata():

    '''
    bulk download of the data
    '''
    
    for symbol in symbollist:    
        earnings = yf.Ticker(symbol).earnings
        financials = yf.Ticker(symbol).financials
        cashflow = yf.Ticker(symbol).cashflow
        sheet = yf.Ticker(symbol).balance_sheet
        
        for i in earningsref:
            e = earnings[i]
            if e.isnull().any() == False: #check if the the data has any NaN or None
                maindf.loc[symbol, i] = s.mean(e)
            else:
                pass

        for i in financialsref:
            try:
                f = financials.loc[i]
                if f.isnull().any() == False:
                    maindf.loc[symbol, i] = s.mean(f)
                    print(maindf.loc[symbol, i])
                else:
                    pass
            except KeyError:
                continue

        for i in cashflowref:
            try:
                c = cashflow.loc[i]
                if c.isnull().any() == False:
                    maindf.loc[symbol, i] = s.mean(c)
                    print(maindf.loc[symbol, i])
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

    x = maindf.loc[symbol, i]
    print(x)
    maindf.to_csv("test.csv", index=False)

#with concurrent.futures.ThreadPoolExecutor() as exe:
        #results = exe.map(populatedata, symbollist)
#sheet = yf.Ticker("FB").cashflow
#print(sheet)
#f = sheet.loc['Short Long Term Debt']
#print(f)
#if f.isnull().any() == False:
#    x = s.mean(f)
#else:
#    x = 0
#print (x)
