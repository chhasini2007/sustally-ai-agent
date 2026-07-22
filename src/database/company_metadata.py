import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from src.database.metrics_store import MetricsStore

class CompanyMetadataManager:
    def __init__(self):
        self.metrics_store = MetricsStore()
        # Explicit overrides for key companies to guarantee correctness
        self.overrides = {
            "tata consultancy services limited": {"sector": "IT", "industry": "Technology", "country": "India"},
            "infosys limited": {"sector": "IT", "industry": "Technology", "country": "India"},
            "the south indian bank limited": {"sector": "Banking", "industry": "Financial Services", "country": "India"},
            "canara bank": {"sector": "Banking", "industry": "Financial Services", "country": "India"},
            "reliance industries limited": {"sector": "Energy", "industry": "Conglomerate", "country": "India"},
            "cipla limited": {"sector": "Pharmaceuticals", "industry": "Healthcare", "country": "India"},
            "sun pharmaceutical industries limited": {"sector": "Pharmaceuticals", "industry": "Healthcare", "country": "India"}
        }
        
    def register_company(self, company_name: str, sector: str, industry: str = "Other", country: str = "India"):
        comp_lower = company_name.lower().strip()
        self.overrides[comp_lower] = {
            "sector": sector,
            "industry": industry,
            "country": country
        }

    def get_company_metadata(self, company_name: str) -> Dict[str, Any]:
        comp_lower = company_name.lower().strip()
        
        # Check overrides exactly
        if comp_lower in self.overrides:
            meta = self.overrides[comp_lower].copy()
            meta["company"] = company_name
            meta["report_years"] = self.metrics_store.get_company_years(company_name)
            return meta
            
        # Check partial override matches
        for k, v in self.overrides.items():
            if k in comp_lower or comp_lower in k:
                meta = v.copy()
                meta["company"] = company_name
                meta["report_years"] = self.metrics_store.get_company_years(company_name)
                return meta
                
        # Rule-based fallback classification
        sector = "Other"
        industry = "Other"
        country = "India"
        
        # Sector / Industry keywords detection
        if any(w in comp_lower for w in ["bank", "banking"]):
            sector = "Banking"
            industry = "Financial Services"
        elif any(w in comp_lower for w in ["pharma", "pharmaceutical", "health", "lab", "biotech", "clinical", "medplus", "drug", "care", "medical", "hospital"]):
            sector = "Pharmaceuticals"
            industry = "Healthcare"
        elif any(w in comp_lower for w in ["tech", "soft", "info", "system", "consultancy", "digital", "data", "analytics", "comput", "electronic", "solution", "aptech", "infotech"]):
            sector = "IT"
            industry = "Technology"
        elif "cement" in comp_lower:
            sector = "Cement"
            industry = "Construction Materials"
        elif "chem" in comp_lower:
            sector = "Chemicals"
            industry = "Basic Materials"
        elif any(w in comp_lower for w in ["telecom", "communications", "mobile"]):
            sector = "Telecommunications"
            industry = "Communication Services"
        elif any(w in comp_lower for w in ["power", "energy", "solar", "wind", "ntpc"]):
            sector = "Energy"
            industry = "Utilities"
        elif any(w in comp_lower for w in ["steel", "metal", "iron", "aluminium", "zinc", "mining", "forge", "oxide"]):
            sector = "Metals & Mining"
            industry = "Basic Materials"
        elif any(w in comp_lower for w in ["auto", "motor", "car", "tyre", "vehicles", "bajaj", "wheel"]):
            sector = "Automobile"
            industry = "Consumer Cyclical"
        elif "insurance" in comp_lower:
            sector = "Insurance"
            industry = "Financial Services"
        elif any(w in comp_lower for w in ["finance", "capital", "wealth", "securities", "mutual", "fund", "housing", "financial", "credit"]):
            sector = "Financial Services"
            industry = "Financial Services"
        elif any(w in comp_lower for w in ["agro", "crop", "sugar", "fertilizer", "food", "brew", "agriculture", "spice", "tea"]):
            sector = "Agriculture & Food"
            industry = "Consumer Defensive"
        elif any(w in comp_lower for w in ["build", "infra", "const", "bridge", "pipe", "engineering"]):
            sector = "Infrastructure & Construction"
            industry = "Industrials"
        elif any(w in comp_lower for w in ["paper", "packaging"]):
            sector = "Paper & Packaging"
            industry = "Basic Materials"
        elif any(w in comp_lower for w in ["textile", "fashion", "garment", "denim", "retail", "wear", "silk", "wool"]):
            sector = "Textiles & Apparel"
            industry = "Consumer Cyclical"

        return {
            "company": company_name,
            "sector": sector,
            "industry": industry,
            "country": country,
            "report_years": self.metrics_store.get_company_years(company_name)
        }
        
    def get_companies_by_sector(self, sector: str) -> List[str]:
        all_companies = set(self.metrics_store.get_all_companies())
        for o_name in self.overrides.keys():
            all_companies.add(o_name.title())

        matched = []
        sec_lower = sector.lower().strip()
        for comp in all_companies:
            meta = self.get_company_metadata(comp)
            if (meta["sector"].lower() == sec_lower or 
                meta["industry"].lower() == sec_lower or 
                sec_lower in meta["sector"].lower() or 
                sec_lower in meta["industry"].lower()):
                if comp not in matched:
                    matched.append(comp)
        return matched
