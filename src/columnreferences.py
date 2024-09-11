import yfinance

newcsv_dropref = (
    "Name",
    "Last Sale",
    "Net Change",
    "% Change",
    "Country",
    "IPO Year",
    "Volume",
)

def get_col_refs(ticker: str) -> None:
    
    """
    Singular yfinance call to get the column references
    """

    stock = yfinance.Ticker(ticker)

    global balancesheetref
    global financialsref
    global cashflowref
    global everyref

    balancesheetref = stock.balance_sheet.index
    
    financialsref = stock.financials.index
    
    cashflowref = stock.cashflow.index
    
    everyref = balancesheetref.union(financialsref).union(cashflowref)

    print("Finished Retrieving the column references")