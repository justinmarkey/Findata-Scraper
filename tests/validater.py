tickers = ["X", "Y", "Z"]
retry_ticker_set = set(tickers)
print(retry_ticker_set)

def func (symbol_lst: list) -> None:
    
    for i in symbol_lst:
        print(i)
        
    
    global retry_ticker_set
    if len(retry_ticker_set) != 0:
        print(f"Retrying API requests for {retry_ticker_set}\nwaiting 30 seconds")
        to_retry = symbol_lst
        retry_ticker_set = set()
        func(symbol_lst=to_retry)

func(["AAPL", "BABA", "GOOGL"])
print(retry_ticker_set)
retry_ticker_set.add(1)
print(retry_ticker_set)