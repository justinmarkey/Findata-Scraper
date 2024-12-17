import json
import pandas as pd
from datetime import date

#Modifies the JSON encoder to handle serializing datetime "date"
#converts the date object into isoformat. e.g.,date(YYYY, MM, DD) into YYYY-MM-DD

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        
        if isinstance(obj, date):
            return obj.isoformat()
        
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        
        return super().default(obj)