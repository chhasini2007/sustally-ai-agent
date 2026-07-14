# Canonical taxonomy dictionary mapping keys to their metadata and common query aliases/synonyms

METRIC_TAXONOMY = {
    "scope1_emissions_tco2e": {
        "label": "Scope 1 Emissions",
        "unit": "tCO2e",
        "synonyms": [
            "scope 1", "scope 1 emissions", "direct emissions", "direct ghg emissions", 
            "scope 1 greenhouse gas emissions", "scope 1 ghg emissions"
        ],
        "patterns": [
            r"scope\s*1\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"direct\s*(?:ghg|emissions|greenhouse\s*gas\s*emissions)"
        ]
    },
    "scope2_emissions_tco2e": {
        "label": "Scope 2 Emissions",
        "unit": "tCO2e",
        "synonyms": [
            "scope 2", "scope 2 emissions", "indirect emissions", "indirect ghg emissions", 
            "location-based scope 2", "market-based scope 2", "scope 2 greenhouse gas emissions",
            "scope 2 ghg emissions"
        ],
        "patterns": [
            r"scope\s*2\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"indirect\s*(?:ghg|emissions|greenhouse\s*gas\s*emissions)"
        ]
    },
    "scope3_emissions_tco2e": {
        "label": "Scope 3 Emissions",
        "unit": "tCO2e",
        "synonyms": [
            "scope 3", "scope 3 emissions", "value chain emissions", "other indirect emissions",
            "scope 3 greenhouse gas emissions", "scope 3 ghg emissions"
        ],
        "patterns": [
            r"scope\s*3\s*(?:emissions|ghg|greenhouse\s*gas)?"
        ]
    },
    "water_consumption_kl": {
        "label": "Water Consumption",
        "unit": "kl",
        "synonyms": [
            "water consumption", "water consumed", "water usage", "total water consumed", 
            "water withdrawal", "total water consumption"
        ],
        "patterns": [
            r"water\s*consumption",
            r"water\s*consumed",
            r"water\s*usage",
            r"total\s*water\s*consumed"
        ]
    },
    "renewable_energy_pct": {
        "label": "Renewable Energy Share",
        "unit": "%",
        "synonyms": [
            "renewable energy share", "renewable energy percentage", "renewable energy",
            "renewable source", "renewable electricity percentage", "renewable power share",
            "renewable energy consumption percentage"
        ],
        "patterns": [
            r"renewable\s*energy\s*(?:share|percentage|pct|electricity|power)?",
            r"share\s*of\s*renewable\s*energy"
        ]
    },
    "female_employee_headcount_share_pct": {
        "label": "Female Employee Headcount Share",
        "unit": "%",
        "synonyms": [
            "female employee headcount share", "percentage of female employees", "female employee share", 
            "how many female employees", "percentage of women employees", "percentage of women", 
            "female representation", "women representation", "women workforce percentage", 
            "gender diversity", "female employees", "women employees", "women in workforce"
        ],
        "patterns": [
            r"female\s*employee\s*(?:share|percentage|pct)",
            r"percentage\s*of\s*female\s*employees",
            r"women\s*workforce\s*(?:share|percentage|pct)",
            r"female\s*representation",
            r"women\s*representation",
            r"female\s*employees\s*headcount",
            r"number\s*of\s*female\s*employees",
            r"female\s*employees",
            r"women\s*employees",
            r"women\s*in\s*workforce"
        ]
    },
    "female_employee_count": {
        "label": "Female Employee Headcount",
        "unit": "employees",
        "synonyms": [
            "female employee count", "female employee headcount", "number of female employees",
            "how many women employees", "number of women employees", "total female employees",
            "count of female employees",
            "averagenumberoffemaleemployeesorworkersatthebeginningoftheyearandasatendoftheyear",
            "numberoffemaleemployeesorworkers"
        ],
        "patterns": [
            r"number\s*of\s*female\s*employees(?!\s*wage|\s*share|\s*percentage|\s*pct)",
            r"female\s*employees\s*count",
            r"female\s*employees\s*headcount"
        ]
    },
    "total_employee_count": {
        "label": "Total Employee Headcount",
        "unit": "employees",
        "synonyms": [
            "total employee count", "total employee headcount", "number of total employees",
            "total employees", "total headcount", "how many total employees",
            "count of total employees"
        ],
        "patterns": [
            r"total\s*(?:employee|workforce|staff)\s*(?:count|headcount|number)",
            r"number\s*of\s*total\s*employees",
            r"total\s*employees"
        ]
    },
    "female_employee_wage_share_pct": {
        "label": "Female Employee Wage Share",
        "unit": "%",
        "synonyms": [
            "female employee wage share", "wages paid to female employees", "percentage of gross wages paid to female employees to total wages", 
            "female employee wage percentage", "female wage share", "gross wages paid to female as % of total wages", 
            "gross wages paid to female to total wages paid", "percentageofgrosswagespaidtofemaletototalwagespaid",
            "grosswagespaidtofemale"
        ],
        "patterns": [
            r"wages?\s*paid\s*to\s*female\s*employees",
            r"female\s*employee\s*wage\s*(?:share|percentage|pct)",
            r"percentage\s*of\s*gross\s*wages?\s*paid\s*to\s*female",
            r"wages?\s*paid\s*to\s*female",
            r"female\s*wage\s*share"
        ]
    },
    "waste_generation_tonnes": {
        "label": "Total Waste Generated",
        "unit": "tonnes",
        "synonyms": [
            "waste generation", "total waste generated", "waste generated", 
            "hazardous waste generated", "non-hazardous waste generated"
        ],
        "patterns": [
            r"waste\s*generated",
            r"total\s*waste\s*generated",
            r"waste\s*generation"
        ]
    }
}

# Fast lookup dictionary mapping aliases to canonical key
ALIASED_METRICS = {}
for canonical_key, info in METRIC_TAXONOMY.items():
    for synonym in info["synonyms"]:
        ALIASED_METRICS[synonym.lower()] = canonical_key
