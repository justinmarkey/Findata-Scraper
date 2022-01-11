import pandas as pd
import time as t
from populatedata import bigsymbollist
from datetime import datetime
# import earnings calender, make request after release of earnings, and update the database using pd.at(idx, column)


outdated_counter = 0

data = pd.read_csv('finaldb.csv')

def run_test():
    for i in earnings_calender:
