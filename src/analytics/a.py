import numpy as np
import pandas as pd
import statistics as s
import json
from scipy import stats
import seaborn as sns

import time as t

EARNINGS_JSONPATH = "data/json/earningsdata.json"


# Import the data
def build_dataframe():
    
    with open(file_path, "r") as file:
            data = json.load(file)
    
    with 


def shapiro_testing_sector(sector: str, element: str) -> None:
    data_filter = findata[findata["Sector"] == sector]
    data = data_filter[element] # select single column
    stat = stats.shapiro(data)
    return stat
def shapiro_testing_industry(industry: str, element: str) -> None:
    data_filter = findata[findata["Industry"] == industry]
    data = data_filter[element] # select single column
    stat = stats.shapiro(data)
    return stat