

import yfinance as yf


#calc sector avgs
symbol = "hd" #aapl #abgi


def send(symbol):
    a = yf.Ticker(symbol)
    a.earnings
    a.balance_sheet
    a.cashflow
    a.financials
    
    #recieve 3.2 1.5 Mbps
if __name__ == '__main__':
    send(symbol)
    
