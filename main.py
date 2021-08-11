import yfinance as yf


#calc sector avgs
symbol = "hd" #aapl #abgi


def send(symbol):
    a = yf.Ticker(symbol)

    print (a.balance_sheet)
    
    
    #recieve 3.2 1.5 Mbps
if __name__ == '__main__':
    #send(symbol)
    pass
