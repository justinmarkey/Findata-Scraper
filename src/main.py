import json

def main (symbol: str = "AAPL"):
    with open("data/json/info.json", 'r') as info_data:
        info = json.load(info_data)
    print(list(info[symbol].keys()))
    
    with open("data/json/info.json", 'r') as info_data:
        info = json.load(info_data)
        print(list(info[symbol].keys()))
    
if __name__ == "__main__":
    main()
