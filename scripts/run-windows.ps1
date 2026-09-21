$ErrorActionPreference = 'Stop'
if (!(Test-Path .venv)) { py -3.11 -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
