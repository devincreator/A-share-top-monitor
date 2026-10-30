$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python prepare_data.py
if ($LASTEXITCODE -ne 0) { throw 'Data preparation failed' }
node build_model.cjs
if ($LASTEXITCODE -ne 0) { throw 'Model verification failed' }
python build_page.py
if ($LASTEXITCODE -ne 0) { throw 'Page build failed' }
Write-Output (Join-Path $PSScriptRoot 'index.html')
