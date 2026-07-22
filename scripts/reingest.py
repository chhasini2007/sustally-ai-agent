import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.document_manager import DocumentManager

def reingest():
    index_path = "data/document_index.json"
    
    # 1. Load index
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            index = json.load(f)
    else:
        index = {}
        
    # 2. Files to reingest
    files_to_reingest = [
        "data/raw_reports/Infosys Limited/2025/BRSR_1477079_03072025095250_WEB_3.xml",
        "data/raw_reports/Tata Consultancy Services Limited/2025/BRSR_1474736_30062025044052_WEB_2.xml",
        "data/raw_reports/Infosys Limited/2026/BRSR_500209_1062026191217_BRSR_WebXMLFile_20260610_191246055.xml",
        "data/raw_reports/Tata Consultancy Services Limited/2026/BRSR_532540_155202623553_BRSR_WebXMLFile_20260602_163936876.xml",
        "data/raw_reports/Tata Consultancy Services Limited/2024/tcs_report_2.xml"
    ]
    
    # Make absolute paths
    files_to_reingest = [os.path.abspath(f) for f in files_to_reingest]
    
    # Remove from index
    removed_count = 0
    for f in files_to_reingest:
        for key in list(index.keys()):
            if os.path.abspath(key) == f:
                del index[key]
                removed_count += 1
                
    # Save back index
    with open(index_path, "w") as f:
        json.dump(index, f, indent=4)
        
    print(f"Removed {removed_count} keys from document_index.json.")
    
    # 3. Call document manager to ingest them
    dm = DocumentManager()
    result = dm.ingest_new_reports(target_files=files_to_reingest)
    print("Ingestion result:", result)

if __name__ == "__main__":
    reingest()
