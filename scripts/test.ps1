$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Runtime = Join-Path $env:LOCALAPPDATA 'Temp\opencode\langganin'
$Secrets = Get-Content (Join-Path $Runtime 'local-secrets.json') -Raw | ConvertFrom-Json
$env:UV_PROJECT_ENVIRONMENT = Join-Path $Runtime 'venv'
$env:LANGGANIN_RUNTIME_DIR = $Runtime
$env:LANGGANIN_STATIC_ROOT = Join-Path $Runtime 'staticfiles'
$env:DJANGO_DEBUG = '1'
$env:DATABASE_URL = "postgresql://langganin:$($Secrets.postgres)@127.0.0.1:5547/langganin"
$env:REDIS_URL = 'redis://127.0.0.1:6397/1'
Push-Location $Project
try {
    uv run --frozen manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Pengumpulan aset gagal' }
    uv run --frozen manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Migrasi tidak sinkron' }
    uv run --frozen manage.py test --settings=config.test_settings --noinput -v 2
    if ($LASTEXITCODE -ne 0) { throw 'Pengujian gagal' }
    $env:DJANGO_DEBUG = '0'
    $env:DJANGO_SECRET_KEY = Get-Content (Join-Path $Runtime 'secret.key') -Raw
    uv run --frozen manage.py check --deploy
    if ($LASTEXITCODE -ne 0) { throw 'Pemeriksaan deployment gagal' }
} finally { Pop-Location }
