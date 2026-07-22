import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.xml_loader import XMLLoader

def check_loader():
    loader = XMLLoader()
    chunks, metrics = loader.load_xml("data/incoming_xml/BRSR_1477079_03072025095250_WEB.xml")
    
    print(f"Extracted {len(metrics)} metrics:")
    for m in metrics[:30]:
        print(m)

if __name__ == "__main__":
    check_loader()
