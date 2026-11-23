$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$path = Join-Path ([Environment]::GetFolderPath('Desktop')) 'ClipForge.lnk'
$shortcut = $shell.CreateShortcut($path)
$root = Split-Path -Parent $PSScriptRoot
$shortcut.TargetPath = Join-Path $root 'START_CLIPFORGE.bat'
$shortcut.Arguments = ''
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 1
$shortcut.Description = 'Start ClipForge AI in the default browser'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,0"
$shortcut.Save()
Write-Host "Created $path"
