import sys
import os
try:
    import fitz
    _ = fitz.Rect
    HAS_FITZ = True
except (ImportError, AttributeError, Exception):
    HAS_FITZ = False
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.link_extractor import LinkExtractorUtility

def create_test_pdf(filename="test_links.pdf"):
    if HAS_FITZ:
        doc = fitz.open()
        page = doc.new_page()
        # Insert visible text with a URL
        page.insert_text((50, 50), "TCS 2024 Report Link: http://example.com/tcs_report_link.xml")
        # Insert a link annotation
        link_rect = fitz.Rect(50, 100, 250, 120)
        page.insert_link({
            "kind": fitz.LINK_URI,
            "from": link_rect,
            "uri": "http://example.com/infosys_report_2023.xml"
        })
        doc.save(filename)
        doc.close()
    else:
        # Fallback PDF generation using pypdf
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject, NumberObject, DictionaryObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        
        # Define Helvetica Font Resource
        font_dict = DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica")
            })
        })
        resources_dict = DictionaryObject({
            NameObject("/Font"): font_dict
        })
        page[NameObject("/Resources")] = resources_dict
        
        # Inject text into the content stream
        content_stream = b"BT /F1 12 Tf 50 700 Td (TCS 2024 Report Link: http://example.com/tcs_report_link.xml) Tj ET"
        stream = DecodedStreamObject()
        stream._data = content_stream
        stream[NameObject("/Length")] = NumberObject(len(content_stream))
        page[NameObject("/Contents")] = stream
        
        # Add a URI link annotation
        writer.add_uri(
            page_number=0,
            uri="http://example.com/infosys_report_2023.xml",
            rect=(50, 100, 250, 120)
        )
        
        with open(filename, "wb") as f:
            writer.write(f)

def run_tests():
    # 1. Create a dummy PDF with links
    pdf_name = "test_links.pdf"
    create_test_pdf(pdf_name)
    
    extractor = LinkExtractorUtility()
    
    # 2. Test extraction
    links = extractor.extract_links_from_pdf(pdf_name)
    print("Extracted links:", links)
    
    # Clean up PDF file
    if os.path.exists(pdf_name):
        os.remove(pdf_name)
        
    assert len(links) == 2, f"Should extract exactly 2 links, got {len(links)}"
    
    # Check link contents
    urls = [l["url"] for l in links]
    assert "http://example.com/tcs_report_link.xml" in urls
    assert "http://example.com/infosys_report_2023.xml" in urls
    
    # 3. Test company/year resolver
    c1, y1 = extractor.resolve_company_year("TCS 2024 Report Link", "http://example.com/tcs_report_link.xml")
    print("Resolved TCS Context:", c1, y1)
    assert c1 == "Tata Consultancy Services Limited"
    assert y1 == "2024"
    
    c2, y2 = extractor.resolve_company_year("No context here", "http://example.com/infosys_report_2023.xml")
    print("Resolved Infosys Context (Fallback to URL):", c2, y2)
    assert c2 == "Infosys Limited"
    assert y2 == "2023"
    
    # 4. Test is_xml_link logic (Pass 1 cheap check)
    session_mock = MagicMock()
    is_xml, reason = extractor.is_xml_link("http://example.com/data.xml", session_mock)
    assert is_xml is True
    print("XML check success:", is_xml, reason)
    
    # Pass 2 Head check simulation
    session_mock.head.return_value.headers = {"Content-Type": "application/xml"}
    is_xml, reason = extractor.is_xml_link("http://example.com/data_api?format=raw", session_mock)
    assert is_xml is True
    print("XML check Pass 2 HEAD success:", is_xml, reason)
    
    # Pass 2 Head check skip PDF
    session_mock.head.return_value.headers = {"Content-Type": "application/pdf"}
    is_xml, reason = extractor.is_xml_link("http://example.com/data_api?pdf=true", session_mock)
    assert is_xml is False
    print("XML check skip PDF success:", is_xml, reason)

    print("\nLINK EXTRACTOR TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
