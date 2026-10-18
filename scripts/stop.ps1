$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Runtime = Join-Path $env:LOCALAPPDATA 'Temp\opencode\langganin'
$PgBin = if ($env:LANGGANIN_PG_BIN) { $env:LANGGANIN_PG_BIN } else { Join-Path $Project '..\..\.tools\pgsql\bin' }
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*manage.py runserver 127.0.0.1:8017*' -and $_.Name -like 'python*' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
if (Test-Path "$Runtime\postgres\postmaster.pid") { & "$PgBin\pg_ctl.exe" stop -D "$Runtime\postgres" -m fast -w }
$RedisCli = Get-ChildItem "$Runtime\redis-bin" -Recurse -Filter 'redis-cli.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($RedisCli) { & $RedisCli.FullName -h 127.0.0.1 -p 6397 shutdown nosave }
