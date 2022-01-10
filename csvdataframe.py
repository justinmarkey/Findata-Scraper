import pandas as pd
import numpy as np

nasdaq = pd.read_csv("./exchangestocks/nasdaq.csv")
nyse = pd.read_csv("./exchangestocks/nyse.csv")
amex = pd.read_csv("./exchangestocks/amex.csv")
dirtydata = pd.concat([nasdaq, nyse, amex], ignore_index=True) #ignore index cuz all indicies the same

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
    'Change In Cash',
    'Repurchase Of Stock',
    'Total Cash From Operating Activities',
    'Depreciation',
    'Other Cashflows From Investing Activities',
    'Dividends Paid',
    'Change To Inventory',
    'Change To Account Receivables',
    'Other Cashflows From Financing Activities',
    'Change To Net Income',
    'Capital Expenditures',
    'Issuance Of Stock',
)

earningsref = (
    'Revenue',
    'Earnings',
)

everyref = (
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
    'Research Development',
    'Income Before Tax',
    'Net Income',
    'Selling General Administrative',
    'Gross Profit',
    'Ebit',
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
    'Investments',
    'Change To Liabilities',
    'Total Cashflows From Investing Activities',
    'Net Borrowings',
    'Total Cash From Financing Activities',
    'Change To Operating Activities',
    'Change In Cash',
    'Repurchase Of Stock',
    'Total Cash From Operating Activities',
    'Depreciation',
    'Other Cashflows From Investing Activities',
    'Dividends Paid',
    'Change To Inventory',
    'Change To Account Receivables',
    'Other Cashflows From Financing Activities',
    'Change To Net Income',
    'Capital Expenditures',
    'Issuance Of Stock',
    'Revenue',
    'Earnings',
)
def clean(dirtydata):
    
    nandroplist = dirtydata[dirtydata.isnull().any(axis=1)] #get rid of entire row if NaN

    for i in nandroplist.index:
        dirtydata.drop(i, inplace=True)

    zerodroplist = dirtydata[dirtydata['Market Cap'].eq(0)] #get rid of zeros in marketcap
    
    for i in zerodroplist.index:
        dirtydata.drop(i, inplace=True)

    dirtydata = dirtydata.reset_index(drop=True)
    dirtydata.to_csv('stockdata.csv', index=False)

def addcolumns():
    '''
    used to prepopulate df with columns and zeros so we can easily make changes to it in the future
    '''
    cleaneddata = pd.read_csv('stockdata.csv')
    
    for i in everyref:
        cleaneddata[i] = np.zeros(len(cleaneddata))

    print(cleaneddata)
    cleaneddata.reset_index(drop=True)
    cleaneddata.to_csv('stockdata.csv', index=False)
#maindf = pd.read_csv('stockdata.csv') 

#clean(dirtydata)
#addcolumns()