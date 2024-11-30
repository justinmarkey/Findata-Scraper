import os
import time
from datetime import date
import glob
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.firefox import GeckoDriverManager


def rename_downloaded_csv(target_download_dir: str) -> None:
    
    #identify the file name
    file_prefix = "nasdaq_screener_"
    pattern = f"{target_download_dir}/{file_prefix}*"
    matchingCSV_files = glob.glob(pattern)
    
    #todays date and format the str
    today_date = date.today()
    today_date_str = today_date.strftime("%Y%m%d")

    #rename
    original_file_path = matchingCSV_files[0]
    new_file_path = f"{target_download_dir}/nasdaq_stocklist{today_date_str}.csv"
    os.rename(original_file_path, new_file_path)


def fetch_nasdaq_stocklist(target_download_dir: str) -> None:
    """
    selenium setup to click the download button for 
    """

    url_stocklist = "https://www.nasdaq.com/market-activity/stocks/screener"

    firefox_options = Options()
    #disable the browser gui
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--private")
    firefox_options.add_argument("--disable-notifications")
    firefox_options.add_argument("--start-maximized")
    
    #set custom download path

    profile = webdriver.FirefoxProfile()
    profile.set_preference("browser.download.folderList", 2)
    profile.set_preference("browser.download.dir", target_download_dir)
    profile.set_preference("browser.helperApps.neverAsk.saveToDisk", 
    "application/csv,application/excel,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain")
    firefox_options.profile = profile
    

    firefox_service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=firefox_service, options=firefox_options)

    driver.get(url_stocklist)

    wait = WebDriverWait(driver, 10)

    #accept the cookie banner. Note: the cookie banner is blocking the download button
    cookie_banner = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='onetrust-accept-btn-handler']")))
    cookie_banner.click()

    time.sleep(1)

    download_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/main/div[2]/article/div[3]/div[1]/div/div/div[3]/div[2]/div[2]/div/button")))
    download_button.click()

    #wait for download
    time.sleep(3)

    driver.quit()
    

def get_current_stocklist():
    """
    Master script function for getting the stocklist from nasdaq website
    """
    #make directory path
    
    csv_root = f"{Path(__file__).resolve().parent.parent}/data/csv"
    os.makedirs(csv_root, exist_ok=True)
    
    path_csv_files = glob.glob(f"{csv_root}/nasdaq_*")
    
    #cleaning the target download directory
    for csv_file in path_csv_files:
        if os.path.exists(csv_file):
            os.remove(csv_file)
            
    
    fetch_nasdaq_stocklist(csv_root)
    rename_downloaded_csv(csv_root)
    print("Successfully fetched csv")