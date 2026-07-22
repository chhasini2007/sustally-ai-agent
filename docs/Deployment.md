# Deployment Guide

This document describes how to deploy the **Sustally ESG Intelligence Platform** to staging or production environments.

---

## 1. Streamlit Community Cloud Deployment (Recommended)

Streamlit Community Cloud is the easiest way to deploy and share the Sustally dashboard. Since it runs in a cloud environment, you must use **OpenAI** as the LLM provider (local Ollama is not accessible).

### Deployment Steps:
1. **Push Code to GitHub**:
   Commit your changes and push the clean repository to a GitHub repository.
2. **Deploy on Streamlit**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
   - Click **New app**.
   - Select your repository, branch (e.g., `master` or `main`), and set the main file path to:
     `app/streamlit_app.py`
3. **Configure Secrets**:
   Before launching, click **Advanced settings** and paste your secrets in the TOML editor under **Secrets**:
   ```toml
   LLM_PROVIDER = "openai"
   OPENAI_API_KEY = "your-actual-openai-api-key-here"
   OPENAI_MODEL = "gpt-4o-mini"
   OPENAI_CONNECT_TIMEOUT = 3
   OPENAI_READ_TIMEOUT = 20

   STREAMLIT_APP_USER = "admin"
   STREAMLIT_APP_PASSWORD = "your-custom-production-password"
   ```
4. **Deploy**: Click **Deploy**. Streamlit will provision the container, install dependencies from `requirements.txt`, and boot the app.

---

## 2. Self-Hosted Virtual Machine (VM) / Server

For production environments requiring data privacy, you can host Sustally on a local VM (e.g., AWS EC2, Azure VM, DigitalOcean) and combine it with Ollama.

### Setup Architecture:
- **Web App Server**: Runs the Streamlit dashboard on port `8501`.
- **LLM Server**: Runs Ollama in the background (or on a dedicated GPU host).
- **Reverse Proxy**: Nginx or Apache to handle SSL termination and route traffic to the Streamlit app.

### VM Deployment Steps:
1. Clone the repository and run the setup commands listed in [Setup.md](Setup.md).
2. Install Ollama on the server and start the service.
3. Configure Systemd to keep Streamlit running:
   Create `/etc/systemd/system/sustally.service`:
   ```ini
   [Unit]
   Description=Sustally ESG Platform
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/sustally
   ExecStart=/home/ubuntu/sustally/.venv/bin/python -m streamlit run app/streamlit_app.py --server.port 8501 --server.headless true
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
4. Start and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sustally.service
   sudo systemctl start sustally.service
   ```

---

## 3. Secure Demo Tunneling (ngrok Setup)

Sustally includes a secure, temporary sharing script (`run_demo.ps1`) for demos or client review from Windows machines using ngrok.

### Prerequisites:
1. Register/Log in to [ngrok.com](https://ngrok.com/).
2. Retrieve your authtoken from your ngrok dashboard.
3. Add the authtoken to your local ngrok configuration:
   ```powershell
   ngrok config add-authtoken <your-authtoken>
   ```

### Running the secure demo:
1. Set the user credentials (`DEMO_USER` and `DEMO_PASS`) in `.env`.
2. Run the secure demo script:
   ```powershell
   .\run_demo.ps1
   ```
This script will start the Streamlit server locally, verify connection, open a secure tunnel, and print the public URL. Close the terminal window or press `Ctrl+C` to terminate the tunnel.
