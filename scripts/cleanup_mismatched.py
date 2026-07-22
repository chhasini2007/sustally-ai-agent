import os
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
except Exception:
    pass
from pathlib import Path
import json
import sqlite3
import xml.etree.ElementTree as ET

# Insert project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from src.retrieval.company_router import CompanyRouter

def detect_metadata_from_xml_robust(file_path: Path) -> str:
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML structure for {file_path.name}: {e}")
        return ""

    company_raw = None
    company_tags = {"company", "company_name", "companyname", "organization", "organisation", "name", "nameofthecompany", "nameofthelistedentity", "nameoflistedentity", "nameoftheentity"}

    for node in root.iter():
        tag_name = node.tag.split("}")[-1].lower()
        if tag_name in company_tags:
            if node.text and node.text.strip():
                company_raw = node.text.strip()
                break
    return company_raw or ""

def main():
    print("Starting database audit for mismatched company file attributions...")
    raw_dir = Path(settings.RAW_DIR)
    index_path = Path(settings.DOC_INDEX_PATH)
    company_router = CompanyRouter()

    # Load document index
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            document_index = json.load(f)
    else:
        document_index = {}

    db_path = settings.METRICS_DB_PATH
    print(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    mismatch_count = 0
    deleted_files_count = 0
    deleted_db_rows = 0

    # Scan properly filed reports
    for company_path in raw_dir.iterdir():
        if company_path.is_dir() and company_path.name != "_unsorted":
            company_folder_name = company_path.name
            
            # Resolve canonical company folder name
            resolved_folder_comps, _ = company_router.resolve_companies_and_years(company_folder_name)
            canonical_folder_name = resolved_folder_comps[0] if resolved_folder_comps else company_folder_name
            
            for year_path in company_path.iterdir():
                if year_path.is_dir():
                    year = year_path.name
                    for f in list(year_path.iterdir()):
                        if f.is_file() and f.suffix.lower() == ".xml":
                            # Parse internal company name
                            internal_company_raw = detect_metadata_from_xml_robust(f)
                            if not internal_company_raw:
                                print(f"Warning: No company tag found in {f.name}")
                                continue
                                
                            # Resolve canonical internal company name
                            resolved_internal_comps, _ = company_router.resolve_companies_and_years(internal_company_raw)
                            canonical_internal_name = resolved_internal_comps[0] if resolved_internal_comps else internal_company_raw
                            
                            # Verify if mismatch
                            if canonical_folder_name != canonical_internal_name:
                                mismatch_count += 1
                                print(f"MISMATCH FOUND for file '{f.name}':")
                                print(f"  - Located in folder: '{company_folder_name}'")
                                print(f"  - Declares company internally: '{internal_company_raw}' (Canonical: '{canonical_internal_name}')")
                                
                                # 1. Delete physical file
                                try:
                                    f.unlink()
                                    print(f"  -> Deleted physical file: {f}")
                                    deleted_files_count += 1
                                except Exception as e:
                                    print(f"  -> Error deleting physical file {f}: {e}")
                                    
                                # 2. Delete entries in document index
                                abs_path_key = str(f.resolve())
                                if abs_path_key in document_index:
                                    del document_index[abs_path_key]
                                    print(f"  -> Removed entry from document_index.json")
                                # Also check for keys with relative/different separators
                                for key in list(document_index.keys()):
                                    if f.name in key and company_folder_name in key:
                                        del document_index[key]
                                        print(f"  -> Removed duplicate key from document_index.json: {key}")

                                # 3. Delete database rows from metrics table
                                try:
                                    cursor.execute(
                                        "DELETE FROM metrics WHERE source_file = ? AND company = ?",
                                        (f.name, company_folder_name)
                                    )
                                    rows_deleted = cursor.rowcount
                                    deleted_db_rows += rows_deleted
                                    print(f"  -> Deleted {rows_deleted} rows from metrics table for company '{company_folder_name}'")
                                except Exception as e:
                                    print(f"  -> Error deleting database rows: {e}")

    # 4. Database-first pass: Delete database rows that have no matching physical file on disk
    print("\nRunning database-first pass for orphaned metrics rows...")
    cursor.execute("SELECT DISTINCT company, year, source_file FROM metrics")
    db_rows = cursor.fetchall()
    deleted_orphaned_db_rows = 0
    
    for comp, yr, src in db_rows:
        if not src:
            continue
        expected_path = raw_dir / comp / str(yr) / src
        if not expected_path.exists():
            found = False
            for c_dir in raw_dir.iterdir():
                if c_dir.is_dir() and c_dir.name.lower() == comp.lower():
                    for y_dir in c_dir.iterdir():
                        if y_dir.is_dir() and y_dir.name == str(yr):
                            if (y_dir / src).exists():
                                found = True
                                break
            if not found:
                try:
                    cursor.execute(
                        "DELETE FROM metrics WHERE company = ? AND year = ? AND source_file = ?",
                        (comp, yr, src)
                    )
                    deleted_orphaned_db_rows += cursor.rowcount
                except Exception as e:
                    print(f"Error deleting orphaned row for {comp} ({yr}) - {src}: {e}")
                    
    print(f"Total orphaned database rows deleted: {deleted_orphaned_db_rows}")

    # Save document index
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(document_index, f, indent=2)
    print("Saved updated document_index.json.")

    conn.commit()
    conn.close()

    print("\n=== AUDIT AND CLEANUP SUMMARY ===")
    print(f"Total mismatched company files found: {mismatch_count}")
    print(f"Total physical files deleted: {deleted_files_count}")
    print(f"Total mismatched folder database rows deleted: {deleted_db_rows}")
    print(f"Total orphaned database rows deleted: {deleted_orphaned_db_rows}")

if __name__ == "__main__":
    main()
