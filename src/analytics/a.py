import numpy as np
import pandas as pd
import statistics as s

from scipy import stats
import seaborn as sns

import time as t

from functools import lru_cache

from src.utils.jsonhelper import *
from src.utils.lib import *

from src.utils.datapaths import *
from src.analytics.load_dataset import *


def get_industry_average (industry: str, element: str) -> None:
    
    stockdata = pd.read_csv(STOCKLIST_CSVPATH)
    stock_listing_by_industry = stockdata [stockdata["Industry"] == industry] 
    
    symbols = stock_listing_by_industry["Symbol"]
    
    dataloaded = load_dataset(symbol_list=symbols)
    
    dataloaded = dataloaded [dataloaded["Element"] == element]
    
    return np.mean(dataloaded["Value"])
    
def get_sector_average (sector: str, element: str) -> None:
    
    stockdata = pd.read_csv(STOCKLIST_CSVPATH)
    stock_listing_by_sector = stockdata [stockdata["Sector"] == sector] 
    
    symbols = stock_listing_by_sector["Symbol"]
    
    dataloaded = load_dataset(symbol_list=symbols)
    
    dataloaded = dataloaded [dataloaded["Element"] == element]
    
    return np.mean(dataloaded["Value"])