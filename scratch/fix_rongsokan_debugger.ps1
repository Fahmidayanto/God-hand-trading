# Ganti emoji tersisa di rongsokan.tsx dan LayoutDebugger.tsx
$ErrorActionPreference = "Stop"

$f1 = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\rongsokan.tsx"
$text = [System.IO.File]::ReadAllText($f1)
$pairs = @(
    @([char]::ConvertFromUtf32(0x1F50B), '<BatteryCharging size={26} aria-hidden="true" className="text-[var(--text-primary)]" />'),
    @([char]::ConvertFromUtf32(0x1F4C5), '<Loader2 size={14} className="inline animate-spin shrink-0" aria-hidden="true" /> '),
    @([char]::ConvertFromUtf32(0x270D) + [char]::ConvertFromUtf32(0xFE0F), '<PenLine size={14} className="inline shrink-0" aria-hidden="true" /> ')
)
$n = 0
foreach ($p in $pairs) {
    $c = [regex]::Matches($text, [regex]::Escape($p[0])).Count
    if ($c -gt 0) { $text = $text.Replace($p[0], $p[1]); $n += $c }
}
if (-not $text.Contains('from "lucide-react"')) {
    $text = $text.Replace('import Particles from "@tsparticles/react";', 'import { BatteryCharging, Loader2, PenLine } from "lucide-react";' + "`r`n" + 'import Particles from "@tsparticles/react";')
    Write-Output "Import lucide-react ditambahkan"
}
[System.IO.File]::WriteAllText($f1, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "rongsokan.tsx: $n penggantian"

$f2 = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\LayoutDebugger.tsx"
$t2 = [System.IO.File]::ReadAllText($f2)
$mag = [char]::ConvertFromUtf32(0x1F50D)
if ($t2.Contains($mag)) {
    $t2 = $t2.Replace($mag, '').Replace('title="Toggle Layout Debugger"', 'title="Toggle Layout Debugger"').Replace('        Layout Debug', '        <Search size={13} className="inline mr-1.5 -mt-0.5" aria-hidden="true" />Layout Debug')
    if (-not $t2.Contains('lucide-react')) {
        $t2 = $t2.Replace('import { useState } from "react";', 'import { useState } from "react";' + "`r`n" + 'import { Search } from "lucide-react";')
    }
    [System.IO.File]::WriteAllText($f2, $t2, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output "LayoutDebugger.tsx: diganti"
} else {
    Write-Output "LayoutDebugger.tsx: tidak ada emoji"
}
