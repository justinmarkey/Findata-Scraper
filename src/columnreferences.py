import yfinance as yf

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

    global balancesheetref
    global financialsref
    global cashflowref
    global everyref
    global inforef

    balancesheetref = stock.balance_sheet.index
    
    financialsref = stock.financials.index
    
    cashflowref = stock.cashflow.index
    
    everyref = balancesheetref.union(financialsref).union(cashflowref)

    inforef = stock.info.values()

get_col_refs()
