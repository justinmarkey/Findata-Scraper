import os
import time
import stat
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
    #firefox_options.set_preference("browser.download.defaultFolder", target_download_dir)
    #firefox_options.set_preference("browser.download.lastDir", target_download_dir)
    firefox_options.set_preference("browser.download.folderList", 2)  # Custom location
    firefox_options.set_preference("browser.download.dir", target_download_dir)  # Specify the custom directory
    firefox_options.set_preference("browser.download.useDownloadDir", True)
    firefox_options.set_preference("browser.helperApps.neverAsk.saveToDisk", 
                                "application/csv,application/excel,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain")
    
    firefox_service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=firefox_service, options=firefox_options)
    
    try:
        driver.get(url_stocklist)
        wait = WebDriverWait(driver, 10)  # Increased wait time for reliability

        # Handle cookie banner if present
        try:
            cookie_banner = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            cookie_banner.click()
            print("Cookie banner accepted.")
        except Exception as e:
            print(f"Cookie banner handling error (ignored if not present): {e}")
        # Wait for the Download CSV button to be clickable
        try:
            download_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Download CSV')]")
            ))
            # Scroll to the button (optional, but helps in some cases)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",download_button)
            time.sleep(1)  # Small delay to ensure scrolling has completed
            # Click the button
            download_button.click()
            print("Download button clicked.")
            # Give time for download to complete (adjust as needed)
            time.sleep(5)
            print("Download completed.")
        except Exception as e:
            print(f"Error interacting with download button: {e}")
    finally:
        driver.quit()
        print("WebDriver closed.")

def get_current_stocklist():
    """
    Master script function for getting the stocklist from nasdaq website
    """
    #make directory path
    
    csv_path = f"{Path(__file__).resolve().parent.parent}/data/csv"
    os.makedirs(csv_path, exist_ok=True)
    
    path_csv_files = glob.glob(f"{csv_path}/nasdaq_*")
    
    
    #cleaning the target download directory
    for csv_file in path_csv_files:
        if os.path.exists(csv_file):
            os.remove(csv_file)
            print(f"Removed {csv_file}")
    # Check if the directory is accessible and writable
    if os.access(csv_path, os.W_OK):
        print(f"Directory {csv_path} is writable.")
    else:
        os.chmod(csv_path, stat.S_IWRITE | stat.S_IWOTH)
        
    fetch_nasdaq_stocklist(target_download_dir=csv_path)
    rename_downloaded_csv(target_download_dir=csv_path)
    print("Successfully fetched csv")
    
get_current_stocklist()