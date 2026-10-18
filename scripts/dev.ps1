param([switch]$Demo, [switch]$NoServer)
$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Runtime = Join-Path $env:LOCALAPPDATA 'Temp\opencode\langganin'
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$env:UV_PROJECT_ENVIRONMENT = Join-Path $Runtime 'venv'
$env:LANGGANIN_RUNTIME_DIR = $Runtime
$env:DJANGO_DEBUG = '1'

function Assert-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step gagal, exit code $LASTEXITCODE" }
}
function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).Replace('+','a').Replace('/','b').TrimEnd('=')
}

Push-Location $Project
try {
    uv sync --frozen --link-mode hardlink
    Assert-Exit 'Instalasi Python'
    $SecretsPath = Join-Path $Runtime 'local-secrets.json'
    if (!(Test-Path $SecretsPath)) {
        @{ postgres = (New-Secret); manager = (New-Secret); cashier = (New-Secret) } |
            ConvertTo-Json | Set-Content -Encoding UTF8 $SecretsPath
        # Hanya akun Windows pemilik yang boleh membaca kredensial lokal.
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls.exe $SecretsPath /inheritance:r /grant:r "${identity}:(F)" | Out-Null
        Assert-Exit 'Pembatasan akses kredensial'
    }
    $Secrets = Get-Content $SecretsPath -Raw | ConvertFrom-Json
    $PgBin = if ($env:LANGGANIN_PG_BIN) { $env:LANGGANIN_PG_BIN } else { Join-Path $Project '..\..\.tools\pgsql\bin' }
    if (!(Test-Path (Join-Path $PgBin 'initdb.exe'))) {
        throw 'PostgreSQL tidak ditemukan. Set LANGGANIN_PG_BIN ke direktori bin PostgreSQL portabel.'
    }
    $PgData = Join-Path $Runtime 'postgres'
    if (!(Test-Path (Join-Path $PgData 'PG_VERSION'))) {
        $PasswordFile = Join-Path $Runtime 'pg-init-password'
        try {
            [System.IO.File]::WriteAllText($PasswordFile, $Secrets.postgres)
            & "$PgBin\initdb.exe" -D $PgData -U langganin --encoding=UTF8 --locale=C --auth=scram-sha-256 "--pwfile=$PasswordFile"
            Assert-Exit 'Inisialisasi PostgreSQL'
        } finally { Remove-Item $PasswordFile -ErrorAction SilentlyContinue }
        Add-Content (Join-Path $PgData 'postgresql.conf') "`nlisten_addresses = '127.0.0.1'`nport = 5547`nshared_buffers = '32MB'`nmax_connections = 30"
    }
    & "$PgBin\pg_ctl.exe" status -D $PgData *> $null
    if ($LASTEXITCODE -ne 0) {
        & "$PgBin\pg_ctl.exe" start -D $PgData -l (Join-Path $Runtime 'postgres.log') -w
        Assert-Exit 'Menjalankan PostgreSQL'
    }
    $env:PGPASSWORD = $Secrets.postgres
    $Exists = & "$PgBin\psql.exe" -h 127.0.0.1 -p 5547 -U langganin -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='langganin'"
    Assert-Exit 'Koneksi PostgreSQL'
    if ("$Exists" -ne '1') {
        & "$PgBin\createdb.exe" -h 127.0.0.1 -p 5547 -U langganin langganin
        Assert-Exit 'Pembuatan database'
    }
    Remove-Item Env:PGPASSWORD
    $env:DATABASE_URL = "postgresql://langganin:$($Secrets.postgres)@127.0.0.1:5547/langganin"

    # Port komunitas Windows untuk demo lokal, bukan distribusi Redis resmi.
    $RedisDir = Join-Path $Runtime 'redis-bin'
    $RedisServer = Get-ChildItem $RedisDir -Recurse -Filter 'redis-server.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$RedisServer) {
        $Zip = Join-Path $Runtime 'redis.zip'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/redis-windows/redis-windows/releases/download/8.10.2/Redis-8.10.2-Windows-x64-msys2.zip' -OutFile $Zip
        if ((Get-FileHash $Zip -Algorithm SHA256).Hash -ne '7C8CEBD50347EAA1D9E784DA842ED47A4F33394637835531D6614777B950EE85') {
            throw 'Checksum Redis tidak cocok. Instalasi dihentikan.'
        }
        Expand-Archive -Path $Zip -DestinationPath $RedisDir -Force
        Remove-Item $Zip
        $RedisServer = Get-ChildItem $RedisDir -Recurse -Filter 'redis-server.exe' | Select-Object -First 1
    }
    $RedisBin = $RedisServer.DirectoryName
    if (!(Get-NetTCPConnection -State Listen -LocalPort 6397 -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $RedisServer.FullName -ArgumentList '--bind 127.0.0.1 --port 6397 --protected-mode yes --save "" --appendonly no' -WorkingDirectory $Runtime -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime 'redis.log') -RedirectStandardError (Join-Path $Runtime 'redis-error.log') | Out-Null
        Start-Sleep -Seconds 2
    }
    & "$RedisBin\redis-cli.exe" -h 127.0.0.1 -p 6397 ping
    Assert-Exit 'Koneksi Redis'
    $env:REDIS_URL = 'redis://127.0.0.1:6397/0'
    uv run --frozen manage.py migrate --noinput
    Assert-Exit 'Migrasi database'
    $env:LANGGANIN_MANAGER_PASSWORD = $Secrets.manager
    $env:LANGGANIN_CASHIER_PASSWORD = $Secrets.cashier
    uv run --frozen manage.py setup_roles
    Assert-Exit 'Pembuatan akun'
    Remove-Item Env:LANGGANIN_MANAGER_PASSWORD,Env:LANGGANIN_CASHIER_PASSWORD
    if ($Demo) {
        uv run --frozen manage.py seed_demo
        Assert-Exit 'Data demo'
    }
    Write-Host "`nLangganin: http://127.0.0.1:8017"
    Write-Host "Kredensial lokal tersimpan di $SecretsPath (manager untuk pengelola, cashier untuk kasir)."
    if (!$NoServer) {
        uv run --frozen manage.py runserver 127.0.0.1:8017 --noreload
        Assert-Exit 'Server aplikasi'
    }
} finally { Pop-Location }
