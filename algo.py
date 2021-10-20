#essential basics

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


findata = pd.read_csv('normalizeddb.csv')


def get_sectors() -> int:
    return pd.unique(findata['Sector'])

def get_industries() -> int:
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

def find_ticker(data: pd.DataFrame, index: int) -> str:
    return data.at[index, 'Symbol']

def sector_mu(sector: str, element: str) -> None:
    
    data_filter = findata.filter(items=[sector, element])

    ignored_zero =[x for x in data_filter[element] if x != 0] #get index for n==0
    
    mu = s.mean(ignored_zero) #calc mean for non zeor 
    for index in data_filter.index:
        data_filter.at[index,element] = mu

    return s.mean(data_filter[element])
    
def show_scatterplot(data: pd.DataFrame, sector: str,element: str):
    
    #sns.scatterplot(data = data.filter(items=[sector, element]), x=data.index, y=element)
    # plt.show()
    sns.boxplot(data = data.filter(items=[sector, element]))
    plt.show()
if __name__ == '__main__':
    find_ticker(findata, 4120)
    show_scatterplot(findata,'Finance', 'Cash')
    
#                          cd Projects/Python/'.\BalanceSheet Parser\'