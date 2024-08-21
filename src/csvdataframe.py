import pandas as pd
import glob
import os

from columnreferences import *

def find_csv(glob_pattern: str = "nasdaq_*") -> str:

    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_dir = f"{current_dir}/../data/exchangelistcsv"
    glob_pattern = "nasdaq_*"

    csv_filename = glob.glob(f"{csv_file_dir}/{glob_pattern}")

    return(csv_filename)

def clean_data():

    #find csv file name
    csv_filename = find_csv()
    stock_df = pd.read_csv(csv_filename)
    
    #Drop columns that are unnecessary
    stock_df = stock_df.drop(columns=[x for x in newcsv_dropref])
    
    #Drop zero marketcap securities
    zero_Marketcap_droplist = stock_df[stock_df['Market Cap'].eq(0)] #get rid of zeros in marketcap
    stock_df = stock_df.drop (zero_Marketcap_droplist.index)
    print (f"\n{len(zero_Marketcap_droplist)} tickers had no specified Market Cap size\n")

    #Drop securites with NaN in the data
    NaN_droplist = stock_df[stock_df.isnull().any(axis=1)] #get rid of NaN in any of the columns
    stock_df = stock_df.drop (NaN_droplist.index)
    print (f"{len(NaN_droplist)} tickers had no specified Sector or Industry \n")

    #create stock data df with financial colummns
    financialcolumns_df = pd.DataFrame(columns=everyref)
    financials_df = pd.concat([stock_df,financialcolumns_df], axis=1)

    #create stock info df with inforef columns
    infocolumns_df = pd.DataFrame(columns=inforef)
    stockinfo_df = pd.concat([stock_df,infocolumns_df], axis=1)

    #reset the index on the df's
    financials_df.reset_index(drop=True)
    stockinfo_df.reset_index(drop=True)

    #convert into csv
    financials_df.to_csv('data/stockdata.csv', index=False)
    stockinfo_df.to_csv('data/stockinfo.csv', index=False)

clean_data()