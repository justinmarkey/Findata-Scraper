import pandas as pd
import glob
from utils.makedirectory import makedirectory

from data_scripts.columnreferences import *


def find_csv(glob_pattern: str = "nasdaq_*") -> str:

    csv_file_dir = makedirectory("data/csv")
    
    glob_pattern = "nasdaq_*"

    csv_filename = glob.glob(f"{csv_file_dir}/{glob_pattern}")

    return(csv_filename[0])


def clean_data():

    #find csv file name path
    csv_filename = find_csv()
    
    stock_df = pd.read_csv(csv_filename)
    
    #Drop unused columns
    stock_df = stock_df.drop(columns=[x for x in newcsv_dropcolumns])
    
    #Drop zero marketcap securities
    zero_Marketcap_droplist = stock_df[stock_df['Market Cap'].eq(0)] #get rid of zeros in marketcap
    stock_df = stock_df.drop (zero_Marketcap_droplist.index)
    print (f"\n{len(zero_Marketcap_droplist)} tickers had no specified Market Cap size\n")

    #Drop securites with no Sector or Industry data
    NaN_droplist = stock_df[stock_df.isnull().any(axis=1)] #get rid of NaN in any of the columns
    stock_df = stock_df.drop (NaN_droplist.index)
    print (f"{len(NaN_droplist)} tickers had no specified Sector or Industry \n")
    
    #Get data refs. Arbitrarily using AAPL
    data_refs = get_col_refs("AAPL")
        
    #create stock data df with financial colummns
    financialcolumns_df = pd.DataFrame(columns=data_refs["everyref"])
    financials_df = pd.concat([stock_df,financialcolumns_df], axis=1)
    
    financials_df.reset_index()
    
    financials_df.to_csv('data/csv/stockdata.csv', index=False)
    
clean_data()