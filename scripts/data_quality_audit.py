import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
import csv
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from typing import Dict, Any, List, Tuple

from config import settings
from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import METRIC_TAXONOMY

def get_xml_file_hash(file_path: Path) -> str:
    import hashlib
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def detect_metadata_from_xml_robust(file_path: Path) -> Tuple[str, str, str]:
    """
    Robustly parses company and year from XML.
    Returns: (company_raw, year_raw, error_reason)
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        return "", "", f"Failed to parse XML structure: {str(e)}"

    company_raw = None
    year_raw = None

    company_tags = {"company", "company_name", "companyname", "organization", "organisation", "name", "nameofthecompany", "nameofthelistedentity", "nameoflistedentity", "nameoftheentity"}
    year_tags = {"year", "reporting_year", "reportingyear", "fiscal_year", "fiscalyear", "reporting_period", "reportingperiod", "period", "enddate", "reportingperiod"}

    for node in root.iter():
        tag_name = node.tag.split("}")[-1].lower()
        if not company_raw and tag_name in company_tags:
            if node.text and node.text.strip():
                company_raw = node.text.strip()
        if not year_raw and tag_name in year_tags:
            if node.text and node.text.strip():
                year_raw = node.text.strip()

    # Try fallback to filename if missing
    company_router = CompanyRouter()
    company = company_raw
    year = year_raw
    company_err = None
    year_err = None

    if company:
        resolved_companies, _ = company_router.resolve_companies_and_years(company)
        if not resolved_companies:
            pass # We allow unregistered companies now
        elif len(resolved_companies) > 1:
            company_err = f"ambiguous company match for '{company}'"
        else:
            company = resolved_companies[0]
    else:
        company_err = "missing company tag"

    if year:
        year_matches = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", year)
        if not year_matches:
            year_err = f"invalid year format: '{year}'"
        elif len(set(year_matches)) > 1:
            year_err = f"ambiguous years found: {year_matches}"
        else:
            year = year_matches[0]
    else:
        year_err = "missing year tag"

    # Fallback to filename
    if not company or not year:
        filename = file_path.name
        fn_companies, fn_years = company_router.resolve_companies_and_years(filename)
        if not company and fn_companies and len(fn_companies) == 1:
            company = fn_companies[0]
            company_err = None
        if not year and fn_years:
            year = fn_years[0]
            year_err = None

    errs = []
    if company_err:
        errs.append(company_err)
    if year_err:
        errs.append(year_err)

    return company or company_raw or "", year or year_raw or "", " / ".join(errs) if errs else ""

def main():
    print("Starting Sustally Data Quality Audit...")

    raw_dir = Path(settings.RAW_DIR)
    unsorted_dir = raw_dir / "_unsorted"
    index_path = Path(settings.DOC_INDEX_PATH)

    # Load document index
    document_index = {}
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            document_index = json.load(f)

    # 1. Scan Unsorted and Misfiled
    unsorted_files_report = []
    if unsorted_dir.exists():
        for f in unsorted_dir.iterdir():
            if f.is_file() and f.suffix.lower() == ".xml":
                company_raw, year_raw, error_reason = detect_metadata_from_xml_robust(f)
                unsorted_files_report.append({
                    "filename": f.name,
                    "company_raw": company_raw,
                    "year_raw": year_raw,
                    "reason": error_reason or "unknown"
                })

    misfiled_files_report = []
    all_valid_reports = []
    total_xml_count = 0

    # Scan properly filed reports
    for company_path in raw_dir.iterdir():
        if company_path.is_dir() and company_path.name != "_unsorted":
            for year_path in company_path.iterdir():
                if year_path.is_dir():
                    for f in year_path.iterdir():
                        if f.is_file() and f.suffix.lower() == ".xml":
                            total_xml_count += 1
                            all_valid_reports.append(f)
                            company_detected, year_detected, error_reason = detect_metadata_from_xml_robust(f)
                            # Check for mismatch with physical path
                            if company_detected != company_path.name or year_detected != year_path.name:
                                misfiled_files_report.append({
                                    "filename": f.name,
                                    "physical_path": str(f.relative_to(settings.PROJECT_ROOT)),
                                    "expected_path": f"data/raw_reports/{company_detected}/{year_detected}/",
                                    "company_detected": company_detected,
                                    "year_detected": year_detected
                                })

    # Total reports scanned
    total_reports_scanned = len(unsorted_files_report) + total_xml_count

    # 2. Query metrics.db for missing metrics
    conn = sqlite3.connect(settings.METRICS_DB_PATH)
    cursor = conn.cursor()
    
    # Retrieve all metrics
    cursor.execute("SELECT company, year, metric_key, source_file, value FROM metrics")
    db_rows = cursor.fetchall()
    conn.close()

    # Group metrics by company and year
    metrics_by_company_year = {}
    for company, year, metric_key, source_file, val in db_rows:
        key = (company, year)
        if key not in metrics_by_company_year:
            metrics_by_company_year[key] = []
        metrics_by_company_year[key].append({
            "metric_key": metric_key,
            "source_file": source_file,
            "value": val
        })

    # High Priority: Pairs with ZERO extracted metrics
    zero_metric_pairs = []
    missing_metrics_pairs = []

    # Get all company/year pairs from index or database
    all_pairs = set()
    for doc in document_index.values():
        if doc.get("file_type") == "xml":
            all_pairs.add((doc.get("company"), doc.get("year")))

    for company, year in all_pairs:
        key = (company, year)
        stored = metrics_by_company_year.get(key, [])
        if not stored:
            zero_metric_pairs.append((company, year))
        else:
            # Find missing metric keys
            stored_keys = {m["metric_key"] for m in stored}
            missing_keys = []
            for mkey in METRIC_TAXONOMY.keys():
                if mkey not in stored_keys:
                    missing_keys.append(mkey)
            if missing_keys:
                missing_metrics_pairs.append({
                    "company": company,
                    "year": year,
                    "missing": missing_keys
                })

    # 3. Alias gaps
    raw_company_names = set()
    unresolved_company_names = set()
    company_router = CompanyRouter()

    # Scan raw names from all files
    all_files = list(unsorted_dir.glob("*.xml")) if unsorted_dir.exists() else []
    all_files.extend(all_valid_reports)

    for f in all_files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            company_tags = {"company", "company_name", "companyname", "organization", "organisation", "name", "nameofthecompany", "nameofthelistedentity", "nameoflistedentity", "nameoftheentity"}
            for node in root.iter():
                tag_name = node.tag.split("}")[-1].lower()
                if tag_name in company_tags and node.text and node.text.strip():
                    raw_name = node.text.strip()
                    raw_company_names.add(raw_name)
                    # Check resolution
                    res, _ = company_router.resolve_companies_and_years(raw_name)
                    if not res:
                        unresolved_company_names.add(raw_name)
                    break
        except Exception:
            pass

    # Group unresolved company names
    grouped_alias_gaps = {}
    sorted_unresolved = sorted(list(unresolved_company_names))
    for name in sorted_unresolved:
        # Standardize for grouping comparison
        std_name = re.sub(r"[^\w\s]", "", name.lower())
        std_name = re.sub(r"\b(?:limited|ltd|pvt|private|co|corp|corporation|inc)\b", "", std_name).strip()
        
        found_group = False
        for gkey in grouped_alias_gaps.keys():
            # If standard names are very similar, group them
            if std_name == gkey or std_name in gkey or gkey in std_name:
                grouped_alias_gaps[gkey].append(name)
                found_group = True
                break
        if not found_group:
            grouped_alias_gaps[std_name] = [name]

    # 4. Duplicate / Conflicting Data
    company_year_files = {}
    for doc in document_index.values():
        if doc.get("file_type") == "xml":
            key = (doc.get("company"), doc.get("year"))
            if key not in company_year_files:
                company_year_files[key] = []
            company_year_files[key].append(doc.get("file_name"))

    multiple_source_files_pairs = []
    for key, files in company_year_files.items():
        if len(files) > 1:
            multiple_source_files_pairs.append({
                "company": key[0],
                "year": key[1],
                "files": files
            })

    # Conflicting metrics
    metric_conflicts = []
    conn = sqlite3.connect(settings.METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT company, year, metric_key, COUNT(*), COUNT(DISTINCT value)
        FROM metrics
        GROUP BY company, year, metric_key
        HAVING COUNT(*) > 1
    """)
    conflicts_raw = cursor.fetchall()
    conn.close()

    for company, year, metric_key, total_count, distinct_vals in conflicts_raw:
        metric_conflicts.append({
            "company": company,
            "year": year,
            "metric_key": metric_key,
            "total_count": total_count,
            "distinct_values": distinct_vals
        })

    # 5. Taxonomy Gaps
    unrecognized_tags = Counter()
    
    # Pre-compile taxonomy keywords
    all_taxonomy_keywords = set()
    for info in METRIC_TAXONOMY.values():
        for syn in info["synonyms"]:
            all_taxonomy_keywords.update(syn.lower().split())

    for f in all_files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            for node in root.iter():
                tag_name = node.tag.split("}")[-1]
                # If tag text represents numeric value but tag is not in taxonomy
                if node.text and node.text.strip():
                    text_val = node.text.strip().replace(",", "")
                    if re.match(r"^[-+]?\d+(?:\.\d+)?$", text_val):
                        # Tag is numeric. Check if it matches any taxonomy synonyms
                        matched = False
                        tag_lower = tag_name.lower()
                        for key, info in METRIC_TAXONOMY.items():
                            if tag_lower == key.lower() or any(syn in tag_lower for syn in info["synonyms"]):
                                matched = True
                                break
                        if not matched:
                            unrecognized_tags[tag_name] += 1
        except Exception:
            pass

    # Rank taxonomy gaps
    ranked_taxonomy_gaps = unrecognized_tags.most_common(50)

    # 6. Generate single summary report
    report_lines = []
    report_lines.append("=== SUSTALLY DATA QUALITY AUDIT ===")
    report_lines.append(f"Total reports scanned: {total_reports_scanned}")
    report_lines.append("")

    report_lines.append("1. UNSORTED / MISFILED")
    report_lines.append(f"   - {len(unsorted_files_report)} files in _unsorted/")
    for item in unsorted_files_report[:15]:
        report_lines.append(f"     * {item['filename']} | Detected Company: {item['company_raw']} | Detected Year: {item['year_raw']} | Reason: {item['reason']}")
    if len(unsorted_files_report) > 15:
        report_lines.append(f"     * ... and {len(unsorted_files_report) - 15} more files.")
    
    report_lines.append(f"   - {len(misfiled_files_report)} files with folder/content mismatch")
    for item in misfiled_files_report:
        report_lines.append(f"     * {item['filename']} | Location: {item['physical_path']} | Expected: {item['expected_path']} (Detected: {item['company_detected']} / {item['year_detected']})")
    report_lines.append("")

    report_lines.append("2. MISSING METRICS")
    report_lines.append(f"   - {len(zero_metric_pairs)} company/year pairs with ZERO extracted metrics (HIGH PRIORITY)")
    for comp, yr in zero_metric_pairs:
        report_lines.append(f"     * [HIGH PRIORITY] {comp} ({yr}) has zero extracted metrics.")
        
    report_lines.append(f"   - {len(missing_metrics_pairs)} company/year pairs missing specific metrics (likely genuine non-disclosure)")
    for item in missing_metrics_pairs[:10]:
        report_lines.append(f"     * {item['company']} ({item['year']}) missing: {', '.join(item['missing'])}")
    if len(missing_metrics_pairs) > 10:
        report_lines.append(f"     * ... and {len(missing_metrics_pairs) - 10} more company/year pairs.")
    report_lines.append("")

    report_lines.append("3. ALIAS GAPS")
    report_lines.append(f"   - {len(unresolved_company_names)} unresolved raw company names")
    for std_name, raw_names in list(grouped_alias_gaps.items())[:20]:
        report_lines.append(f"     * Group [{std_name.upper()}]: {', '.join(raw_names)}")
    if len(grouped_alias_gaps) > 20:
        report_lines.append(f"     * ... and {len(grouped_alias_gaps) - 20} more groups.")
    report_lines.append("")

    report_lines.append("4. DUPLICATES/CONFLICTS")
    report_lines.append(f"   - {len(multiple_source_files_pairs)} company/year pairs with multiple source files")
    for item in multiple_source_files_pairs:
        report_lines.append(f"     * {item['company']} ({item['year']}): {', '.join(item['files'])}")
        
    report_lines.append(f"   - {len(metric_conflicts)} metric_key conflicts (should be zero)")
    for item in metric_conflicts:
        report_lines.append(f"     * Conflict in {item['company']} ({item['year']}) for '{item['metric_key']}': {item['total_count']} values ({item['distinct_values']} distinct)")
    report_lines.append("")

    report_lines.append("5. TAXONOMY GAPS")
    report_lines.append(f"   - {len(ranked_taxonomy_gaps)} unrecognized numeric tags/labels, ranked by frequency:")
    for tag, freq in ranked_taxonomy_gaps[:25]:
        report_lines.append(f"     * Tag: {tag:<60} | Frequency: {freq} occurrences")
    report_lines.append("")

    # Output report
    report_content = "\n".join(report_lines)
    print(report_content)
    
    # Write to file
    output_path = Path("data/audit_report.txt")
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(report_content)
    print(f"\nAudit report successfully written to: {output_path.resolve()}")

if __name__ == "__main__":
    main()
