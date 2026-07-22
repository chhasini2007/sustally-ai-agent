import csv
from collections import Counter

def check_years():
    from src.utils.csv_helper import get_latest_csv_path
    csv_path = get_latest_csv_path()
    years = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if idx < 8:
                continue
            if len(row) > 2:
                years.append(row[2].strip()) # TO YEAR
    print("Distribution of TO YEAR in CSV:")
    print(Counter(years))

if __name__ == "__main__":
    check_years()
