$env:GOOGLE_CLIENT_ID     = "your_client_id_here"
$env:GOOGLE_CLIENT_SECRET = "your_client_secret_here"
Write-Host ""
Write-Host "  NOC Portal starting..."
Write-Host "  Open your browser at: http://localhost:5000"
Write-Host ""
python app.py
