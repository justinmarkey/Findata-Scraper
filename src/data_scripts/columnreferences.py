import yfinance

newcsv_dropcolumns = (
    "Name",
    "Last Sale",
    "Net Change",
    "% Change",
    "Country",
    "IPO Year",
    "Volume",
)
    
  
def get_col_refs(ticker: str = "AAPL") -> None:
    
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

#get_col_refs()