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


# to access data[symbol][element] -> k:v = [date, value]
# compare data across the industry average.
# 1. load csvfile to get stock information
# 2. 

#@lru_cache
def get_industry_average (industry: str, element: str) -> None:
    
    #keep in mind, these stocks listed here are denominated in USD finances only. All nonUSD securities have been removed for simplicity.
    stockdata = pd.read_csv(STOCKLIST_CSVPATH)
    stock_listing_by_industry = stockdata [stockdata["Industry"] == industry]

    data = read_json_file(file_path=EARNINGS_JSONPATH)
    
    
    
    for symbol in stock_listing_by_industry["Symbol"]:
        try:
            print(type(data[symbol][element]))
        except KeyError:
            print(f"")
        

dataloaded = load_dataset()