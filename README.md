# Sustally Sustainability Report Agent

AI-powered Sustainability Report Analysis Agent. Rebuilt with a performance-optimized architecture that delivers sub-second response times for structured numeric queries (via an SQLite database) and fast narrative responses (via pre-filtered ChromaDB vector store RAG).

## Installation & Setup

1. **Clone & Navigate**:
   ```bash
   cd sustally
   ```

2. **Initialize Environment**:
   Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## LLM Configuration

Sustally supports different LLM providers depending on the deployment environment:
- **Local Development**: Set `LLM_PROVIDER=ollama` in your `.env`. Make sure Ollama is running locally with the configured model (default: `qwen2.5:7b`).
- **Cloud Deployment (Streamlit Community Cloud)**: Set `LLM_PROVIDER=grok` and provide `GROK_API_KEY` via the platform's secrets manager. Ollama cannot run on Streamlit Cloud, so Grok serves as the cloud LLM provider.

## Running the App

### Normal Local Mode
To launch the Streamlit frontend dashboard locally:
```bash
.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port 8501 --server.headless true
```

### Ingestion CLI
To incrementally ingest raw report files stored under `data/raw_reports/`:
```bash
python run.py --ingest-new
```

---

## Secure Demo Tunneling (ngrok Setup)

Sustally includes a secure, temporary sharing setup for demos using ngrok.

### One-Time Setup:
1. Register/Log in to [ngrok](https://ngrok.com/).
2. Retrieve your authtoken from your ngrok dashboard.
3. Add the authtoken to your local ngrok agent setup:
   ```powershell
   ngrok config add-authtoken <your-authtoken>
   ```

### Running the secure demo:
1. Configure your desired credentials (`DEMO_USER` and `DEMO_PASS`) in `.env`.
2. Run the secure demo script:
   ```powershell
   .\run_demo.ps1
   ```
This starts the Streamlit server, verifies connectivity, launches an authenticated ngrok tunnel on port 8501, and prints the public URL to your console. Press `Ctrl+C` in the console window to stop all processes cleanly.
