import xml.etree.ElementTree as ET

def find_tags():
    tree = ET.parse("data/raw_reports/Infosys Limited/2025/BRSR_1477079_03072025095250_WEB_3.xml")
    root = tree.getroot()
    for child in root.iter():
        if "scope1" in child.tag.lower():
            print(f"Tag: {child.tag} | Text: {child.text} | contextRef: {child.attrib.get('contextRef')}")

if __name__ == "__main__":
    find_tags()
