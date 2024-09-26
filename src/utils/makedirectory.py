import os

def makedirectory (target_dir: str) -> str:
    """
    Target_dir is the target path from within the Findata_Scraper project directory
    
    Returns the path.
    
    OK if dir exists.
    """
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = f"{current_dir}/../{target_dir}"
    os.makedirs(target_path, exist_ok=True)

    print(f"Successfully created dir:  {target_path}")
    
    return target_path