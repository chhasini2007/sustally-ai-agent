import os
import sys
# Insert project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import urllib.request
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.csv_helper import get_latest_csv_path
from src.retrieval.company_router import CompanyRouter

def download_file(url, dest_path):
    try:
        # User-agent header to avoid getting blocked
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        return True, url, dest_path, None
    except Exception as e:
        return False, url, dest_path, str(e)

def main():
    parser = argparse.ArgumentParser(description="Download reports from the latest master CSV file")
    parser.add_argument("--xml-only", action="store_true", help="Only download XML reports")
    parser.add_argument("--pdf-only", action="store_true", help="Only download PDF reports")
    args = parser.parse_args()

    csv_path = get_latest_csv_path()
    dest_dir = Path("data/raw_reports")
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading CSV from: {csv_path}")
    company_router = CompanyRouter()
    
    download_tasks = []
    
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        
        for idx, row in enumerate(reader):
            # Skip the multiline header (first 8 rows)
            if idx < 8:
                continue
            
            if len(row) < 5:
                continue
                
            company_raw = row[0].strip()
            from_year = row[1].strip()
            to_year = row[2].strip()
            pdf_url = row[3].strip()
            xml_url = row[4].strip()
            
            if not company_raw or not to_year:
                continue
                
            # Resolve canonical company name
            resolved_companies, _ = company_router.resolve_companies_and_years(company_raw)
            company_folder = resolved_companies[0] if resolved_companies else company_raw
            
            # Sanitize company folder name for Windows filesystems
            company_folder = "".join([c for c in company_folder if c not in '<>:\"/\\|?*']).strip()
            
            target_dir = dest_dir / company_folder / to_year
            
            # Add PDF task
            if not args.xml_only and pdf_url and pdf_url.lower().startswith("http"):
                pdf_filename = "report.pdf"
                pdf_path = target_dir / pdf_filename
                # Check if any report.pdf or report_*.pdf exists
                pdf_exists = False
                if target_dir.exists():
                    for f_item in target_dir.iterdir():
                        if f_item.is_file() and f_item.name.startswith("report") and f_item.name.endswith(".pdf"):
                            if f_item.stat().st_size > 0:
                                pdf_exists = True
                                break
                if not pdf_exists:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    download_tasks.append((pdf_url, target_dir / "report.pdf"))
            
            # Add XML task
            if not args.pdf_only and xml_url and xml_url.lower().startswith("http"):
                xml_filename = "report.xml"
                xml_path = target_dir / xml_filename
                xml_exists = False
                if target_dir.exists():
                    for f_item in target_dir.iterdir():
                        if f_item.is_file() and f_item.name.startswith("report") and f_item.name.endswith(".xml"):
                            if f_item.stat().st_size > 0:
                                xml_exists = True
                                break
                if not xml_exists:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    download_tasks.append((xml_url, target_dir / "report.xml"))

    total_tasks = len(download_tasks)
    print(f"Found {total_tasks} new report files to download.")

    if total_tasks == 0:
        print("No new files to download.")
        return

    success_count = 0
    failure_count = 0

    print("Starting downloads in parallel...")
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(download_file, url, dest_path): (url, dest_path) for url, dest_path in download_tasks}
        
        for idx, future in enumerate(as_completed(futures), 1):
            success, url, dest_path, err = future.result()
            if success:
                success_count += 1
            else:
                failure_count += 1
                print(f"[{idx}/{total_tasks}] Failed to download {url} to {dest_path}: {err}")
            
            if idx % 100 == 0 or idx == total_tasks:
                print(f"Progress: {idx}/{total_tasks} completed. (Success: {success_count}, Failed: {failure_count})")

    print(f"\nDownload completed!")
    print(f"Successfully downloaded: {success_count}")
    print(f"Failed: {failure_count}")

if __name__ == "__main__":
    main()
