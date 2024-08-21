import yfinance as yf

balancesheetref = None
financialsref = None
cashflowref = None
everyref = None

inforef = None

newcsv_dropref = (
    "Name",
    "Last Sale",
    "Net Change",
    "% Change",
    "Country",
    "IPO Year",
    "Volume",
)

def get_col_refs():
    stock = yf.Ticker("AAPL")

    balancesheetref = stock.balance_sheet.index
    
    financialsref = stock.financials.index
    
    cashflowref = stock.cashflow.index
    
    everyref = balancesheetref.union(financialsref).union(cashflowref)

    inforef = stock.info.values()
  


get_col_refs()