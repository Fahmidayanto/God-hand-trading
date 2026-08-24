# Sweep emoji -> Lucide untuk replay.tsx dan replay-original.tsx
# Semua emoji dibangun via ConvertFromUtf32 agar aman dari encoding shell.
$ErrorActionPreference = "Stop"
$files = @(
    "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay.tsx",
    "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay-original.tsx"
)

$e_clap   = [char]::ConvertFromUtf32(0x1F3AC)  # clapper
$e_pin    = [char]::ConvertFromUtf32(0x1F4CD)  # round pushpin
$e_target = [char]::ConvertFromUtf32(0x1F3AF)  # bullseye
$e_shield = [char]::ConvertFromUtf32(0x1F6E1) + [char]::ConvertFromUtf32(0xFE0F)
$e_clock  = [char]::ConvertFromUtf32(0x23F1) + [char]::ConvertFromUtf32(0xFE0F)
$e_move   = [char]::ConvertFromUtf32(0x2722)  # four club symbol
$e_scis   = [char]::ConvertFromUtf32(0x2702) + [char]::ConvertFromUtf32(0xFE0F)
$e_zap    = [char]::ConvertFromUtf32(0x26A1)
$e_bot    = [char]::ConvertFromUtf32(0x1F916)
$e_brain  = [char]::ConvertFromUtf32(0x1F9E0)
$e_bulb   = [char]::ConvertFromUtf32(0x1F4A1)
$e_check  = [char]::ConvertFromUtf32(0x2713)
$e_cross  = [char]::ConvertFromUtf32(0x2717)
$e_chart  = [char]::ConvertFromUtf32(0x1F4CA)
$e_pack   = [char]::ConvertFromUtf32(0x1F4E6)
$e_money  = [char]::ConvertFromUtf32(0x1F4B0)
$e_warn   = [char]::ConvertFromUtf32(0x26A0) + [char]::ConvertFromUtf32(0xFE0F)
$e_gear   = [char]::ConvertFromUtf32(0x2699) + [char]::ConvertFromUtf32(0xFE0F)
$e_tag    = [char]::ConvertFromUtf32(0x1F3F7) + [char]::ConvertFromUtf32(0xFE0F)
$e_scale  = [char]::ConvertFromUtf32(0x2696) + [char]::ConvertFromUtf32(0xFE0F)
$e_star   = [char]::ConvertFromUtf32(0x2B50)
$e_clip   = [char]::ConvertFromUtf32(0x1F4CB)
$e_cal    = [char]::ConvertFromUtf32(0x1F4C5)

$pairs = @(
    @("<span className=`"text-5xl`">$e_clap</span>", '<Clapperboard size={44} strokeWidth={1.5} aria-hidden="true" className="opacity-70 mx-auto" />'),
    @("`n            $e_clap`n", "`n            <Clapperboard size={18} strokeWidth={1.8} aria-hidden=`"true`" className=`"text-[var(--text-primary)]`" />`n"),
    @("<span>$e_pin Candle</span>", '<MapPin size={9} className="inline mr-0.5 -mt-px" aria-hidden="true" />Candle'),
    @('<span className="text-xs">' + "$e_pin" + ' Entry Level:</span>', '<MapPin size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span className="text-xs">Entry Level:</span>'),
    @("<span>$e_target Target TP:</span>", '<Target size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Target TP:</span>'),
    @("<span>$e_shield Stop Loss:</span>", '<Shield size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Stop Loss:</span>'),
    @("<span>$e_clock Lebar Waktu:</span>", '<Clock3 size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Lebar Waktu:</span>'),
    @("<span>$e_move Pindah Posisi Bebas:</span>", '<Move size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" /><span>Pindah Posisi Bebas:</span>'),
    @("$e_scis Klik untuk memotong replay ke titik ini", '<Scissors size={11} className="inline mr-1 -mt-px" aria-hidden="true" />Klik untuk memotong replay ke titik ini'),
    @('title="Jump to Bar (TradingView ' + "$e_scis" + ')"', 'title="Jump to Bar (TradingView)"'),
    @("$e_zap" + ' Daftar Posisi', '<Zap size={14} className="inline shrink-0" aria-hidden="true" /> Daftar Posisi'),
    @("<span className=`"text-base`">$e_bot</span>", '<Bot size={15} aria-hidden="true" />'),
    @("$e_brain" + ' Analisis Sekarang (LLM)', '<Brain size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Analisis Sekarang (LLM)'),
    @("<span>$e_bulb</span> Analisis &amp; Pertimbangan AI:", '<Lightbulb size={13} className="inline mr-1 -mt-px" aria-hidden="true" /> Analisis &amp; Pertimbangan AI:'),
    @('<span class="x-check-tmp">' + "$e_check" + '</span>', '__CHECK_TMP__'),
    @("<span>$e_check</span>", '<Check size={12} className="inline shrink-0" aria-hidden="true" />'),
    @("<span>$e_cross</span>", '<X size={12} className="inline shrink-0" aria-hidden="true" />'),
    @("'`$e_check Eksekusi'", "'Eksekusi'"),
    @("'`$e_cross Tolak'", "'Tolak'"),
    @($e_check + ' Eksekusi', 'Eksekusi'),
    @($e_cross + ' Tolak', 'Tolak'),
    @("<span className=`"text-cyan-400`">$e_chart TOTAL REKAPITULASI:</span>", '<span className="text-cyan-400"><BarChart3 size={12} className="inline mr-1 -mt-px" aria-hidden="true" />TOTAL REKAPITULASI:</span>'),
    @("$e_target Total Posisi", '<Target size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Total Posisi'),
    @("$e_chart Win Rate", '<BarChart3 size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Win Rate'),
    @("$e_pack Volume Lot", '<Package size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Volume Lot'),
    @("$e_money Total Net Profit", '<Wallet size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Total Net Profit'),
    @('label="' + "$e_shield" + ' EMA Stretch Filter"', 'label="EMA Stretch Filter"'),
    @('label="' + "$e_shield" + ' BOS Cycle Stage Filter"', 'label="BOS Cycle Stage Filter"'),
    @("$e_gear" + ' SmartRule Engine', '<Settings size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />SmartRule Engine'),
    @("$e_brain" + ' LLM 7-Step Reasoning', '<Brain size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />LLM 7-Step Reasoning'),
    @("$e_bot" + ' Gunakan LLM untuk SL/TP/Lot', '<Bot size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Gunakan LLM untuk SL/TP/Lot'),
    @('label="' + "$e_tag" + ' Visual Supply', 'label="Visual Supply'),
    @("$e_target" + ' Visual Liquidity Pools', '<Target size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Visual Liquidity Pools'),
    @('Garis Cyan ' + "$e_target" + ' BSL', 'Garis Cyan BSL'),
    @('Orange ' + "$e_target" + ' SSL', 'Orange SSL'),
    @("$e_scale" + ' Price-Ratio Dynamic Scaling', '<Scale size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Price-Ratio Dynamic Scaling'),
    @("<span>$e_zap</span> Quick Presets Range Emas", '<Zap size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Quick Presets Range Emas'),
    @('badge: "' + "$e_star" + ' +15.3k`$"', 'badge: "+15.3k`$"'),
    @("<h2 className=`"text-xl font-semibold`">$e_clip Monthly Performance Summary</h2>", '<h2 className="text-xl font-semibold inline-flex items-center gap-2"><ClipboardList size={18} aria-hidden="true" /> Monthly Performance Summary</h2>'),
    @("$e_cal" + ' Loading Replay Data', '<Loader2 size={14} className="inline animate-spin mr-1.5 -mt-0.5" aria-hidden="true" />Loading Replay Data'),
    @("<div className=`"mt-0.5 text-[9px] text-amber-400/80`">" + "$e_warn" + ' {disabledReason}</div>', '<div className="mt-0.5 text-[9px] text-amber-400/80 flex items-center gap-1"><AlertTriangle size={10} className="shrink-0" aria-hidden="true" /> {disabledReason}</div>'),
    @(' => `$e_zap ' + '$s`', ' => $s'),
    @('"`$e_target EQH"', '"EQH"'),
    @('"`$e_target EQL"', '"EQL"'),
    @('"`$e_target BSL"', '"BSL"'),
    @('"`$e_target SSL"', '"SSL"'),
    @($e_target + ' EQH', 'EQH'),
    @($e_target + ' EQL', 'EQL'),
    @($e_target + ' BSL', 'BSL'),
    @($e_target + ' SSL', 'SSL'),
    @('(Bar Replay ' + "$e_scis" + ')', '(Bar Replay)')
)

$importAdd = "Clapperboard, MapPin, Shield, Clock3, Move, Zap, Bot, Brain, Lightbulb, Check, X, BarChart3, Package, Wallet, Tag, Scale, ClipboardList, AlertTriangle"

foreach ($f in $files) {
    if (-not (Test-Path $f)) { continue }
    $text = [System.IO.File]::ReadAllText($f)
    $total = 0
    foreach ($p in $pairs) {
        $c = [regex]::Matches($text, [regex]::Escape($p[0])).Count
        if ($c -gt 0) { $text = $text.Replace($p[0], $p[1]); $total += $c }
    }
    # Tambah ikon yang belum ada di import lucide-react
    $m = [regex]::Match($text, 'import \{ ([^}]+) \} from "lucide-react";')
    if ($m.Success) {
        $have = $m.Groups[1].Value -split ",\s*" | ForEach-Object { $_.Trim() }
        $missing = $importAdd -split ",\s*" | Where-Object { $have -notcontains $_ }
        if ($missing.Count -gt 0) {
            $newImport = 'import { ' + (($have + $missing) -join ", ") + ' } from "lucide-react";'
            $text = $text.Replace($m.Value, $newImport)
        }
    }
    [System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
    $name = Split-Path $f -Leaf
    Write-Output "${name}: $total penggantian"
}
