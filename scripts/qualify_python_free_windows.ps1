# Run inside an unmodified Microsoft Windows Server Core container.
$ErrorActionPreference = 'Stop'
$result = [ordered]@{ status = 'failed'; environment = 'Windows Server Core container'; pythonInstalled = $null; checks = @() }
try {
    $result.osVersion = [Environment]::OSVersion.VersionString
    $commands = @(Get-Command python, python3, py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    $registrations = @(@('HKLM:\Software\Python', 'HKCU:\Software\Python', 'HKLM:\Software\WOW6432Node\Python') | Where-Object { Test-Path -LiteralPath $_ })
    $interpreters = @(Get-ChildItem -LiteralPath 'C:\' -Filter 'python*.exe' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $result.pythonCommands = $commands
    $result.pythonRegistry = $registrations
    $result.pythonExecutables = $interpreters
    $result.pythonInstalled = ($commands.Count -gt 0 -or $registrations.Count -gt 0 -or $interpreters.Count -gt 0)
    if ($result.pythonInstalled) { throw 'The container unexpectedly contains an installed Python interpreter.' }
    Copy-Item -LiteralPath 'C:\Inputs\Application' -Destination 'C:\Application' -Recurse
    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    Set-Location C:\
    $binary = 'C:\Application\SwirProfileDemo.exe'
    foreach ($attempt in 1..2) {
        $stdout = & $binary 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
        $passed = $exitCode -eq 0 -and $stdout.Contains('Maxkompilator: build and resource check OK')
        $result.checks += [ordered]@{ attempt = $attempt; sha256 = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLower(); exitCode = $exitCode; stdout = $stdout.Trim(); passed = $passed }
        if (-not $passed) { throw 'Application or bundled resource failed in the Python-free container.' }
    }
    $result.status = 'passed'
} catch { $result.error = $_.Exception.Message }
$result.completedUtc = [DateTime]::UtcNow.ToString('o')
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath C:\Results\python-free-windows.json -Encoding UTF8
$result | ConvertTo-Json -Depth 8
if ($result.status -ne 'passed') { exit 1 }
