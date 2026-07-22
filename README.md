# Sustally ESG Intelligence Platform 

**Sustally** is an enterprise-grade, AI-powered ESG (Environmental, Social, and Governance) intelligence dashboard designed to ingest, process, and analyze Business Responsibility and Sustainability Reports (BRSR) of public and private companies.

Built with a performance-optimized multi-agent architecture, Sustally delivers sub-second response times for structured numeric queries (via an SQLite database) and highly-grounded qualitative insights (via a pre-filtered ChromaDB vector store RAG).

---

## 🚀 Key Features

- **Dual-Retrieval Routing**: Uses deterministic lane routing (SQLite vs. ChromaDB) to deliver instant quantitative data lookups and precise qualitative semantic search.
- **Multi-Agent Orchestration**: Coordinates specialized agents (Planner, Retrieval, Reasoning, Comparison, Ranking, and Report Generator) to fulfill complex analysis tasks.
- **Automated Ingestion Pipeline**: Bulk and incremental parser for PDF and XML reports, standardizing names, years, metrics, and units via a unified taxonomy mapping.
- **Year-Over-Year (YoY) Analytics**: Automatically calculates trends, percentage changes, and direction of metrics over multiple fiscal years.
- **Bloomberg-Grade Reports**: Generates formal ESG analyst reports featuring Executive Summaries, Grounded Evidence, Confidence Levels, and Citations.
- **Interactive Visualization**: Automatically generates Plotly charts for trends, comparative leaderboards, and metric distributions.
- **Secure Demo Tunneling**: Out-of-the-box ngrok integration for sharing authenticated local app instances securely.

---

## 🏛️ System Architecture

Sustally avoids the latency and hallucination pitfalls of generic RAG systems by separating queries into distinct execution paths:

1. **Planner Agent**: Classifies question intent, extracts target company/year metadata, and matches required ESG variables against a unified taxonomy.
2. **Lane Routing**:
   - **Lane A (Quantitative)**: Deterministic SQLite database lookup for exact values (e.g., water consumption, emissions totals).
   - **Lane B (Qualitative)**: Semantic vector store search limited only to text chunks belonging to the target report, preventing cross-company contamination.
   - **Lane C (Comparative)**: Dynamic comparisons and sector-wide ranking analysis.
   - **Lane D (Out of Scope)**: Graceful deflected fallback for unrelated prompts.
3. **Reasoning and Comparison Agent**: Performs calculations, delta tracking, and unit conversions.
4. **Report Assembly**: Formats and packages output with data grounding logs.

Detailed design diagrams are available in [Architecture.md](docs/Architecture.md).

---

## 📂 Project Structure

```text
sustally/
├── .streamlit/                   # Streamlit configurations and secret examples
├── app/
│   └── streamlit_app.py          # Dashboard UI entrypoint
├── config/
│   ├── settings.py               # Central directory paths, models, and environment variables
│   └── __init__.py
├── data/
│   ├── incoming_xml/             # Target directory for bulk XML reports
│   └── raw_reports/              # Target directory for PDF reports
├── docs/                         # Detailed architecture, setup, and workflow documentation
│   ├── Architecture.md
│   ├── Setup.md
│   ├── Deployment.md
│   └── Workflow.md
├── scripts/                      # System administration, audits, and ingestion utilities
│   └── data_quality_audit.py     # Check folder/year alignments and data parsing
├── src/                          # Application core package
│   ├── agents/                   # Agent logic files (Planner, Retrieval, Reasoning, etc.)
│   ├── database/                 # SQLite and ChromaDB store connectors
│   ├── embeddings/               # Tokenizers and SentenceTransformer embeddings manager
│   ├── ingestion/                # PDF loaders, XML parsers, and loaders
│   ├── processing/               # Taxonomies, metrics normalizers, and text chunkers
│   ├── retrieval/                # Multi-lane routing, query parser, and routers
│   ├── utils/                    # Shared caching and helpers
│   └── visualization/            # Plotly dashboard chart generators
├── tests/                        # Suite of active unit tests
├── LICENSE                       # MIT License
├── README.md                     # This file
├── requirements.txt              # Project package dependencies
└── run.py                        # Ingestion and pre-flight diagnostics CLI
```

---

## 🛠️ Installation & Setup

Please refer to the step-by-step [Setup Guide](docs/Setup.md) for detailed guidelines. A quick-start summary is provided below:

### 1. Configure Local Environment
```bash
# Clone the repository
git clone https://github.com/your-organization/sustally.git
cd sustally

# Initialize virtual environment and install packages
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements-local.txt
```

### 2. Configure Credentials
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update the `.env` settings to match your chosen LLM provider (Ollama or OpenAI) and credentials.

### 3. Pull LLM Model & Run Ingestion
If running locally, pull the Ollama model:
```bash
ollama pull qwen2.5:7b
```
Ensure Ollama is running and ingest the sample reports:
```bash
python run.py --check-llm
python run.py --import-xml
```

---

## 📈 Usage & CLI Reference

### Running the CLI Engine
The root `run.py` script manages back-end operations:
```bash
# Verify LLM provider connectivity
python run.py --check-llm

# Bulk import data/incoming_xml/ reports
python run.py --import-xml

# Scan and incrementally ingest new files under raw_reports/
python run.py --ingest-new

# List all registered companies
python run.py --list-companies
```

### Launching the Dashboard UI
To open the Streamlit web dashboard locally:
```bash
python -m streamlit run app/streamlit_app.py
```
Open `http://localhost:8501` in your browser.

---

## ❓ Sample Queries

Try the following questions in the dashboard query box:

- **Lane A (Quantitative lookup)**: `"What is the water consumption of Infosys in 2024?"`
- **Lane B (Narrative lookup)**: `"What is the climate risk mitigation strategy of Tata Consultancy Services?"`
- **Lane C (Comparison)**: `"Compare Scope 1 emissions between TCS and Infosys in 2024."`
- **Lane C (Ranking)**: `"Rank pharmaceutical companies by water consumption."`
- **Lane C (Trend)**: `"Water consumption trend for Infosys between 2022 and 2024."`

---

## 🖼️ Screenshots

*Dashboard UI placeholder - Coming soon*

---

## 🔮 Future Improvements

- **Cross-Report Tabular Extractors**: Enhance processing for multi-page tables in scanned PDFs.
- **Taxonomy Expansion**: Expand default taxonomies to cover global standards (e.g. GRI, SASB, CSRD) in addition to SEBI BRSR.
- **Enhanced LLM Cache**: Implement vector semantic cache for repeated query intents to reduce API costs.

## ☁️ Vercel Cloud Deployment

Sustally is fully configured for serverless deployment on **Vercel** with a **Next.js frontend** and a **FastAPI backend** (optimized for the 500 MB function limits by splitting dependencies and excluding large report databases).

### Deployment Steps:
1. **Push code to GitHub**: Create a repository and push your project files.
2. **Import to Vercel**:
   - Log in to Vercel and import your repository.
   - Set the Framework Preset to **Next.js** (Vercel will auto-detect it).
3. **Configure Environment Variables**:
   Add the following variables in your Vercel Project Settings:
   - `DEPLOYMENT_MODE`: Set to `vercel` (Enables lightweight cloud adapter mode).
   - `LLM_PROVIDER`: Set to `openai` (Ollama cannot run serverless).
   - `OPENAI_API_KEY`: Your OpenAI API key.
   - `OPENAI_MODEL`: `gpt-4o-mini` (or preferred model).
   - `SUSTALLY_BACKEND_URL`: (Optional) Connects to a hosted backend server running the full RAG pipeline.
4. **Deploy**: Click **Deploy**.
5. **Verify Endpoints**:
   - Root URL `/` loads the Next.js search dashboard interface.
   - `/api/health` returns `{"status": "healthy"}` confirming FastAPI backend status.
   - `/api/ask` serves the multi-agent question answering capabilities.

> [!NOTE]
> The local Streamlit dashboard remains fully available via `pip install -r requirements-local.txt` and `python -m streamlit run app/streamlit_app.py`. For production-grade Vercel RAG capabilities, configure a hosted cloud database or remote backend endpoint (`SUSTALLY_BACKEND_URL`) as explained in [Deployment.md](docs/Deployment.md) (local database and vector files are automatically excluded in `vercel.json` to keep the bundle under 500 MB).


---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

