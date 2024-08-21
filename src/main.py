import os
import glob
import yfinance as yf
import numpy as np
import pandas as pd

financials_df = pd.read_csv("data/stockdata.csv")
financials_df = financials_df.set_index('Symbol')


def setting_cashflow_data(symbol, cashflow, ref):
    try:
        cashflow_col = cashflow[cashflow[ref]] 
        print(cashflow)
        if cashflow_col.isnull().any() == False: 
            financials_df.at[symbol, ref] = np.mean(cashflow_col)
            return None
    except KeyError:
        return None
    

def main ():

    setting_cashflow_data('aapl', yf.Ticker('aapl'), ref = "Sector")



if __name__ == '__main__':
    main()