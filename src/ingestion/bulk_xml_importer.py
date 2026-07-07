import os
import re
import shutil
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any

from config import settings
from src.retrieval.company_router import CompanyRouter
from src.ingestion.document_manager import DocumentManager

def detect_metadata_from_xml(file_path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parses XML file to detect company and year from the structured content.
    Returns: (resolved_company, resolved_year, error_reason)
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        return None, None, f"Failed to parse XML: {str(e)}"

    company_raw = None
    year_raw = None

    # Tag names we look for (case-insensitive)
    company_tags = {"company", "company_name", "companyname", "organization", "organisation", "name"}
    year_tags = {"year", "reporting_year", "reportingyear", "fiscal_year", "fiscalyear", "reporting_period", "reportingperiod", "period"}

    for node in root.iter():
        # Remove namespace prefix if any (e.g. {http://example.com}company -> company)
        tag_name = node.tag.split("}")[-1].lower()
        if not company_raw and tag_name in company_tags:
            if node.text and node.text.strip():
                company_raw = node.text.strip()
        if not year_raw and tag_name in year_tags:
            if node.text and node.text.strip():
                year_raw = node.text.strip()

    if not company_raw and not year_raw:
        return None, None, "missing company tag / missing year tag"
    if not company_raw:
        return None, None, "missing company tag"
    if not year_raw:
        return None, None, "missing year tag"

    # Resolve company name
    company_router = CompanyRouter()
    resolved_companies, _ = company_router.resolve_companies_and_years(company_raw)

    if not resolved_companies:
        return None, None, f"ambiguous (company name '{company_raw}' not recognized by router)"
    if len(resolved_companies) > 1:
        return None, None, f"ambiguous (multiple matches for '{company_raw}': {resolved_companies})"
    
    company = resolved_companies[0]

    # Resolve year
    year_matches = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", year_raw)
    if not year_matches:
        return None, None, f"missing year tag (invalid year format: '{year_raw}')"
    if len(set(year_matches)) > 1:
        return None, None, f"ambiguous (multiple years found: {year_matches})"

    year = year_matches[0]

    return company, year, None

def get_unique_filename(directory: Path, original_filename: str) -> Path:
    """
    Returns a unique file path in the directory, appending _2, _3 etc. if there is a conflict.
    """
    name_part, ext_part = os.path.splitext(original_filename)
    target_path = directory / original_filename
    suffix = 2
    while target_path.exists():
        target_path = directory / f"{name_part}_{suffix}{ext_part}"
        suffix += 1
    return target_path

def import_xml_folder(source_folder: str, recursive: bool = False):
    """
    Iterate over every *.xml file in source_folder.
    Detect company + year, place them into data/raw_reports/{Company}/{Year}/ or data/raw_reports/_unsorted/.
    Ingest successfully placed new files.
    """
    source_path = Path(source_folder)
    if not source_path.exists() or not source_path.is_dir():
        print(f"Error: Source folder '{source_folder}' does not exist or is not a directory.")
        return

    # Find all XML files
    pattern = "**/*.xml" if recursive else "*.xml"
    xml_files = []
    # Case-insensitive glob search for xml
    for file in source_path.glob(pattern):
        if file.is_file():
            xml_files.append(file)
    for file in source_path.glob(pattern.upper() if recursive else "*.XML"):
        if file.is_file() and file not in xml_files:
            xml_files.append(file)

    total_found = len(xml_files)
    success_count = 0
    unsorted_count = 0
    skipped_count = 0

    document_manager = DocumentManager()
    document_manager.load_index()

    newly_placed_files = []

    for file_path in xml_files:
        company, year, error_reason = detect_metadata_from_xml(file_path)

        if error_reason:
            # Move to unsorted directory
            unsorted_dir = Path(settings.RAW_DIR) / "_unsorted"
            unsorted_dir.mkdir(parents=True, exist_ok=True)
            target_path = get_unique_filename(unsorted_dir, file_path.name)
            
            try:
                shutil.move(str(file_path), str(target_path))
                print(f"[UNSORTED] Moved '{file_path.name}' to '{target_path}' due to: {error_reason}")
            except Exception as e:
                print(f"Error moving file '{file_path.name}' to unsorted: {e}")
                
            unsorted_count += 1
            continue

        # File has valid metadata. Compute hash to check if already indexed
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                buf = f.read(65536)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(65536)
            file_hash = hasher.hexdigest()
        except Exception as e:
            print(f"Error reading file '{file_path.name}' for hashing: {e}")
            continue

        # Check if hash already indexed anywhere
        is_indexed = False
        for path, val in document_manager.index.items():
            if val.get("file_hash") == file_hash:
                is_indexed = True
                break

        if is_indexed:
            print(f"[SKIPPED] File '{file_path.name}' already indexed (matching hash).")
            skipped_count += 1
            continue

        # Place the file: copy it
        target_dir = Path(settings.RAW_DIR) / company / year
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = get_unique_filename(target_dir, file_path.name)

        try:
            shutil.copy(str(file_path), str(target_path))
            newly_placed_files.append(str(target_path))
            success_count += 1
        except Exception as e:
            print(f"Error copying file '{file_path.name}' to raw reports: {e}")

    # Call the existing ingestion path on newly placed files
    if newly_placed_files:
        print(f"Ingesting {len(newly_placed_files)} new reports...")
        document_manager.load_index() # reload index
        document_manager.ingest_new_reports(target_files=newly_placed_files)

    # Print summary as required
    print("XML files found:", total_found)
    print("Successfully placed & ingested:", success_count)
    print("Unsorted (company/year unclear):", unsorted_count)
    print("Skipped (already indexed, same hash):", skipped_count)
