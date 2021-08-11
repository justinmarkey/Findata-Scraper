import pandas as pd
import statistics as s
import yfinance as yf
from csvdataframe import balancesheetref
from csvdataframe import financialsref
from csvdataframe import cashflowref
from csvdataframe import earningsref
import time as t

findata = pd.read_csv('finaldb.csv')

def get_sectors():
    return pd.unique(findata['Sector'])

def get_industries():
    return pd.unique(findata['Industry'])


def get_dict():

    """
    returns a unique list of industries
    """
    
    industrysector_dict = {} #USE THIS TO n log n sort unique keys

    for sector in get_sectors():

        sectorfilter_df = findata[findata['Sector'] == sector]

        industry = pd.unique(sectorfilter_df['Industry'])
        
        industrysector_dict [sector] = industry 
    
    
    return industrysector_dict



if __name__ == '__main__':
    pass
    
