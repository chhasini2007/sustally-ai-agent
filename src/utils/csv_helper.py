import re
from pathlib import Path
from datetime import datetime

def get_latest_csv_path() -> Path:
    """
    Dynamically finds the newest CF-BRSR-equities-*.csv file in data/processed/
    by parsing the date from the filename (format: DD-MMM-YYYY).
    """
    csv_dir = Path("data/processed")
    if not csv_dir.exists():
        return Path("data/processed/CF-BRSR-equities-13-Jun-2026.csv")
        
    csv_files = list(csv_dir.glob("CF-BRSR-equities-*.csv"))
    if not csv_files:
        return Path("data/processed/CF-BRSR-equities-13-Jun-2026.csv")
        
    def get_date(path: Path) -> datetime:
        match = re.search(r'CF-BRSR-equities-(\d{1,2}-[A-Za-z]{3}-\d{4})\.csv', path.name)
        if match:
            try:
                # e.g., 14-Jul-2026 -> 14 Jul 2026
                return datetime.strptime(match.group(1), "%d-%b-%Y")
            except Exception:
                pass
        return datetime.min

    return max(csv_files, key=get_date)
