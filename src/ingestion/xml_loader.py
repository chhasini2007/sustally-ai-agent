import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple
from src.processing.metric_taxonomy import METRIC_TAXONOMY

class XMLLoader:
    def load_xml(self, file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Loads XML, extracts text content and direct structured metrics.
        Returns:
        - List of chunks: [{"section": str, "content": str, "page": str}]
        - List of extracted metrics: [{"metric_key": str, "metric_label": str, "value": float, "unit": str, "page": str, "year": str}]
        """
        chunks = []
        metrics = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Build context Ref -> Year map
            context_year_map = {}
            for node in root.iter():
                local_tag = node.tag.split("}")[-1]
                if local_tag == "context":
                    context_id = node.attrib.get("id")
                    if context_id:
                        end_date = None
                        for child in node.iter():
                            child_tag = child.tag.split("}")[-1]
                            if child_tag in ("endDate", "instant"):
                                if child.text:
                                    end_date = child.text.strip()
                                    break
                        if end_date:
                            match = re.match(r"(\d{4})", end_date)
                            if match:
                                context_year_map[context_id] = match.group(1)
            
            # Simple recursive helper to extract all tag content
            all_text_elements = []
            
            def recurse(node, path=""):
                current_path = f"{path}/{node.tag}" if path else node.tag
                
                # Strip namespace (e.g. {http://...}TagName -> TagName)
                local_tag = node.tag
                if local_tag.startswith("{") and "}" in local_tag:
                    local_tag = local_tag.split("}", 1)[1]
                
                tag_name_clean = local_tag.replace("_", "").replace("-", "").replace(" ", "").lower()
                
                # Custom handler for BRSR headcount count tags
                matched_key = None
                context_ref = node.attrib.get("contextRef", "")
                
                # Custom handler for BRSR tags to avoid false synonym matches
                matched_key = None
                context_ref = node.attrib.get("contextRef", "")
                context_ref_lower = context_ref.lower() if context_ref else ""
                
                # Explicit mappings
                if tag_name_clean == "percentageofemployeesorworkersincludingdifferentlyabled":
                    if "female" in context_ref_lower and "employees" in context_ref_lower:
                        matched_key = "female_employee_headcount_share_pct"
                elif tag_name_clean == "percentageofgrosswagespaidtofemaletototalwagespaid":
                    matched_key = "female_employee_wage_share_pct"
                elif tag_name_clean == "totalenergyconsumedfromrenewablesources":
                    matched_key = "raw_renewable_energy"
                elif tag_name_clean == "totalenergyconsumedfromrenewableandnonrenewablesources":
                    matched_key = "raw_total_energy"
                elif tag_name_clean == "totalvolumeofwaterconsumption":
                    matched_key = "water_consumption_kl"
                elif tag_name_clean == "totalscope1emissions":
                    matched_key = "scope1_emissions_tco2e"
                elif tag_name_clean == "totalscope2emissions":
                    matched_key = "scope2_emissions_tco2e"
                elif tag_name_clean == "totalscope3emissions":
                    matched_key = "scope3_emissions_tco2e"
                elif tag_name_clean == "totalwastegenerated":
                    matched_key = "waste_generation_tonnes"
                elif tag_name_clean == "numberofemployeesorworkersincludingdifferentlyabled":
                    if context_ref:
                        if "female" in context_ref_lower and "employee" in context_ref_lower:
                            matched_key = "female_employee_count"
                        elif "employees" in context_ref_lower and "gender" in context_ref_lower:
                            matched_key = "total_employee_count"
                elif tag_name_clean in ("averagenumberoffemaleemployeesorworkersatthebeginningoftheyearandasatendoftheyear", "numberoffemaleemployeesorworkers"):
                    matched_key = "female_employee_count"
                elif tag_name_clean in ("averagenumberofemployeesorworkersatthebeginningoftheyearandasatendoftheyear", "numberofemployeesorworkers"):
                    matched_key = "total_employee_count"
                
                # Fallback to taxonomy synonym matching (excluding percentage keys from loose substring matching)
                if not matched_key:
                    if any(x in tag_name_clean for x in ["intensity", "turnover", "output", "rupee", "revenue", "ppp", "adjusted", "perarea", "peremployee", "perworker"]):
                        pass
                    else:
                        for key, info in METRIC_TAXONOMY.items():
                            if key.endswith("_pct"):
                                continue # Skip loose substring matches for percentages
                            
                            key_clean = key.replace("_", "").replace("-", "").replace(" ", "").lower()
                            if tag_name_clean == key_clean:
                                matched_key = key
                                break
                            
                            # Check synonyms
                            match_found = False
                            for syn in info["synonyms"]:
                                syn_clean = syn.replace("_", "").replace("-", "").replace(" ", "").lower()
                                if tag_name_clean == syn_clean or syn_clean in tag_name_clean:
                                    matched_key = key
                                    match_found = True
                                    break
                            if match_found:
                                break

                # If matched, try to extract numerical value
                if matched_key and node.text:
                    val_str = node.text.strip().replace(",", "")
                    # Extract numeric part
                    num_match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", val_str)
                    if num_match:
                        try:
                            val = float(num_match.group(0))
                            
                            # Scale fractions <= 1.0 to percentages for percentage metrics
                            if matched_key in ("female_employee_headcount_share_pct", "female_employee_wage_share_pct"):
                                if val <= 1.0:
                                    val = val * 100.0
                            
                            tax_info = METRIC_TAXONOMY.get(matched_key)
                            unit = node.attrib.get("unit", tax_info["unit"] if tax_info else "")
                            resolved_year = None
                            if context_ref:
                                resolved_year = context_year_map.get(context_ref)
                                
                            metrics.append({
                                "metric_key": matched_key,
                                "metric_label": f"XML Tag: {current_path}",
                                "value": val,
                                "unit": unit,
                                "page": "XML",
                                "year": resolved_year
                            })
                        except ValueError:
                            pass
                
                if node.text and node.text.strip():
                    all_text_elements.append(f"{node.tag}: {node.text.strip()}")
                    
                for child in node:
                    recurse(child, current_path)
                    
            recurse(root)
            
            # Group all XML text into a single cohesive narrative chunk (truncated to fit model token limits)
            full_text = "\n".join(all_text_elements[:100])
            chunks.append({
                "section": "XML Content",
                "content": full_text,
                "page": "XML"
            })
            
            # Post-process raw energy metrics to calculate renewable_energy_pct
            energy_by_year = {}
            filtered_metrics = []
            for m in metrics:
                k = m["metric_key"]
                yr = m["year"]
                if k == "raw_renewable_energy":
                    if yr not in energy_by_year:
                        energy_by_year[yr] = {}
                    energy_by_year[yr]["renewable"] = m["value"]
                    energy_by_year[yr]["label"] = m["metric_label"]
                elif k == "raw_total_energy":
                    if yr not in energy_by_year:
                        energy_by_year[yr] = {}
                    energy_by_year[yr]["total"] = m["value"]
                    energy_by_year[yr]["label"] = m["metric_label"]
                else:
                    filtered_metrics.append(m)
                    
            for yr, data in energy_by_year.items():
                if "renewable" in data and "total" in data and data["total"] > 0:
                    pct_val = (data["renewable"] / data["total"]) * 100.0
                    filtered_metrics.append({
                        "metric_key": "renewable_energy_pct",
                        "metric_label": f"Calculated from: {data['label']}",
                        "value": pct_val,
                        "unit": "%",
                        "page": "XML",
                        "year": yr
                    })
            metrics = filtered_metrics
            
        except Exception as e:
            # Add basic dummy chunk for structural fallback
            chunks.append({
                "section": "XML Error",
                "content": f"Failed to parse XML file: {str(e)}",
                "page": "XML"
            })
            
        return chunks, metrics

