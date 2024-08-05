import pandas as pd
import glob
import os
import numpy as np
from columnreferences import *


def cleandata():

    #find csv file name
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_dir = f"{current_dir}/../data/exchangelistcsv"
    
    csv_file = glob.glob(f"{csv_file_dir}/nasdaq_")

    stock_df = pd.read_csv(csv_file)
    
    zerodroplist = stock_df[stock_df['Market Cap'].eq(0)] #get rid of zeros in marketcap
    stock_df = stock_df.drop (zerodroplist.index)
    print (f"\n{len(zerodroplist)} tickers had no specified Market Cap size\n")

    nandroplist = stock_df[stock_df.isnull().any(axis=1)] #get rid of NaN in any of the columns
    stock_df = stock_df.drop (nandroplist.index)
    print (f"{len(nandroplist)} tickers had no specified Sector or industry \n")

    #create df with financial colummns
    financialcolumns_df = pd.DataFrame(columns=everyref)
    financials_df = pd.concat([stock_df,financialcolumns_df], axis=1)

    infocolumns_df = pd.DataFrame(columns=inforef)
    stockinfo_df = pd.concat([stock_df,infocolumns_df], axis=1)

    financials_df.reset_index(drop=True)
    stockinfo_df.reset_index(drop=True)

    print (financials_df)
    financials_df.to_csv('data/stockdata.csv', index=False)
    stockinfo_df.to_csv('data/stockinfo.csv', index=False)