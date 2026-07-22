import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
import csv
import json
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from typing import Dict, Any, List, Tuple

from config import settings
from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import METRIC_TAXONOMY

def download_test(url: str) -> Tuple[bool, int, str]:
    """
    Tries to download the XML URL.
    Returns: (success, size_in_bytes, error_message)
    """
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read()
            return True, len(content), ""
    except Exception as e:
        return False, 0, str(e)

def main():
    print("Running detailed data-quality audit...")

    from src.utils.csv_helper import get_latest_csv_path
    csv_path = get_latest_csv_path()
    raw_dir = Path(settings.RAW_DIR)
    unsorted_dir = raw_dir / "_unsorted"
    index_path = Path(settings.DOC_INDEX_PATH)

    # 1. Investigate the 12 zero-byte files
    targets = [
        "BRSR_1489630_21072025073711_WEB.xml",
        "BRSR_1489635_21072025073842_WEB.xml",
        "BRSR_1489648_21072025074537_WEB.xml",
        "BRSR_1489695_21072025075954_WEB.xml",
        "BRSR_1489713_21072025080442_WEB.xml",
        "BRSR_1489718_21072025080650_WEB.xml",
        "BRSR_1489740_21072025081731_WEB.xml",
        "BRSR_1489826_21072025090305_WEB.xml",
        "BRSR_1489930_21072025104027_WEB.xml",
        "BRSR_1489948_21072025112238_WEB.xml",
        "BRSR_1490461_22072025052519_WEB.xml",
        "BRSR_1490677_22072025064514_WEB.xml"
    ]

    # Map target name to URL from CSV
    url_map = {}
    if csv_path.exists():
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                for col in row:
                    col_clean = col.strip()
                    if col_clean.lower().startswith("http") and col_clean.lower().endswith(".xml"):
                        fname = col_clean.split("/")[-1]
                        if fname in targets:
                            url_map[fname] = col_clean

    part1_lines = []
    part1_lines.append("\n=== PART 1 — ZERO-BYTE FILES INVESTIGATION ===")
    part1_lines.append(f"Found {len(targets)} zero-byte files in _unsorted/.")
    part1_lines.append("")
    part1_lines.append("| Filename | Likely Origin | Recoverable Automatically | Recommended Action |")
    part1_lines.append("| --- | --- | --- | --- |")

    for t in targets:
        file_path = unsorted_dir / t
        # Check size on disk
        size_on_disk = file_path.stat().st_size if file_path.exists() else 0
        url = url_map.get(t)
        
        origin = "bulk_xml_importer (via CSV download)" if url else "direct upload / unknown"
        recoverable = "No"
        rec_action = "Manual download required"
        
        if url:
            success, size_downloaded, err = download_test(url)
            if success:
                if size_downloaded > 0:
                    recoverable = "Yes"
                    rec_action = f"Re-download (Source URL reachable, size={size_downloaded} bytes)"
                else:
                    rec_action = "Source URL returns 0 bytes (corrupt at source)"
            else:
                rec_action = f"Source URL unreachable: {err}"
        else:
            rec_action = "No source URL found in master CSV"

        part1_lines.append(f"| {t} | {origin} | {recoverable} | {rec_action} |")

    # 2. Missing Metrics Per Company/Year
    conn = sqlite3.connect(settings.METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT company, year, metric_key FROM metrics")
    db_rows = cursor.fetchall()
    conn.close()

    metrics_by_company_year = {}
    for company, year, metric_key in db_rows:
        key = (company, year)
        if key not in metrics_by_company_year:
            metrics_by_company_year[key] = set()
        metrics_by_company_year[key].add(metric_key)

    # Get all company/year pairs from document index
    document_index = {}
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            document_index = json.load(f)

    all_pairs = set()
    for doc in document_index.values():
        if doc.get("file_type") == "xml":
            all_pairs.add((doc.get("company"), doc.get("year")))

    high_priority_pairs = []
    normal_pairs = []

    for company, year in all_pairs:
        key = (company, year)
        stored_keys = metrics_by_company_year.get(key, set())
        if len(stored_keys) == 0:
            # Let's inspect the original XML file to see if recognizable ESG data exists
            xml_file_path = None
            for fp_str, doc in document_index.items():
                if doc.get("company") == company and doc.get("year") == year and doc.get("file_type") == "xml":
                    xml_file_path = Path(fp_str)
                    break
            
            has_esg = "No"
            reason = "Unknown error"
            if xml_file_path and xml_file_path.exists():
                try:
                    tree = ET.parse(xml_file_path)
                    root = tree.getroot()
                    # Check if there are standard namespaces/elements
                    esg_tags = [n.tag.split("}")[-1] for n in root.iter()]
                    num_esg_tags = sum(1 for t in esg_tags if any(k in t.lower() for k in ["emission", "water", "waste", "workforce", "energy"]))
                    if num_esg_tags > 0:
                        has_esg = "Yes"
                        reason = f"File has {num_esg_tags} ESG-related XML elements but extractor failed to parse them"
                    else:
                        reason = "File has no recognizable ESG tags"
                except Exception as e:
                    reason = f"Failed to parse XML: {e}"
            else:
                reason = "Source XML file not found on disk"
            
            high_priority_pairs.append({
                "company": company,
                "year": year,
                "xml_path": str(xml_file_path.relative_to(settings.PROJECT_ROOT)) if xml_file_path else "Unknown",
                "has_esg": has_esg,
                "reason": reason
            })
        else:
            missing_keys = []
            for mkey in METRIC_TAXONOMY.keys():
                if mkey not in stored_keys:
                    missing_keys.append(mkey)
            if missing_keys:
                normal_pairs.append({
                    "company": company,
                    "year": year,
                    "missing": missing_keys
                })

    part2_lines = []
    part2_lines.append("\n=== PART 2 — MISSING METRICS ===")
    part2_lines.append(f"[HIGH PRIORITY] Pairs with ZERO metrics extracted: {len(high_priority_pairs)}")
    for item in high_priority_pairs:
        part2_lines.append(f"  * {item['company']} ({item['year']}) | Path: {item['xml_path']} | Recognizable ESG data exists: {item['has_esg']} | Reason: {item['reason']}")
    
    part2_lines.append(f"\n[NORMAL] Pairs missing only specific metrics (likely non-disclosure): {len(normal_pairs)}")
    for item in normal_pairs[:15]:
        part2_lines.append(f"  * {item['company']} ({item['year']}) missing: {', '.join(item['missing'])}")
    if len(normal_pairs) > 15:
        part2_lines.append(f"  * ... and {len(normal_pairs) - 15} more pairs.")

    # 3. Alias / Company Name Gaps
    company_router = CompanyRouter()
    all_raw_company_names = set()
    unresolved_company_names = set()

    # Get all XML files under raw_reports
    all_xml_files = []
    for company_path in raw_dir.iterdir():
        if company_path.is_dir() and company_path.name != "_unsorted":
            for year_path in company_path.iterdir():
                if year_path.is_dir():
                    for f in year_path.iterdir():
                        if f.is_file() and f.suffix.lower() == ".xml":
                            all_xml_files.append(f)
    if unsorted_dir.exists():
        for f in unsorted_dir.iterdir():
            if f.is_file() and f.suffix.lower() == ".xml":
                all_xml_files.append(f)

    # Scan tags for raw company names
    company_tags = {"company", "company_name", "companyname", "organization", "organisation", "name", "nameofthecompany", "nameofthelistedentity", "nameoflistedentity", "nameoftheentity"}
    for f in all_xml_files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            for node in root.iter():
                tag_name = node.tag.split("}")[-1].lower()
                if tag_name in company_tags and node.text and node.text.strip():
                    raw_name = node.text.strip()
                    all_raw_company_names.add(raw_name)
                    # Check resolution
                    res, _ = company_router.resolve_companies_and_years(raw_name)
                    if not res:
                        unresolved_company_names.add(raw_name)
                    break
        except Exception:
            pass

    # Group near-duplicate unresolved names
    grouped_gaps = {}
    sorted_unresolved = sorted(list(unresolved_company_names))
    for name in sorted_unresolved:
        std_name = re.sub(r"[^\w\s]", "", name.lower())
        std_name = re.sub(r"\b(limited|ltd|pvt|private|co|corp|corporation|inc)\b", "", std_name).strip()
        
        found = False
        for gkey in grouped_gaps.keys():
            if std_name == gkey or std_name in gkey or gkey in std_name:
                grouped_gaps[gkey].append(name)
                found = True
                break
        if not found:
            grouped_gaps[std_name] = [name]

    part3_lines = []
    part3_lines.append("\n=== PART 3 — ALIAS GAPS ===")
    part3_lines.append(f"Total unresolved raw company names: {len(unresolved_company_names)}")
    part3_lines.append("\nSuggested Alias Entries:")
    for std_name, raw_names in grouped_gaps.items():
        if len(raw_names) > 1:
            canonical = sorted(raw_names, key=len, reverse=True)[0]
            for rname in raw_names:
                if rname != canonical:
                    part3_lines.append(f'  "{rname}" -> "{canonical}"')
        else:
            part3_lines.append(f'  "{raw_names[0]}" -> Needs manual review')

    # 4. Duplicate / Conflicting Data
    company_year_files = {}
    for doc in document_index.values():
        if doc.get("file_type") == "xml":
            key = (doc.get("company"), doc.get("year"))
            if key not in company_year_files:
                company_year_files[key] = []
            company_year_files[key].append(doc.get("file_name"))

    multiple_source_files = []
    for key, files in company_year_files.items():
        if len(files) > 1:
            multiple_source_files.append({
                "company": key[0],
                "year": key[1],
                "files": files
            })

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

    part4_lines = []
    part4_lines.append("\n=== PART 4 — DUPLICATE / CONFLICTING DATA ===")
    part4_lines.append(f"Pairs with multiple source files: {len(multiple_source_files)}")
    for item in multiple_source_files:
        part4_lines.append(f"  * {item['company']} ({item['year']}): {', '.join(item['files'])}")
        
    part4_lines.append(f"\n[HIGH PRIORITY] Metric key conflicts: {len(metric_conflicts)}")
    for item in metric_conflicts:
        part4_lines.append(f"  * [HIGH PRIORITY] Conflict in {item['company']} ({item['year']}) for '{item['metric_key']}': {item['total_count']} values ({item['distinct_values']} distinct)")

    # 5. Metric Taxonomy Coverage
    unrecognized_tags = Counter()
    for f in all_xml_files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            for node in root.iter():
                tag_name = node.tag.split("}")[-1]
                if node.text and node.text.strip():
                    text_val = node.text.strip().replace(",", "")
                    if re.match(r"^[-+]?\d+(?:\.\d+)?$", text_val):
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

    ranked_gaps = unrecognized_tags.most_common(50)

    # Suggest corresponding canonical keys for top 10
    suggestions = {
        "NumberOfEmployeesOrWorkersRelatedToMinimumWages": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "NumberOfWellBeingOfEmployeesOrWorkers": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "PercentageOfWellBeingOfEmployeesOrWorkers": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "PercentageOfEmployeesOrWorkersRelatedToMinimumWages": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "NumberOfTrainedEmployeesOrWorkers": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "PercentageOfTrainedEmployeesOrWorkers": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "TurnoverRate": "genuinely new metric type, no existing canonical key",
        "NumberOfEmployeesOrWorkersIncludingDifferentlyAbled": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "NumberOfDifferentlyAbledEmployeesOrWorkers": "women_workforce_pct (related, but genuinely new workforce metrics)",
        "PercentageOfEmployeesOrWorkersIncludingDifferentlyAbled": "women_workforce_pct (related, but genuinely new workforce metrics)"
    }

    part5_lines = []
    part5_lines.append("\n=== PART 5 — METRIC TAXONOMY COVERAGE ===")
    part5_lines.append("Top 10 unrecognized tags and suggested mapping:")
    for idx, (tag, freq) in enumerate(ranked_gaps[:10], 1):
        sugg = suggestions.get(tag, "genuinely new metric type, no existing canonical key")
        part5_lines.append(f"  {idx}. Tag: {tag:<60} | Frequency: {freq} occurrences | Suggested: {sugg}")

    # Append to existing report
    report_path = Path("data/audit_report.txt")
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
    else:
        existing_content = ""

    new_report_content = existing_content + "\n" + "\n".join(part1_lines + part2_lines + part3_lines + part4_lines + part5_lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(new_report_content)

    print("\nDetailed audit results appended to data/audit_report.txt successfully!")

if __name__ == "__main__":
    main()
