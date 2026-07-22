import os
from pathlib import Path

def list_raw():
    raw_dir = Path("data/raw_reports")
    if not raw_dir.exists():
        print("data/raw_reports does not exist")
        return
        
    for company_dir in raw_dir.iterdir():
        if company_dir.is_dir() and not company_dir.name.startswith("_"):
            file_count = sum(len(files) for _, _, files in os.walk(company_dir))
            print(f"Company: {company_dir.name} | Files: {file_count}")

if __name__ == "__main__":
    list_raw()
