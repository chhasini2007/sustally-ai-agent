import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
import argparse
from src.ingestion.document_manager import DocumentManager
from src.retrieval.company_router import CompanyRouter

def main():
    parser = argparse.ArgumentParser(description="Sustally Sustainability Report Agent Command-line Interface")
    parser.add_argument("--ingest-new", action="store_true", help="Scan and incrementally ingest new/modified reports")
    parser.add_argument("--list-companies", action="store_true", help="List all registered companies in the database")
    parser.add_argument("--extract-links", type=str, help="Scan a master PDF for XML report links and download them")
    parser.add_argument("--check-llm", action="store_true", help="Run pre-flight checks against LLM providers")
    parser.add_argument("--import-xml-folder", type=str, help="Bulk import a folder of unsorted XML reports")
    parser.add_argument("--recursive", action="store_true", help="Enable recursive scanning for --import-xml-folder")
    parser.add_argument("--import-xml", action="store_true", help="Scan data/incoming_xml/, validate, index, and organize reports")
    
    args = parser.parse_args()
    
    if args.import_xml:
        from src.ingestion.xml_importer import import_xml_reports
        stats = import_xml_reports()
        print("XML files scanned:", stats["scanned"])
        print("Successfully imported:", stats["success"])
        print("Already indexed:", stats["indexed"])
        print("Moved to _unsorted:", stats["unsorted"])
        print("Failed:", stats["failed"])
        
    elif args.import_xml_folder:
        from src.ingestion.bulk_xml_importer import import_xml_folder
        import_xml_folder(args.import_xml_folder, recursive=args.recursive)
        
    elif args.ingest_new:
        print("Scanning and ingesting new reports...")
        manager = DocumentManager()
        result = manager.ingest_new_reports()
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        
    elif args.list_companies:
        router = CompanyRouter()
        companies = router.get_known_companies()
        print("Registered Companies:")
        for idx, c in enumerate(companies):
            print(f"{idx+1}. {c}")
            
    elif args.extract_links:
        from src.ingestion.link_extractor import LinkExtractorUtility
        extractor = LinkExtractorUtility()
        summary = extractor.run_extractor(args.extract_links)
        
        print("\n--- Ingestion Link Extraction Summary ---")
        print(f"Links found: {summary['found']}")
        print(f"Report links matched (XML/PDF): {summary['xml_matched']}")
        print(f"Unresolved/other: {summary['unresolved']}")
        print(f"Downloaded (new): {summary['downloaded']}")
        print(f"Skipped (already indexed): {summary['skipped_indexed']}")
        print(f"Unsorted (company/year unclear): {summary['unsorted']}")
            
    elif args.check_llm:
        import requests
        from config import settings
        
        print("=== Sustally Pre-flight LLM Diagnostics ===")
        
        # 1. Check Ollama
        ollama_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        print(f"Checking Ollama connectivity at: {ollama_url}")
        ollama_ok = False
        try:
            resp = requests.get(ollama_url, timeout=3.0)
            if resp.status_code == 200:
                print("🟢 PASS: Ollama service is reachable and returned HTTP 200.")
                ollama_ok = True
            else:
                print(f"🔴 FAIL: Ollama returned status code {resp.status_code}.")
        except Exception as e:
            print(f"🔴 FAIL: Ollama is NOT reachable: {str(e)}")
            
        print("\n--- Summary ---")
        print(f"Ollama:    {'AVAILABLE' if ollama_ok else 'UNAVAILABLE'}")
        
        active_provider = settings.LLM_PROVIDER.strip().lower()
        if active_provider == "ollama":
            print("Active provider: Ollama (configured).")
            is_active_ok = ollama_ok
        elif active_provider == "openai":
            if settings.OPENAI_API_KEY.strip():
                print("Active provider: OpenAI (configured). Checking connectivity is skipped (cloud API), API Key is set.")
                is_active_ok = True
            else:
                print("🔴 FAIL: Active provider is OpenAI but OPENAI_API_KEY is not set in environment.")
                is_active_ok = False
        else:
            print(f"Active provider: {settings.LLM_PROVIDER} (configured) — unrecognized.")
            is_active_ok = False
            
        if not is_active_ok:
            print(f"\n⚠️ WARNING: The active provider '{settings.LLM_PROVIDER}' is not available. Please start the service.")
            sys.exit(1)
        sys.exit(0)
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
