import time as t
import yfinance as yf

#calc sector avgs
i = "adbe"
#yf.Ticker(i).quarterly_financials
#yf.Ticker(i).quarterly_cashflow
#yf.Ticker(i).quarterly_earnings
#yf.Ticker(i).quarterly_balance_sheet

#print(yf.Ticker(i).quarterly_financials)
#print(yf.Ticker(i).quarterly_balancesheet)
#print(yf.Ticker(i).quarterly_cashflow)
#print(yf.Ticker(i).quarterly_earnings)

def send(i):
    a = yf.Ticker(i).earnings
    print(a.size)
    print(a)
    
if __name__ == '__main__':
    send(i)
