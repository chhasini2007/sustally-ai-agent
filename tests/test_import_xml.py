import os
import sys
import shutil
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.xml_importer import import_xml_reports
from src.database.metrics_store import MetricsStore
from src.database.chroma_store import ChromaStore
from config import settings

INDEX_BACKUP_PATH = "document_index_backup_xml.json"

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
            
    incoming_dir = Path(settings.INCOMING_XML_DIR)
    if incoming_dir.exists():
        for file in incoming_dir.iterdir():
            if file.is_file():
                os.remove(file)

def run_tests():
    print("=== Setup Test Environment ===")
    setup_environment()
    
    incoming_dir = Path(settings.INCOMING_XML_DIR)
    incoming_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create a valid XML file for TCS in 2024
    tcs_xml_content = """<report>
    <company>TCS</company>
    <year>2024</year>
    <scope1_emissions_tco2e unit="tCO2e">15200</scope1_emissions_tco2e>
</report>"""
    tcs_path = incoming_dir / "tcs_report.xml"
    with open(tcs_path, "w") as f:
        f.write(tcs_xml_content)

    # 2. Create an invalid XML file (malformed structure)
    invalid_xml_content = """<report>
    <company>TCS</company>
    <year>2024</year>
    <scope1_emissions_tco2e unit="tCO2e">15200
</report>"""
    invalid_path = incoming_dir / "malformed_report.xml"
    with open(invalid_path, "w") as f:
        f.write(invalid_xml_content)

    # 3. Create an XML file with missing company metadata
    missing_company_content = """<report>
    <year>2024</year>
</report>"""
    missing_company_path = incoming_dir / "missing_company.xml"
    with open(missing_company_path, "w") as f:
        f.write(missing_company_content)

    try:
        print("=== Running import_xml_reports ===")
        stats = import_xml_reports()

        print("\n=== Verifying Import Statistics ===")
        print(stats)
        assert stats["scanned"] == 3, f"Expected 3 files, got {stats['scanned']}"
        assert stats["success"] == 1, f"Expected 1 success, got {stats['success']}"
        assert stats["failed"] == 1, f"Expected 1 failed (malformed), got {stats['failed']}"
        assert stats["unsorted"] == 1, f"Expected 1 unsorted, got {stats['unsorted']}"

        print("\n=== Verifying File Locations ===")
        # TCS report should be moved to raw reports
        tcs_placed_dir = Path(settings.RAW_DIR) / "Tata Consultancy Services Limited" / "2024"
        assert tcs_placed_dir.exists(), "TCS raw folder should exist"
        assert (tcs_placed_dir / "tcs_report.xml").exists(), "TCS report should have been moved/copied"
        
        # Source file should be deleted on success
        assert not tcs_path.exists(), "Source TCS file should be deleted after successful import"

        # Malformed and missing company reports should be moved to _unsorted
        unsorted_dir = Path(settings.RAW_DIR) / "_unsorted"
        assert unsorted_dir.exists(), "_unsorted directory should exist"
        assert (unsorted_dir / "malformed_report.xml").exists(), "malformed_report should be moved to _unsorted"
        assert (unsorted_dir / "missing_company.xml").exists(), "missing_company should be moved to _unsorted"

        # Check database ingestion for TCS
        store = MetricsStore()
        tcs_emissions = store.get_metric("Tata Consultancy Services Limited", "2024", "scope1_emissions_tco2e")
        assert len(tcs_emissions) > 0, "Should have ingested TCS 2024 Scope 1 emissions"
        assert tcs_emissions[0]["value"] == 15200.0, "Value should match XML content"

        # Check ChromaDB metadata structure
        chroma_store = ChromaStore()
        # Query chunks for TCS 2024
        chunks = chroma_store.collection.get(
            where={"$and": [{"company": {"$eq": "Tata Consultancy Services Limited"}}, {"year": {"$eq": "2024"}}]}
        )
        
        assert len(chunks["ids"]) > 0, "Expected chunks to be in ChromaDB"
        for metadata in chunks["metadatas"]:
            assert metadata.get("file_name") == "tcs_report.xml", "Expected file_name in metadata"
            assert metadata.get("file_type") == "xml", "Expected file_type in metadata"
            assert metadata.get("xml_path") is not None, "Expected xml_path in metadata"
            assert metadata.get("source") == "tcs_report.xml", "Expected source in metadata"

        # 4. Check already indexed skipping
        # Put another copy in incoming_dir
        with open(tcs_path, "w") as f:
            f.write(tcs_xml_content)

        print("\n=== Running import_xml_reports again to verify skipping ===")
        stats_dup = import_xml_reports()
        assert stats_dup["indexed"] == 1, f"Expected 1 already indexed, got {stats_dup['indexed']}"
        assert tcs_path.exists(), "Source file should NOT be deleted if already indexed/skipped"

        print("\nALL --import-xml TESTS PASSED SUCCESSFULLY!")

    finally:
        print("\n=== Cleanup Test Environment ===")
        restore_environment()

if __name__ == "__main__":
    run_tests()
