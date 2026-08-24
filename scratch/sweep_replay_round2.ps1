# Round-2 (ASCII-safe): ganti emoji tersisa di replay.tsx & replay-original.tsx
$ErrorActionPreference = "Stop"
$files = @(
    "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay.tsx",
    "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay-original.tsx"
)

function E([int]$cp) { return [char]::ConvertFromUtf32($cp) }
$CLAP = E 0x1F3AC; $PIN = E 0x1F4CD; $TGT = E 0x1F3AF
$SHLD = (E 0x1F6E1) + (E 0xFE0F); $CLK = (E 0x23F1) + (E 0xFE0F)
$MOV = E 0x2722; $SCIS = (E 0x2702) + (E 0xFE0F)
$ZAP = E 0x26A1; $BOT = E 0x1F916; $BRAIN = E 0x1F9E0; $BULB = E 0x1F4A1
$CHK = E 0x2713; $CRS = E 0x2717; $CHRT = E 0x1F4CA; $PACK = E 0x1F4E6
$MNY = E 0x1F4B0; $WARN = (E 0x26A0) + (E 0xFE0F); $GEAR = (E 0x2699) + (E 0xFE0F)
$TAG = (E 0x1F3F7) + (E 0xFE0F); $SCL = (E 0x2696) + (E 0xFE0F); $STAR = E 0x2B50
$CLIP = E 0x1F4CB; $CAL = E 0x1F4C5

$lineMap = [ordered]@{}
$lineMap[$CLAP] = '<Clapperboard size={18} strokeWidth={1.8} aria-hidden="true" className="text-[var(--text-primary)]" />'
$lineMap[($PIN + ' Candle')] = '<MapPin size={9} className="inline mr-0.5 -mt-px" aria-hidden="true" />Candle'
$lineMap[($TGT + ' Target TP:</span>')] = '<Target size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Target TP:</span>'
$lineMap[($SHLD + ' Stop Loss:</span>')] = '<Shield size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Stop Loss:</span>'
$lineMap[($CLK + ' Lebar Waktu:</span>')] = '<Clock3 size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Lebar Waktu:</span>'
$lineMap[($MOV + ' Pindah Posisi Bebas:</span>')] = '<Move size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Pindah Posisi Bebas:</span>'
$lineMap[($PIN + ' Entry Level:</span>')] = 'Entry Level:</span>'
$lineMap[($SCIS + ' Klik untuk memotong replay ke titik ini (Esc untuk batal)')] = '<Scissors size={11} className="inline mr-1 -mt-px" aria-hidden="true" />Klik untuk memotong replay ke titik ini (Esc untuk batal)'
$lineMap[($ZAP + ' Daftar Posisi')] = '<Zap size={14} className="inline shrink-0" aria-hidden="true" /> Daftar Posisi'
$lineMap[$BOT] = '<Bot size={15} aria-hidden="true" />'
$lineMap[($BRAIN + ' Analisis Sekarang (LLM)')] = '<Brain size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Analisis Sekarang (LLM)'
$lineMap[($BULB + '</span> Analisis & Pertimbangan AI:')] = '<Lightbulb size={13} className="inline mr-1 -mt-px" aria-hidden="true" /> Analisis & Pertimbangan AI:'
$lineMap[($CHRT + ' TOTAL REKAPITULASI:</span>')] = '<BarChart3 size={12} className="inline mr-1 -mt-px" aria-hidden="true" />TOTAL REKAPITULASI:</span>'
$lineMap[($TGT + ' Total Posisi')] = '<Target size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Total Posisi'
$lineMap[($CHRT + ' Win Rate')] = '<BarChart3 size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Win Rate'
$lineMap[($PACK + ' Volume Lot')] = '<Package size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Volume Lot'
$lineMap[($MNY + ' Total Net Profit')] = '<Wallet size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Total Net Profit'
$lineMap[($GEAR + ' SmartRule Engine')] = '<Settings size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />SmartRule Engine'
$lineMap[($BRAIN + ' LLM 7-Step Reasoning')] = '<Brain size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />LLM 7-Step Reasoning'
$lineMap[($BOT + ' Gunakan LLM untuk SL/TP/Lot')] = '<Bot size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Gunakan LLM untuk SL/TP/Lot'
$lineMap[($TAG + ' Visual Supply')] = '<Tag size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Visual Supply'
$lineMap[($TGT + ' Visual Liquidity Pools (BSL / SSL)')] = '<Target size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Visual Liquidity Pools (BSL / SSL)'
$lineMap[($SCL + ' Price-Ratio Dynamic Scaling (Opsi 1)')] = '<Scale size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Price-Ratio Dynamic Scaling (Opsi 1)'
$lineMap[($ZAP + '</span> Quick Presets Range Emas (Data Teruji)')] = '<Zap size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Quick Presets Range Emas (Data Teruji)'
$lineMap[($CLIP + ' Monthly Performance Summary</h2>')] = '<ClipboardList size={18} aria-hidden="true" /> Monthly Performance Summary</h2>'
$lineMap[($CAL + ' Loading Replay Data')] = '<Loader2 size={14} className="inline animate-spin mr-1.5 -mt-0.5" aria-hidden="true" />Loading Replay Data'
$lineMap[($WARN + ' {disabledReason}</div>')] = '<AlertTriangle size={10} className="shrink-0 inline mr-1 -mt-px" aria-hidden="true" /> {disabledReason}</div>'
$lineMap[($CLAP + '</span>')] = '<Clapperboard size={44} strokeWidth={1.5} aria-hidden="true" className="opacity-70 mx-auto" />'

$subMap = [ordered]@{}
$subMap[($SCIS + ')')] = ')'
$subMap['(TradingView ' + $SCIS] = '(TradingView'
$subMap[('=> `' + $ZAP + ' ${s}`')] = '=> $s'
$subMap[($TGT + ' EQH')] = 'EQH'
$subMap[($TGT + ' EQL')] = 'EQL'
$subMap[($TGT + ' BSL')] = 'BSL'
$subMap[($TGT + ' SSL')] = 'SSL'
$subMap['label="' + $SHLD] = 'label="'
$subMap['label="' + $TAG] = 'label="'
$subMap[('Garis Cyan ' + $TGT)] = 'Garis Cyan'
$subMap[('Orange ' + $TGT)] = 'Orange'
$subMap['badge: "' + $STAR] = 'badge: "'
$subMap[($CHK + ' Eksekusi')] = 'Eksekusi'
$subMap[($CRS + ' Tolak')] = 'Tolak'

foreach ($f in $files) {
    if (-not (Test-Path $f)) { continue }
    $lines = [System.IO.File]::ReadAllLines($f)
    $nLines = 0
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $trim = $lines[$i].Trim()
        if ($lineMap.Contains($trim)) {
            $indent = $lines[$i].Substring(0, $lines[$i].Length - $lines[$i].TrimStart().Length)
            $lines[$i] = $indent + $lineMap[$trim]
            $nLines++
        }
    }
    $text = ($lines -join "`n") + "`n"
    $nSub = 0
    foreach ($k in $subMap.Keys) {
        $c = [regex]::Matches($text, [regex]::Escape($k)).Count
        if ($c -gt 0) { $text = $text.Replace($k, $subMap[$k]); $nSub += $c }
    }
    $m = [regex]::Match($text, 'import \{ ([^}]+) \} from "lucide-react";')
    if ($m.Success) {
        $need = @("Clapperboard","MapPin","Shield","Clock3","Move","Zap","Bot","Brain","Lightbulb","Check","X","BarChart3","Package","Wallet","Tag","Scale","ClipboardList","AlertTriangle","Loader2")
        $have = $m.Groups[1].Value -split ",\s*" | ForEach-Object { $_.Trim() }
        $missing = $need | Where-Object { $have -notcontains $_ }
        if ($missing.Count -gt 0) {
            $newImport = 'import { ' + (($have + $missing) -join ", ") + ' } from "lucide-react";'
            $text = $text.Replace($m.Value, $newImport)
        }
    }
    [System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output ("{0}: {1} baris, {2} substring" -f (Split-Path $f -Leaf), $nLines, $nSub)
}
