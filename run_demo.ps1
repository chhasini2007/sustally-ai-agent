# run_demo.ps1 - Share running Sustally app securely for a demo

# 1. Load environment variables from .env
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $val = $line.Split("=", 2)
            [System.Environment]::SetEnvironmentVariable($key.Trim(), $val.Trim(), "Process")
        }
    }
}

$user = $env:DEMO_USER
$pass = $env:DEMO_PASS

if (-not $user -or -not $pass) {
    Write-Error "DEMO_USER and DEMO_PASS environment variables must be defined in your .env file."
    exit 1
}

$streamlitProc = $null
$ngrokProc = $null

try {
    # 2. Start Streamlit app
    Write-Host "Starting Streamlit app..." -ForegroundColor Yellow
    $streamlitProc = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m streamlit run app/streamlit_app.py --server.port 8501 --server.headless true" -PassThru -NoNewWindow
    
    # 3. Poll Streamlit port 8501 until reachable
    Write-Host "Waiting for Streamlit server to start on port 8501..." -ForegroundColor Yellow
    $isReachable = $false
    while (-not $isReachable) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                $isReachable = $true
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Write-Host "Streamlit server is ready!" -ForegroundColor Green

    # 4. Start ngrok tunnel with Basic Authentication
    Write-Host "Starting ngrok tunnel..." -ForegroundColor Yellow
    $ngrokArgs = "http 8501 --basic-auth=""$($user):$($pass)"""
    $ngrokProc = Start-Process -FilePath "ngrok" -ArgumentList $ngrokArgs -PassThru -NoNewWindow

    # 5. Fetch public ngrok URL from local API endpoint
    Start-Sleep -Seconds 3
    $ngrokUrl = $null
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $apiResp = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels"
            $ngrokUrl = $apiResp.tunnels[0].public_url
            if ($ngrokUrl) { break }
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if ($ngrokUrl) {
        Write-Host "`n===============================================" -ForegroundColor Green
        Write-Host " Sustally Secure Demo Tunnel is ACTIVE!" -ForegroundColor Green
        Write-Host " Public URL:   $ngrokUrl" -ForegroundColor Cyan
        Write-Host " Credentials:  Username: $user | Password: $pass" -ForegroundColor Cyan
        Write-Host "===============================================" -ForegroundColor Green
    } else {
        Write-Error "Could not retrieve public URL from ngrok local API. Verify ngrok is authenticated."
    }

    # Keep script alive until Ctrl+C
    Write-Host "`nPress Ctrl+C to stop the demo tunnel..." -ForegroundColor Yellow
    while ($true) {
        Start-Sleep -Seconds 1
    }

} finally {
    Write-Host "`nTerminating server processes cleanly..." -ForegroundColor Red
    if ($streamlitProc) {
        Stop-Process -Id $streamlitProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($ngrokProc) {
        Stop-Process -Id $ngrokProc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "All processes stopped. Demo session finished." -ForegroundColor Green
}
