import pandas as pd
import numpy as np
import yfinance as yf
from csvdataframe import balancesheetref
from csvdataframe import financialsref
from csvdataframe import cashflowref
from csvdataframe import earningsref

findata = pd.read_csv('finaldb.csv')

