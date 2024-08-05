import os
import glob
from datetime import date

def main():
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_download_dir = f"{current_dir}/../data/exchangelistcsv"
    path_csv_files = glob.glob(f"{target_download_dir}/nasdaq_*")

    print (target_download_dir)
    print (path_csv_files)

if __name__ == '__main__':
    main()