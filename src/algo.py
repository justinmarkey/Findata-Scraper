import numpy as np
import pandas as pd
import statistics as s
from scipy import stats

from data_scripts.csvdataframe import balancesheetref, financialsref, cashflowref, earningsref, everyref

import seaborn as sns
import matplotlib.pyplot as plt

import time as t

# Import the data
findata = pd.read_csv('../data/normalizeddb.csv')

### Helper functions for Pandas
class testing():
    def __init__(self, findata: pd.DataFrame,sector: str, element: str):

        findata = self.findata
        sector = self.sector
        element = self.element

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


"""
These are the types of testing you can call to play with the data
"""
class norm():
    def __init__(self, findata: pd.DataFrame, sector: str, element: str):

        findata = self.findata
        sector = self.sector
        element = self.element



    def sector_attrs(sector: str, element: str):
        data_filter = findata.filter(items=["Symbol", sector, element])

        log_mu = s.fmean(data_filter[element])


        return (log_mu, data_filter)

class logged_norm():

    def __init__(self, findata: pd.DataFrame, sector: str, element: str):

        findata = self.findata
        sector = self.sector
        element = self.element


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


### STATS

if __name__ == '__main__':
    pass
    # sector = "Miscellaneous"
    # industry = "Net Income"

#                          cd Projects/Python/'.\BalanceSheet Parser\'
