import yfinance
import json

#specify which columns to keep for the cleandata.py
newcsv_keepcolumns = [
    "Symbol",
    "Market Cap",
    "Industry",
    "Sector",
]

def get_nested_info_refs(symbol: str = "AAPL"):
    with open("data/json/info.json", 'r') as info_data:
        info = json.load(info_data)
    return list(info[symbol].keys())

#currently not used 
def get_col_refs(ticker: str = "AAPL"):
    
    """
    Singular yfinance call to get the column references
    """

    stock = yfinance.Ticker(ticker)

    balancesheetref = stock.balancesheet.index
    
    financialsref = stock.financials.index
    
    cashflowref = stock.cashflow.index
    
    everyref = balancesheetref.union(financialsref).union(cashflowref)

    print("Finished Retrieving the column references")
    
    # Return all the references as a dictionary
    return {
        'balancesheetref': balancesheetref,
        'financialsref': financialsref,
        'cashflowref': cashflowref,
        'everyref': everyref
    }