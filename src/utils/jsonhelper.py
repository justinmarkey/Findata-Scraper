import json
from jsonencoder import CustomEncoder

def read_json_file(file_path: str) -> dict:
    
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
            return data
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
       print(f"OK Rebuilding dict because {e}")  # Optional logging for debugging
       return {}
   

def write_json_file(file_path: str, data: dict) -> None:
    
    with open(file_path, "w") as file:
        #CustomEncoder is used change Datetime "Date" objs into compatible JSON strings
        json.dump(data, file, indent=4, cls=CustomEncoder)    

def update_json_info(db_path: str, new_data: dict) -> None:
    
    info = read_json_file(db_path)
    
    for ticker, value in new_data.items():
        info.setdefault(ticker, {})
        info[ticker].update(value)
        
    write_json_file(file_path=db_path, data=info)
    
def update_json_calendars(db_path: str, new_data: dict) -> None:
    
    calendars = read_json_file(db_path)
    
    for ticker, value in new_data.items():
        calendars.setdefault(ticker, {})
        calendars[ticker].update(value)

    write_json_file(file_path=db_path, data=calendars)


def update_json_earnings(db_path: str, new_data: dict) -> None:
    """
    Updates the JSON earnings data file with new earnings data.
    
    Args:
        db_path (str): Path to the JSON file storing current earnings data.
        new_data (dict): New earnings data to merge, with the format:
            {ticker: {date: {values}}}
    """

    current_data = read_json_file(db_path)
    
    for ticker, new_earnings in new_data.items():
        
        if ticker not in current_data:
            # Add the new ticker symbol
            current_data[ticker] = new_earnings
            
        else:
            for date, values in new_earnings.items():
                if date in current_data[ticker]:
                    # update earnings data for the date key
                    current_data[ticker][date].update(values)
                    
                else:
                    # Add the new date key
                    current_data[ticker][date] = values

    write_json_file(file_path=db_path, data=current_data)
