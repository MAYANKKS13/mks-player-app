# Create desktop shortcut pointing directly to the single-file MKS-Player.exe
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "MKS Player.lnk"
$ExePath = "C:\vlc-player-app\dist-single\MKS-Player.exe"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = "C:\vlc-player-app\dist-single"
$Shortcut.Description = "MKS Player"
$Shortcut.IconLocation = "$ExePath,0"
$Shortcut.Save()

Write-Host "MKS Player desktop shortcut successfully pointed to: $ExePath"
