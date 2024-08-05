import os
import glob
from datetime import date

def main():
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_download_dir = f"{current_dir}/../data/exchangelistcsv"
    print (target_download_dir)


if __name__ == '__main__':
    main()