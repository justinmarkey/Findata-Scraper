import cleandata
import datascraper
import getstocklist

def download_all():
    """
    This method will download all securities it finds on the exchanges website.
    """
    
    #downloads from the exchange website
    getstocklist.get_current_stocklist()
    #clean the exchanges csv data, removing bad entries such as zero marketcap securities
    cleandata.clean_data()
    #Will download all stock data from yfinance
    datascraper.download_controller()
    
def download_specific(ticker):    
    datascraper.download_earnings(symbol=ticker)
    
    

if __name__ == "__main__":
    download_all()

