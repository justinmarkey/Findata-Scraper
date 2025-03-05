import pandas as pd

from functools import lru_cache

from src.utils.jsonhelper import *
from src.utils.lib import *

from src.utils.datapaths import *

# Flatten data into a list of records

def load_dataset(json_data_path: str = EARNINGS_JSONPATH, symbol_list: list = None) -> None:
    """

    
    Args:
        json_data_path (str): Path to the JSON data file.
        symbol_list (list, optional): List of symbols to filter. Defaults to None (all symbols).

    Returns:
        pd.DataFrame: DataFrame containing statistics for selected symbols.
    """
    data = read_json_file(file_path=json_data_path)
    
    # If symbol_list is None, include all symbols
    if symbol_list is None:
        symbol_list = list(data.keys())

    records = []

    for symbol in symbol_list:
        if symbol in data:  # Ensure symbol exists in data
            for element, dates in data[symbol].items():
                for date, value in dates.items():
                    records.append({
                        "Symbol": symbol,
                        "Element": element,
                        "Date": date,
                        "Value": value
                    })

    df = pd.DataFrame(records)

    if df.empty:
        print("No data available for selected symbols.")
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"])

    # Compute statistics for each element across selected symbols
    #stats = df.groupby("Element")["Value"].describe(percentiles=[0.25, 0.5, 0.75], include="all")

    return df
