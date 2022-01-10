#essential basics

from typing import List, Tuple
import numpy as np

import pandas as pd
import statistics as s
from scipy import stats


#references to other py files
from csvdataframe import balancesheetref, financialsref, cashflowref, earningsref, everyref

#data display
import seaborn as sns
import matplotlib.pyplot as plt

#utilities
import time as t

# Import the data
findata = pd.read_csv('normalizeddb.csv')

### Helper functions for Pandas
def get_sectors():
    return pd.unique(findata['Sector'])

def get_industries():
    return pd.unique(findata['Industry'])

def get_dict() -> dict:

    """
    returns a dict with the key being the sector, and the values being each industry in that sector
    """
    
    industrysector_dict = {} #USE THIS TO n log n sort unique keys
    
    for sector in get_sectors():

        sectorfilter_df = findata[findata['Sector'] == sector]

        industry = pd.unique(sectorfilter_df['Industry'])
        
        industrysector_dict [sector] = industry 

    return industrysector_dict

def get_num_of_tickers(sector: str, industry: bool = False) -> int: 
    '''
    pass industry = true, if youre passing industries instead of sectors
    '''
    if industry == True:
        return len (findata[findata['Industry'] == sector])
    else:
        return len (findata[findata['Sector'] == sector])

def find_ticker_by_index(data: pd.DataFrame, index: int) -> str:
    return data.at[index, 'Symbol']


### STATS

def shapiro_testing_sector(sector: str, element: str) -> None:
    data_filter = findata[findata["Sector"] == sector]

    data = data_filter[element] # select single column

    stat = stats.shapiro(data)
    print(stat)

def shapiro_testing_industry(industry: str, element: str) -> None:
    data_filter = findata[findata["Industry"] == industry]

    data = data_filter[element] # select single column

    stat = stats.shapiro(data)
    print(stat)

def sector_attrs(sector: str, element: str):
    """
    returns log mean, coeff added to transform to positive data (based on min of dataset), logged datapoints
    """

    data_filter = findata.filter(items=["Symbol", sector, element])
    
    coeff = min (data_filter[element])
    
    coeff = np.abs(coeff)+1
    
    ignored_zero =[np.log(x+coeff) for x in data_filter[element] if x != 0]
    

    log_mu = s.fmean(ignored_zero) #calc mean for untransformed data. 
    
    idx = 0
    for i in data_filter[element]: #settings the transformations and logs each data point
        
        if i == 0:
            data_filter.at[idx, element] = log_mu  #transmutation of zero's by the mean
        else:
            data_filter.at[idx, element] = np.log(data_filter.at[idx, element] + coeff)

        idx += 1


    return (log_mu , coeff, data_filter)



def zscore_logged_data(sector: str, element: str):
    """
    The goal of this is to capture the outliers
    """
    attrs = sector_attrs(sector, element)
    
    log_data = attrs[2]
    
    
    log_data[element] = stats.zscore(log_data[element]) #set column to z scores
    
    return (log_data) # returns zscored data and stdev



def outliers (sector: str, element: str):
    """
    involves putting the data back into a matched dataframe with symbols for each z score value.
    """
    zscore_data = zscore_logged_data(sector, element)

    # Sorting algorithm
    negative_zscores = zscore_data.sort_values(by = element, ascending=True)
    
    positive_zscores = zscore_data.sort_values(by = element, ascending=False)

    return (negative_zscores, positive_zscores)

def show_scatterplot(data: pd.DataFrame, sector: str, element: str):
    sns.scatterplot(data = data.filter(items=[sector, element]), x=data.index, y=element)
    plt.show()

if __name__ == '__main__':
    
    outliers("Miscellaneous", "Net Income")

    #outliers("Miscellaneous", "Net Income")
#                          cd Projects/Python/'.\BalanceSheet Parser\'
