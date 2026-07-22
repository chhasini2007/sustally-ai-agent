import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import shutil
import sqlite3
from pathlib import Path
from config import settings
from src.database.chroma_store import ChromaStore
from src.database.metrics_store import MetricsStore
from src.ingestion.document_manager import DocumentManager

def main():
    print("Fixing misfiled reports...")
    
    raw_dir = Path(settings.RAW_DIR)
    index_path = Path(settings.DOC_INDEX_PATH)
    
    # 1. Define the misfiled paths and target paths
    mismatches = [
        {
            "old_path": raw_dir / "Infosys" / "2024" / "report.xml",
            "new_dir": raw_dir / "Infosys Limited" / "2024",
            "new_path": raw_dir / "Infosys Limited" / "2024" / "report.xml",
            "old_company": "Infosys",
            "new_company": "Infosys Limited",
            "year": "2024"
        },
        {
            "old_path": raw_dir / "TCS" / "2024" / "report.xml",
            "new_dir": raw_dir / "Tata Consultancy Services Limited" / "2024",
            "new_path": raw_dir / "Tata Consultancy Services Limited" / "2024" / "report.xml",
            "old_company": "TCS",
            "new_company": "Tata Consultancy Services Limited",
            "year": "2024"
        }
    ]
    
    # Load index
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {}
        
    chroma_store = ChromaStore()
    metrics_store = MetricsStore()
    
    for item in mismatches:
        old_p = item["old_path"]
        new_p = item["new_path"]
        new_d = item["new_dir"]
        
        if old_p.exists():
            print(f"Moving {old_p.name} from {old_p.parent.name} to {new_d.parent.name}...")
            
            # Clear old records from ChromaDB and SQLite
            chroma_store.delete_company_year(item["old_company"], item["year"])
            chroma_store.delete_company_year(item["new_company"], item["year"])
            metrics_store.clear_company_metrics(item["old_company"], item["year"])
            metrics_store.clear_company_metrics(item["new_company"], item["year"])
            
            # Remove from document index
            old_p_str = str(old_p.resolve())
            if old_p_str in index:
                del index[old_p_str]
            # Also remove under normalized keys if any
            for k in list(index.keys()):
                if old_p.name in k and (item["old_company"] in k or "Infosys" in k or "TCS" in k) and item["year"] in k:
                    del index[k]
            
            # Physical move
            new_d.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_p), str(new_p))
            
            # Clean up old directory if empty
            old_year_dir = old_p.parent
            if old_year_dir.exists() and not list(old_year_dir.iterdir()):
                old_year_dir.rmdir()
            old_comp_dir = old_year_dir.parent
            if old_comp_dir.exists() and not list(old_comp_dir.iterdir()):
                old_comp_dir.rmdir()

    # Save index
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        
    # Re-run ingestion to pick up new files
    print("Re-running ingestion for moved files...")
    document_manager = DocumentManager()
    document_manager.load_index()
    res = document_manager.ingest_new_reports()
    print("Ingestion result:", res)
    
    print("Fix complete! Re-running data quality audit...")
    # Trigger audit report regeneration
    from scripts.data_quality_audit import main as run_audit
    run_audit()

if __name__ == "__main__":
    main()
