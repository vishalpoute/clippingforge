#Requires -Version 5.1
<#
.SYNOPSIS
    Start the local ClipForge stack using the existing dependencies.
.DESCRIPTION
    -Preflight checks dependencies, listeners and the worker without starting
    services, opening a browser, or writing launcher state. -SkipOmniRouter skips
    local OmniRouter startup and checks. -NoBrowser leaves the browser closed.
#>
[CmdletBinding()]
param([switch]$Preflight, [switch]$NoBrowser, [switch]$SkipOmniRouter)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'launcher-common.ps1')
$services = Get-LauncherServices

function Test-LauncherHealth($Service) {
    $request = [Net.HttpWebRequest]::Create($Service.Url)
    $request.Proxy = $null
    $request.AllowAutoRedirect = $false
    $request.Timeout = 3000
    $request.ReadWriteTimeout = 3000
    if ($Service.Name -eq 'FRONTEND') { $request.Method = 'HEAD' }
    try {
        $response = $request.GetResponse()
        try {
            if ([int]$response.StatusCode -ne 200) { return $false }
            if ($Service.Name -eq 'FRONTEND') { return ($response.Headers['X-Powered-By'] -eq 'Next.js') }
            $reader = New-Object IO.StreamReader($response.GetResponseStream())
            try { return (($reader.ReadToEnd() | ConvertFrom-Json -ErrorAction Stop).status -eq 'ok') }
            finally { $reader.Dispose() }
        } finally { $response.Dispose() }
    } catch {
        if ($_.Exception.InnerException -is [Net.WebException] -and $_.Exception.InnerException.Response) {
            $_.Exception.InnerException.Response.Dispose()
        }
        return $false
    }
}

function Start-LauncherService($Service) {
    $log = Join-Path $PSScriptRoot $Service.Log
    $process = Start-Process -FilePath $Service.Exe -ArgumentList $Service.Arguments `
        -WorkingDirectory $Service.Directory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$log.log" -RedirectStandardError "$log.err.log"
    try {
        $started = $process.StartTime.ToUniversalTime().Ticks
        if ($process.HasExited) { throw "$($Service.Name) exited immediately. See $log.err.log." }
        $image = $null
        # Windows can briefly omit executable metadata right after Start-Process.
        for ($attempt = 0; $attempt -lt 20 -and !$image; $attempt++) {
            if ($process.HasExited) { throw "$($Service.Name) exited during startup. See $log.err.log." }
            $process.Refresh()
            $image = $process.Path
            if (!$image) {
                $identity = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
                if (Test-LauncherCommand $Service $identity) { $image = $identity.ExecutablePath }
            }
            if (!$image) { Start-Sleep -Milliseconds 100 }
        }
        if (!$image) { throw "Could not verify the executable for PID $($process.Id). See $log.err.log." }
        '{0}_PID={1}|{2}|{3}' -f $Service.Name, $process.Id, $started, $image |
            Add-Content -LiteralPath $launcherPidFile -Encoding UTF8
        Write-Host "$($Service.Name): started PID $($process.Id)."
    } finally { $process.Dispose() }
}

function Wait-LauncherServices($Pending, [int]$Seconds) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($Pending.Count -and $timer.Elapsed.TotalSeconds -lt $Seconds) {
        $Pending = @($Pending | Where-Object { !(Test-LauncherHealth $_) })
        if ($Pending.Count) { Start-Sleep -Milliseconds 500 }
    }
    return $Pending
}

try {
    Invoke-WithLauncherLock {
        $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop)
        $processes = @(Get-LauncherProcessSnapshot)
        $pythonModulesPresent = $false
        $python = $services[0].Exe
        if (Test-Path -LiteralPath $python -PathType Leaf) {
            $null = & $python -B -c 'from importlib.util import find_spec; import sys; sys.exit(not all(find_spec(name) for name in sys.argv[1:]))' uvicorn fastapi
            $pythonModulesPresent = $LASTEXITCODE -eq 0
        }
        $missing = @()
        $blocked = @()
        $pendingCore = @()
        $router = $null
        $routerReady = $false
        foreach ($service in $services) {
            $optional = $service.Name -eq 'OMNIROUTER'
            if ($optional -and $SkipOmniRouter) { Write-Host 'OMNIROUTER: skipped.'; continue }
            $matching = @($processes | Where-Object { Test-LauncherCommand $service $_ })
            $portListeners = @($listeners | Where-Object LocalPort -eq $service.Port)
            $listening = $portListeners.Count -gt 0
            $matchingListener = @($portListeners | Where-Object OwningProcess -in $matching.ProcessId).Count -gt 0
            # A request to a Next.js dev route can compile it and write build output.
            $frontendPreflight = $Preflight -and $service.Name -eq 'FRONTEND'
            $ready = if ($frontendPreflight) {
                $matchingListener
            } elseif ($service.Port) {
                $listening -and (Test-LauncherHealth $service)
            } else { $matching.Count -gt 0 }
            $canStart = $service.Exe -and (Test-Path -LiteralPath $service.Exe -PathType Leaf) -and
                (Test-Path -LiteralPath $service.Entry -PathType Leaf) -and
                ($service.ImageName -ne 'python.exe' -or $pythonModulesPresent)
            $dependency = if ($canStart) { 'present' } else { 'missing' }
            if ($ready) {
                $check = if ($frontendPreflight) { 'matching Next.js listener; no HTTP probe' } else { 'HTTP 200' }
                if ($service.Port) { Write-Host "$($service.Name): reusing listener on port $($service.Port) ($check); launch prerequisites $dependency." }
                else { Write-Host "$($service.Name): reusing matching PID(s) $($matching.ProcessId -join ', '); launch prerequisites $dependency." }
                if ($optional) { $routerReady = $true }
                continue
            }
            if ($listening -and !$matchingListener) {
                $reason = "port $($service.Port) is occupied and did not pass the health check; not touching the listener."
                if ($optional) { Write-Warning "OMNIROUTER: $reason Continuing with core only." }
                else { $blocked += "$($service.Name): $reason" }
                continue
            }
            if (!$matching.Count -and !$canStart) {
                $reason = "missing executable or entry point (exe: $($service.Exe); entry: $($service.Entry))."
                if ($optional) { Write-Warning "OMNIROUTER: $reason Continuing with core only." }
                else { $missing += "$($service.Name): $reason" }
                continue
            }
            $service.ShouldStart = !$matching.Count
            $plan = if ($service.ShouldStart) { 'would start' } else { 'matching process already exists; would wait for readiness' }
            Write-Host "$($service.Name): $plan."
            if ($optional) { $router = $service } else { $pendingCore += $service }
        }
        if ($missing.Count -or $blocked.Count) { throw (($missing + $blocked) -join [Environment]::NewLine) }
        if ($Preflight) { Write-Host 'Start preflight passed; no services started, browser opened, or launcher state changed.'; return }

        foreach ($service in $pendingCore) {
            if ($service.ShouldStart) { Start-LauncherService $service }
        }
        if ($router -and $router.ShouldStart) {
            try { Start-LauncherService $router }
            catch { Write-Warning "OMNIROUTER: $($_.Exception.Message) Continuing with core only."; $router = $null }
        }
        $unready = @(Wait-LauncherServices @($services | Where-Object { $_.Port -and $_.Name -ne 'OMNIROUTER' }) 120)
        if ($unready.Count) { throw "Not ready: $($unready.Name -join ', '). See logs in $PSScriptRoot." }
        if (!(Get-LauncherProcessSnapshot | Where-Object { Test-LauncherCommand $services[1] $_ } | Select-Object -First 1)) {
            throw "Worker is not running. See worker logs in $PSScriptRoot."
        }
        if ($router) {
            $routerReady = !( @(Wait-LauncherServices @($router) 10).Count )
            if (!$routerReady) { Write-Warning 'OmniRouter did not become ready; continuing with core only.' }
        }
        Write-Host 'ClipForge core is ready at http://localhost:3000/.'
        if (!$NoBrowser) {
            Start-Process 'http://localhost:3000/'
            if ($routerReady) { Start-Process 'http://localhost:20128/' }
        }
    }
} catch {
    Write-Error -ErrorAction Continue $_
    exit 1
}
