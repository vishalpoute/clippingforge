#Requires -Version 5.1
<#
.SYNOPSIS
    Stop only processes recorded by the current ClipForge launcher.
.DESCRIPTION
    -Preflight reports what would stop without terminating processes or changing
    launcher state. PID-only legacy entries are deliberately not trusted.
#>
[CmdletBinding()]
param([switch]$Preflight)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'launcher-common.ps1')

function Add-LauncherDescendants($Parent, $Snapshot, $Tree) {
    foreach ($child in Get-LauncherChildren $Parent $Snapshot) {
        $Tree.Add($child)
        Add-LauncherDescendants $child $Snapshot $Tree
    }
}

try {
    Invoke-WithLauncherLock {
        if (!(Test-Path -LiteralPath $launcherPidFile)) {
            Write-Host 'No launcher PID file; no processes selected for shutdown.'
            return
        }
        $records = @(Read-LauncherRecords)
        $selected = 0
        # Reverse startup order. Keep the original journal if any stop fails.
        [array]::Reverse($records)
        foreach ($record in $records) {
            $process = Get-OwnedLauncherProcess $record
            if (!$process) { Write-Warning "$($record.Name): stale or mismatched PID $($record.Id); left alone."; continue }
            $tree = New-Object 'System.Collections.Generic.List[System.Diagnostics.Process]'
            $tree.Add($process)
            try {
                Add-LauncherDescendants $process @(Get-LauncherProcessSnapshot) $tree
                $selected++
                if ($Preflight) {
                    Write-Host "$($record.Name): would stop verified PID(s) $($tree.Id -join ', ')."
                    continue
                }
                # Stop supervisors first; the retained handles prevent PID reuse.
                foreach ($member in $tree) {
                    try { if (!$member.HasExited) { Stop-Process -Id $member.Id -Force -ErrorAction Stop } }
                    catch { if (!$member.HasExited) { throw } }
                }
                foreach ($member in $tree) {
                    if (!$member.WaitForExit(5000)) { throw "PID $($member.Id) did not exit." }
                }
                Write-Host "$($record.Name): stopped verified PID(s) $($tree.Id -join ', ')."
            } finally {
                foreach ($member in $tree) { $member.Dispose() }
            }
        }
        if ($Preflight) {
            Write-Host "Stop preflight passed; $selected verified service record(s). No processes stopped or launcher state changed."
        } elseif ($records.Count) {
            Remove-Item -LiteralPath $launcherPidFile
        } else {
            Write-Host 'No verified launcher records; existing processes and PID file left alone.'
        }
    }
} catch {
    Write-Error -ErrorAction Continue $_
    exit 1
}
