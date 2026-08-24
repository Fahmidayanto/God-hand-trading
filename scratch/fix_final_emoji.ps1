# Fix 6 spot emoji terakhir (ASCII-safe)
$ErrorActionPreference = "Stop"
function E([int]$cp) { return [char]::ConvertFromUtf32($cp) }

# rongsokan.tsx:1950 -> ✍️ (270D FE0F) sudah pernah diganti? ternyata masih; ganti PenLine
$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\rongsokan.tsx"
$text = [System.IO.File]::ReadAllText($f)
$k = (E 0x270D) + (E 0xFE0F) + " Drawing Structure Lines"
if ($text.Contains($k)) {
    $text = $text.Replace($k, '<PenLine size={14} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Drawing Structure Lines')
    [System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output "rongsokan: OK"
} else { Write-Output "rongsokan: pola tidak ketemu" }

# trades.tsx:2163 -> 💼 Briefcase
$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\trades.tsx"
$text = [System.IO.File]::ReadAllText($f)
$k = '<span>' + (E 0x1F4BC) + '</span> Recent Trades'
if ($text.Contains($k)) {
    $text = $text.Replace($k, '<Briefcase size={16} aria-hidden="true" /> Recent Trades')
    [System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output "trades: OK"
} else { Write-Output "trades: pola tidak ketemu" }

# DraggableLayout.tsx: 🔓🔓 Toggle, 🔄 Reset, 🖱️ Edit Mode Active
$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\DraggableLayout.tsx"
$text = [System.IO.File]::ReadAllText($f)
$n = 0
$unlock = E 0x1F513; $lock = E 0x1F512
$k1 = '"' + $unlock + ' Edit Mode" : "' + $lock + ' Lock Layout"'
$v1 = '"Edit Mode" : "Lock Layout"'
if ($text.Contains($k1)) { $text = $text.Replace($k1, $v1); $n++ }
$k2 = (E 0x1F504) + " Reset"
if ($text.Contains($k2)) { $text = $text.Replace($k2, '<RotateCcw size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Reset'); $n++ }
$k3 = (E 0x1F5B1) + (E 0xFE0F) + " Edit Mode Active"
if ($text.Contains($k3)) { $text = $text.Replace($k3, '<MousePointer2 size={16} className="inline mr-1.5 -mt-0.5" aria-hidden="true" />Edit Mode Active'); $n++ }
if (-not $text.Contains('lucide-react')) {
    $text = $text.Replace('import { useState, useEffect, useRef } from "react";', 'import { useState, useEffect, useRef } from "react";' + "`n" + 'import { RotateCcw, MousePointer2 } from "lucide-react";')
}
[System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "DraggableLayout: $n penggantian"

# MT5Footer.tsx: ✋⚡ logo teks footer + Built with 💙? (270B=hand, 26A1=zap)
$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\MT5Footer.tsx"
$text = [System.IO.File]::ReadAllText($f)
$n = 0
$k1 = (E 0x270B) + (E 0x26A1)
if ($text.Contains($k1)) { $text = $text.Replace($k1, ''); $n++ }
$heart = E 0x1F499
if ($text.Contains($heart)) { $text = $text.Replace($heart, ''); $n++ }
[System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "MT5Footer: $n penggantian"
