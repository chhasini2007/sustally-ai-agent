# Setup and Installation Guide

This guide details the steps required to configure your local development environment and run the **Sustally ESG Intelligence Platform**.

---

## 1. Prerequisites

- **Python**: Version 3.10 to 3.13 is recommended.
- **Git**: For version control.
- **Ollama** (Required for local LLM usage): Download and install from [ollama.com](https://ollama.com).
- **OpenAI API Key** (Required if running in Cloud mode or using OpenAI models).

---

## 2. Initial Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-organization/sustally.git
   cd sustally
   ```

2. **Create a Virtual Environment**:
   ```bash
   python -m venv .venv
   ```

3. **Activate the Virtual Environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt)**:
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 3. Environment Variables Configuration

Create a `.env` file in the root directory by copying the example file:
```bash
cp .env.example .env
```

Open `.env` and configure the following parameters:

```env
# Choose between 'ollama' or 'openai'
LLM_PROVIDER=ollama

# Ollama Setup (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# OpenAI Setup (Cloud / Premium)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Authentication Credentials for Dashboard and Demo Tunnel
STREAMLIT_APP_USER=admin
STREAMLIT_APP_PASSWORD=secure_password_here
```

---

## 4. Database Setup and Ingestion

Before starting the web application, you must populate the databases (`metrics.db` and the Chroma vector store) with corporate sustainability reports.

1. **Local LLM Pre-flight Check**:
   If using Ollama, ensure it is running in the background and the model is downloaded:
   ```bash
   ollama pull qwen2.5:7b
   ```
   Verify connection:
   ```bash
   python run.py --check-llm
   ```

2. **Bulk Import Existing XML Reports**:
   Scan `data/incoming_xml/` to validate, parse, normalize, and ingest XML reports:
   ```bash
   python run.py --import-xml
   ```

3. **Incremental PDF/XML Ingestion**:
   To scan the raw reports folder (`data/raw_reports/`) and ingest new or modified files:
   ```bash
   python run.py --ingest-new
   ```

4. **Verify Registered Companies**:
   Check if the database has successfully registered company records:
   ```bash
   python run.py --list-companies
   ```

---

## 5. Running the Application

To launch the Streamlit dashboard on your local machine:
```bash
python -m streamlit run app/streamlit_app.py
```

Once running, open your web browser and navigate to `http://localhost:8501`. Use the configured `STREAMLIT_APP_USER` and `STREAMLIT_APP_PASSWORD` to log in.
