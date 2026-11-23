$launcherRoot = Split-Path -Parent $PSScriptRoot
$launcherPidFile = Join-Path $PSScriptRoot '.pids'

function Invoke-WithLauncherLock([scriptblock]$Action) {
    $mutex = New-Object System.Threading.Mutex($false, 'Global\ClipForgeLauncher')
    $locked = $false
    try {
        try { $locked = $mutex.WaitOne(0) }
        catch [System.Threading.AbandonedMutexException] { $locked = $true }
        if (!$locked) { throw 'Another ClipForge start or stop is in progress. Try again shortly.' }
        & $Action
    } finally {
        if ($locked) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

function Read-LauncherRecords {
    if (!(Test-Path -LiteralPath $launcherPidFile)) { return }
    foreach ($line in Get-Content -LiteralPath $launcherPidFile) {
        if ($line -match '^(BACKEND|WORKER|FRONTEND|OMNIROUTER)_PID=([1-9][0-9]{0,9})\|([0-9]{1,19})\|([^|]+)$') {
            $processId = 0
            $started = [long]0
            if ([int]::TryParse($Matches[2], [ref]$processId) -and [long]::TryParse($Matches[3], [ref]$started)) {
                [pscustomobject]@{ Name = $Matches[1]; Id = $processId; Started = $started; Image = $Matches[4]; Line = $line }
                continue
            }
        }
        if ($line.Trim()) { Write-Warning "Ignoring unverified PID entry in $launcherPidFile (legacy or malformed)." }
    }
}

function Get-OwnedLauncherProcess($Record) {
    $process = Get-Process -Id $Record.Id -ErrorAction SilentlyContinue
    if (!$process) { return }
    $verified = $false
    try {
        # Open and retain a handle to this process while inspecting or acting on its PID.
        $null = $process.Handle
        $verified = !$process.HasExited -and $process.StartTime.ToUniversalTime().Ticks -eq $Record.Started -and
            $process.Path -eq $Record.Image
        if ($verified) { return $process }
    } catch {
        if (!$process.HasExited) { throw }
    } finally {
        if (!$verified) { $process.Dispose() }
    }
}

function Get-LauncherServices {
    $api = Join-Path $launcherRoot 'services\api'
    $web = Join-Path $launcherRoot 'apps\web'
    $python = Join-Path $api '.venv\Scripts\python.exe'
    $node = (Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    $next = Join-Path $web 'node_modules\next\dist\bin\next'
    $omni = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'npm\node_modules\omniroute\bin\omniroute.mjs'
    [pscustomobject]@{ Name = 'BACKEND'; Exe = $python; Entry = (Join-Path $api 'app\main.py'); Directory = $api; Log = 'backend'; Port = 8000; Url = 'http://127.0.0.1:8000/api/v1/health'; ShouldStart = $false; ImageName = 'python.exe'; Command = ('^"?' + [regex]::Escape($python) + '"?\s+-m\s+uvicorn\s+app\.main:app(?:\s|$)'); Arguments = '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' }
    [pscustomobject]@{ Name = 'WORKER'; Exe = $python; Entry = (Join-Path $api 'app\worker.py'); Directory = $api; Log = 'worker'; Port = $null; Url = $null; ShouldStart = $false; ImageName = 'python.exe'; Command = ('^"?' + [regex]::Escape($python) + '"?\s+-m\s+app\.worker(?:\s|$)'); Arguments = '-m app.worker' }
    $nextServer = Join-Path $web 'node_modules\next\dist\server\lib\start-server.js'
    [pscustomobject]@{ Name = 'FRONTEND'; Exe = $node; Entry = $next; Directory = $web; Log = 'frontend'; Port = 3000; Url = 'http://127.0.0.1:3000/'; ShouldStart = $false; ImageName = 'node.exe'; Command = ('(?:^|\s)"?(?:' + [regex]::Escape($next) + '"?\s+dev(?:\s|$)|' + [regex]::Escape($nextServer) + '"?(?:\s|$))'); Arguments = "`"$next`" dev --hostname 127.0.0.1 --port 3000" }
    $omniServer = Join-Path (Split-Path -Parent (Split-Path -Parent $omni)) 'dist\server-ws.mjs'
    [pscustomobject]@{ Name = 'OMNIROUTER'; Exe = $node; Entry = $omni; Directory = $launcherRoot; Log = 'omniroute'; Port = 20128; Url = 'http://127.0.0.1:20128/api/health'; ShouldStart = $false; ImageName = 'node.exe'; Command = ('(?:^|\s)"?(?:' + [regex]::Escape($omni) + '"?\s+serve(?:\s|$)|' + [regex]::Escape($omniServer) + '"?(?:\s|$))'); Arguments = "`"$omni`" serve --no-open --no-tray --port 20128" }
}

function Get-LauncherProcessSnapshot {
    Get-CimInstance -ClassName Win32_Process -Property ProcessId,ParentProcessId,CreationDate,Name,ExecutablePath,CommandLine
}

function Test-LauncherCommand($Service, $ProcessInfo) {
    $ProcessInfo.Name -eq $Service.ImageName -and $ProcessInfo.CommandLine -match $Service.Command
}

function Get-LauncherChildren($Parent, $ProcessSnapshot) {
    $parentStarted = $Parent.StartTime.ToUniversalTime().Ticks
    foreach ($candidate in $ProcessSnapshot) {
        if ($candidate.ParentProcessId -ne $Parent.Id -or !$candidate.CreationDate -or !$candidate.ExecutablePath) { continue }
        $created = $candidate.CreationDate.ToUniversalTime().Ticks
        if ($created -lt $parentStarted) { continue }
        # CIM rounds creation times to microseconds; verify that exact precision against the live process.
        $child = Get-Process -Id $candidate.ProcessId -ErrorAction SilentlyContinue
        if (!$child) { continue }
        $verified = $false
        try {
            $null = $child.Handle
            if ($child.HasExited -or $child.Path -ne $candidate.ExecutablePath) { continue }
            $difference = $child.StartTime.ToUniversalTime().Ticks - $created
            if ($difference -lt 0 -or $difference -ge 10) { continue }
            $verified = $true
            $child
        } catch {
            if (!$child.HasExited) { throw }
        } finally {
            if (!$verified) { $child.Dispose() }
        }
    }
}
