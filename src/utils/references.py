import yfinance
import json

newcsv_dropcolumns = (
    "Name",
    "Last Sale",
    "Net Change",
    "% Change",
    "Country",
    "IPO Year",
    "Volume",
)
    
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
    
def get_nested_info_refs(symbol: str = "AAPL"):
    with open("data/json/info.json", 'r') as info_data:
        info = json.load(info_data)
    return list(info[symbol].keys())