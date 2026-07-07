import os
import sys
import shutil
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.bulk_xml_importer import import_xml_folder
from src.database.metrics_store import MetricsStore
from src.ingestion.document_manager import DocumentManager
from config import settings

INDEX_BACKUP_PATH = "document_index_backup.json"

def setup_environment():
    # Backup index
    if os.path.exists(settings.DOC_INDEX_PATH):
        shutil.copy(settings.DOC_INDEX_PATH, INDEX_BACKUP_PATH)
        os.remove(settings.DOC_INDEX_PATH)
        
    # Clean up directories
    clean_dirs()
    
    # Remove database entries for the test companies
    store = MetricsStore()
    store.clear_company_metrics("Tata Consultancy Services Limited", "2024")
    store.clear_company_metrics("Infosys Limited", "2025")

def restore_environment():
    # Restore index
    if os.path.exists(INDEX_BACKUP_PATH):
        shutil.copy(INDEX_BACKUP_PATH, settings.DOC_INDEX_PATH)
        os.remove(INDEX_BACKUP_PATH)
    elif os.path.exists(settings.DOC_INDEX_PATH):
        os.remove(settings.DOC_INDEX_PATH)
        
    # Clean up directories
    clean_dirs()

def clean_dirs():
    raw_dir = Path(settings.RAW_DIR)
    for company_dir in ["Tata Consultancy Services Limited", "Infosys Limited", "_unsorted"]:
        p = raw_dir / company_dir
        if p.exists():
            shutil.rmtree(p)

def run_tests():
    print("=== Setup Test Environment ===")
    setup_environment()
    
    # Create temp source directory
    temp_src = Path("temp_xml_source")
    if temp_src.exists():
        shutil.rmtree(temp_src)
    temp_src.mkdir()
    
    # Create sub-directory for recursive test
    sub_dir = temp_src / "sub_folder"
    sub_dir.mkdir()

    # 1. Create a valid XML file for TCS in 2024
    tcs_xml_content = """<report>
    <company>TCS</company>
    <year>2024</year>
    <scope1_emissions_tco2e unit="tCO2e">15200</scope1_emissions_tco2e>
</report>"""
    tcs_path = temp_src / "tcs_report.xml"
    with open(tcs_path, "w") as f:
        f.write(tcs_xml_content)

    # 2. Create a valid XML file for Infosys in 2025 in the sub-folder
    infosys_xml_content = """<report>
    <company>Infosys Limited</company>
    <reporting_year>2025</reporting_year>
    <scope2_emissions_tco2e unit="tCO2e">8420</scope2_emissions_tco2e>
</report>"""
    infosys_path = sub_dir / "infosys_report.xml"
    with open(infosys_path, "w") as f:
        f.write(infosys_xml_content)

    # 3. Create an invalid XML file (missing company tag)
    missing_company_content = """<report>
    <year>2024</year>
</report>"""
    missing_company_path = temp_src / "missing_company.xml"
    with open(missing_company_path, "w") as f:
        f.write(missing_company_content)

    # 4. Create an invalid XML file (missing year tag)
    missing_year_content = """<report>
    <company>TCS</company>
</report>"""
    missing_year_path = temp_src / "missing_year.xml"
    with open(missing_year_path, "w") as f:
        f.write(missing_year_content)

    # 5. Create an invalid XML file (ambiguous company name)
    ambiguous_company_content = """<report>
    <company>NonExistentCorp</company>
    <year>2024</year>
</report>"""
    ambiguous_path = temp_src / "ambiguous_company.xml"
    with open(ambiguous_path, "w") as f:
        f.write(ambiguous_company_content)

    try:
        print("=== Running Bulk XML Import Command (Non-Recursive) ===")
        import_xml_folder(str(temp_src), recursive=False)

        print("\n=== Verifying Non-Recursive Import ===")
        tcs_placed_dir = Path(settings.RAW_DIR) / "Tata Consultancy Services Limited" / "2024"
        assert tcs_placed_dir.exists(), "TCS raw folder should exist"
        assert (tcs_placed_dir / "tcs_report.xml").exists(), "TCS report should have been copied"

        infosys_placed_dir = Path(settings.RAW_DIR) / "Infosys Limited" / "2025"
        assert not infosys_placed_dir.exists(), "Infosys folder should NOT exist under non-recursive run"

        unsorted_dir = Path(settings.RAW_DIR) / "_unsorted"
        assert unsorted_dir.exists(), "_unsorted directory should exist"
        
        assert not missing_company_path.exists(), "missing_company.xml should be moved from source"
        assert not missing_year_path.exists(), "missing_year.xml should be moved from source"
        assert not ambiguous_path.exists(), "ambiguous_company.xml should be moved from source"

        assert (unsorted_dir / "missing_company.xml").exists()
        assert (unsorted_dir / "missing_year.xml").exists()
        assert (unsorted_dir / "ambiguous_company.xml").exists()

        # Check database ingestion for TCS
        store = MetricsStore()
        tcs_emissions = store.get_metric("Tata Consultancy Services Limited", "2024", "scope1_emissions_tco2e")
        assert len(tcs_emissions) > 0, "Should have ingested TCS 2024 Scope 1 emissions"
        assert tcs_emissions[0]["value"] == 15200.0, "Value should match XML content"

        print("\n=== Running Bulk XML Import Command (Recursive with duplicates) ===")
        # Now run recursively. This should pick up the Infosys report in the sub-folder.
        # It should skip tcs_report because it's already indexed (matching hash).
        
        # First, let's create a new file in temp_src that is a duplicate of tcs_report.xml to check same hash skipping
        dup_path = temp_src / "tcs_report_dup.xml"
        with open(dup_path, "w") as f:
            f.write(tcs_xml_content)

        import_xml_folder(str(temp_src), recursive=True)

        print("\n=== Verifying Recursive Import ===")
        assert infosys_placed_dir.exists(), "Infosys raw folder should now exist"
        assert (infosys_placed_dir / "infosys_report.xml").exists(), "Infosys report should have been copied"

        # Verify duplicate is skipped (i.e. not copied/placed in raw_reports)
        assert not (tcs_placed_dir / "tcs_report_dup.xml").exists(), "Duplicate file should not be copied to raw reports"

        # Check database ingestion for Infosys
        infosys_emissions = store.get_metric("Infosys Limited", "2025", "scope2_emissions_tco2e")
        assert len(infosys_emissions) > 0, "Should have ingested Infosys 2025 Scope 2 emissions"
        assert infosys_emissions[0]["value"] == 8420.0, "Value should match XML content"

        print("\nALL BULK XML IMPORTER TESTS PASSED SUCCESSFULLY!")

    finally:
        print("\n=== Cleanup Test Environment ===")
        if temp_src.exists():
            shutil.rmtree(temp_src)
        restore_environment()

if __name__ == "__main__":
    run_tests()
