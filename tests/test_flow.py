import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.document_manager import DocumentManager
from src.database.metrics_store import MetricsStore
from src.retrieval.company_router import CompanyRouter
from src.retrieval.query_classifier import QueryClassifier

def run_tests():
    print("=== Testing Ingestion ===")
    manager = DocumentManager()
    result = manager.ingest_new_reports()
    print("Ingestion result:", result)
    
    print("\n=== Testing Metrics Database ===")
    store = MetricsStore()
    companies = store.get_all_companies()
    print("Registered Companies:", companies)
    assert len(companies) >= 2, "Should have ingested both mock companies"
    
    # Check specific metric
    metric_val = store.get_metric("Infosys Limited", "2024", "scope1_emissions_tco2e")
    print("Infosys 2024 Scope 1 emissions:", metric_val)
    assert len(metric_val) > 0, "Should find Scope 1 emissions for Infosys"
    assert metric_val[0]["value"] == 12450.5, "Value should match mock XML exactly"
    
    print("\n=== Testing Company Routing ===")
    router = CompanyRouter()
    comps, years = router.resolve_companies_and_years("What are the emissions for TCS in 2024?")
    print("Resolved:", comps, years)
    assert "Tata Consultancy Services Limited" in comps, "Should resolve TCS"
    assert "2024" in years, "Should resolve year 2024"
    
    print("\n=== Testing Query Classification ===")
    classifier = QueryClassifier()
    
    # Lane A test
    c1 = classifier.classify("What is the water consumption of Infosys in 2024?")
    print("Query: 'What is the water consumption of Infosys in 2024?' -> Lane:", c1["lane"])
    assert c1["lane"] == "A", "Should route to Lane A"
    
    # Lane B test
    c2 = classifier.classify("Summarize the sustainability report of Infosys 2024")
    print("Query: 'Summarize the sustainability report of Infosys 2024' -> Lane:", c2["lane"])
    assert c2["lane"] == "B", "Should route to Lane B"
    
    # Lane C test
    c3 = classifier.classify("Compare the water consumption between TCS and Infosys")
    print("Query: 'Compare the water consumption between TCS and Infosys' -> Lane:", c3["lane"])
    assert c3["lane"] == "C", "Should route to Lane C"
    
    print("\nALL PIPELINE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
