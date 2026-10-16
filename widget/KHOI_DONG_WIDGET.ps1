# ==============================================================================
#  1-CLICK LAUNCHER: ANTIGRAVITY QUOTA WIDGET (V10 PRO ULTIMATE)
# ==============================================================================
$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $projectDir -or -not (Test-Path "$projectDir\main.py")) {
    $projectDir = $PSScriptRoot
}
if (-not (Test-Path "$projectDir\main.py")) {
    $projectDir = (Get-Location).Path
}

# 1. Đóng cửa sổ widget cũ một cách an toàn
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class AntigravityWidgetCloser {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string className, string windowName);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
}
'@
foreach ($cls in @('AntigravityQuotaWidgetV10Pro')) {
  for ($i = 0; $i -lt 10; $i++) {
    $wnd = [AntigravityWidgetCloser]::FindWindow($cls, $null)
    if ($wnd -eq [IntPtr]::Zero) { break }
    [void][AntigravityWidgetCloser]::PostMessage($wnd, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) # WM_CLOSE
    Start-Sleep -Milliseconds 40
  }
}

# Chỉ đóng tiến trình Python thuộc riêng AntigravityWidget để giải phóng Mutex, tuyệt đối không chạm vào Codex/Cockpit
$escapedDir = [regex]::Escape($projectDir)
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match $escapedDir -or $_.CommandLine -match '(^|[\s"\\])main\.py(\s|"|$)')
} | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 300

# 2. Khởi chạy Antigravity Quota Widget qua pythonw (tìm động trên mọi máy)
$pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pyw) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($py) {
        $cand = Join-Path (Split-Path $py) 'pythonw.exe'
        if (Test-Path $cand) { $pyw = $cand }
    }
}
if (-not $pyw) {
    try {
        $pyPath = (py -c "import sys; print(sys.executable)" 2>$null)
        if ($pyPath) {
            $cand = Join-Path (Split-Path $pyPath.Trim()) 'pythonw.exe'
            if (Test-Path $cand) { $pyw = $cand }
        }
    } catch {}
}
if (-not $pyw) {
    $knownSearch = @(
        "$env:LOCALAPPDATA\Programs\Python\Python*\pythonw.exe",
        "C:\Python*\pythonw.exe",
        "C:\Program Files\Python*\pythonw.exe"
    )
    foreach ($pattern in $knownSearch) {
        $found = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
        if ($found -and (Test-Path $found)) {
            $pyw = $found
            break
        }
    }
}

$mainPyPath = Join-Path $projectDir "main.py"
if ($pyw -and (Test-Path $mainPyPath)) {
  Start-Process -FilePath $pyw -ArgumentList "`"$mainPyPath`"" -WorkingDirectory $projectDir -WindowStyle Hidden
} elseif (Test-Path $mainPyPath) {
  Start-Process -FilePath "python" -ArgumentList "`"$mainPyPath`"" -WorkingDirectory $projectDir -WindowStyle Hidden
}
Start-Sleep -Milliseconds 500

