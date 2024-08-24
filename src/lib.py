import pandas as pd
#import seaborn as sns


"""
This contains a number of wrapper functions for ease of use and also extends the functionality of the software
"""
def get_sectors():
    return pd.unique(findata['Sector'])

def get_industries():
    return pd.unique(findata['Industry'])

def get_dict() -> dict:

    """
    returns a dict with the key being the sector, and the values being each industry in that sector
    """
    
    industrysector_dict = {}
    
    for sector in get_sectors():

        sectorfilter_df = findata[findata['Sector'] == sector]

        industry = pd.unique(sectorfilter_df['Industry'])
        
        industrysector_dict [sector] = industry 

    return industrysector_dict

def get_num_of_tickers(sector: str, industry: bool = False) -> int: 
    '''
    pass industry = True, if you're passing industries instead of sectors
    '''
    if industry == True:
        return len (findata[findata['Industry'] == sector])
    else:
        return len (findata[findata['Sector'] == sector])

def find_ticker_by_index(data: pd.DataFrame, index: int) -> str:
    return data.at[index, 'Symbol']

def show_scatterplot(data: pd.DataFrame, sector: str, element: str):
        sns.scatterplot(data = data.filter(items=[sector, element]), x=data.index, y=element)
        plt.show()