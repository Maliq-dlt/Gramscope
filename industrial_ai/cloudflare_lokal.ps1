# ponytail: temporary URL and pinned Windows connector; use a named Tunnel for a stable domain.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'setup_lokal.ps1')
$repoRoot = Split-Path $PSScriptRoot -Parent
$connector = Join-Path $repoRoot '.cache/cloudflared/cloudflared-2026.10.0.exe'
if (-not (Test-Path -LiteralPath $connector)) { throw 'Connector belum tersedia; lihat docs/CLOUDFLARE.md.' }
if ((Get-FileHash -LiteralPath $connector -Algorithm SHA256).Hash.ToLowerInvariant() -ne '86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c') { throw 'Hash connector tidak cocok dengan rilis resmi.' }
$probe = [System.Net.Sockets.TcpClient]::new()
$portOccupied = $false
try { $probe.Connect('127.0.0.1',8765); $portOccupied = $true } catch [System.Net.Sockets.SocketException] {} finally { $probe.Dispose() }
if ($portOccupied) { throw 'Hentikan server studio lama setelah semua pekerjaan selesai, lalu jalankan kembali.' }
$runDir = Join-Path $repoRoot ('.tmp/cloudflare/'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$previous = @{}
foreach ($name in @('INSIGHT_PUBLIC_URL','INSIGHT_HOSTS','INSIGHT_MAX_UPLOAD_MIB')) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
$tunnel = $null
try {
    $tunnel = Start-Process -FilePath $connector -ArgumentList @('tunnel','--no-autoupdate','--url','http://127.0.0.1:8765') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'tunnel.out.log') -RedirectStandardError (Join-Path $runDir 'tunnel.err.log')
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    $publicUrl = $null
    while (-not $publicUrl -and [DateTime]::UtcNow -lt $deadline) {
        if ($tunnel.HasExited) { throw ('Connector berhenti; periksa '+$runDir) }
        $log = Get-Content -LiteralPath (Join-Path $runDir 'tunnel.err.log') -Raw -ErrorAction SilentlyContinue
        if ($log) {
            $match = [regex]::Match([string]$log,'https://[a-z0-9-]+\.trycloudflare\.com\b')
            if ($match.Success) { $publicUrl = $match.Value }
        }
        if (-not $publicUrl) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $publicUrl) { throw ('Cloudflare belum memberi URL; periksa '+$runDir) }
    $env:INSIGHT_PUBLIC_URL = $publicUrl
    $env:INSIGHT_HOSTS = ([uri]$publicUrl).Host+',127.0.0.1,localhost,[::1]'
    $env:INSIGHT_MAX_UPLOAD_MIB = '95'
    @{url=$publicUrl;tunnel_pid=$tunnel.Id;logs=$runDir} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $repoRoot '.tmp/cloudflare/endpoint.json') -Encoding utf8
    Write-Host ('Buka '+$publicUrl+' - Ctrl+C menghentikan server dan Tunnel.')
    & (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -m uvicorn app:app --app-dir $PSScriptRoot --host 127.0.0.1 --port 8765
    if ($LASTEXITCODE -ne 0) { throw ('Studio berhenti dengan exit code '+$LASTEXITCODE) }
} finally {
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id }
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}
