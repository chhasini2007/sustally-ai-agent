import json
with open("data/document_index.json", "r") as f:
    index = json.load(f)
for k in index.keys():
    if "Infosys" in k or "Tata" in k or "TCS" in k or "tcs" in k:
        print(k)
