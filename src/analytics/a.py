import numpy as np
import pandas as pd
import statistics as s
from scipy import stats

#import seaborn as sns
#import matplotlib.pyplot as plt

import time as t

# Import the data



findata = pd.read_hdf("../../data/hdf5/earningsdata.h5",)

print (findata.columns)

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