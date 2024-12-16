import pandas as pd
import glob

from src.utils.references import newcsv_keepcolumns

def find_csv(glob_pattern: str = "nasdaq_*") -> str:

    csv_root = "data/csv"
    
    glob_pattern = "nasdaq_*"

    csv_filename = glob.glob(f"{csv_root}/{glob_pattern}")
    
    return(csv_filename[0])


def clean_data():

    #find csv file name path
    csv_filename = find_csv()
    
    stock_df = pd.read_csv(csv_filename)
    
    #Drop the excess columns by keeping
    stock_df = stock_df[newcsv_keepcolumns]
    
    #Drop zero marketcap securities
    zero_Marketcap_droplist = stock_df[stock_df['Market Cap'].eq(0)] #get rid of zeros in marketcap
    stock_df = stock_df.drop (zero_Marketcap_droplist.index)
    print (f"\n{len(zero_Marketcap_droplist)} tickers had no specified Market Cap size\n")

    #Drop securites with no Sector or Industry data
    NaN_droplist = stock_df[stock_df.isnull().any(axis=1)] #get rid of NaN in any of the columns
    stock_df = stock_df.drop (NaN_droplist.index)
    print (f"{len(NaN_droplist)} tickers had no specified Sector or Industry \n")
    
    stock_df.reset_index()
    
    stock_df.to_csv('data/csv/stockdata.csv', index=False)