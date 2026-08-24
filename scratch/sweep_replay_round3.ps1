# Round-3 (ASCII-safe): 5 spot terakhir di replay.tsx & replay-original.tsx
$ErrorActionPreference = "Stop"
$files = @(
    "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay.tsx",
    "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay-original.tsx"
)
function E([int]$cp) { return [char]::ConvertFromUtf32($cp) }
$WARN = (E 0x26A0) + (E 0xFE0F)
$PIN = E 0x1F4CD
$BULB = E 0x1F4A1
$TAG = (E 0x1F3F7) + (E 0xFE0F)
$ZAP = E 0x26A1

$subMap = [ordered]@{}
$subMap[($WARN + ' {disabledReason}')] = '<AlertTriangle size={10} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" /> {disabledReason}'
$subMap[('"> ' + $PIN)] = '">'
$subMap[($PIN + ' Entry Level:</span>')] = '<MapPin size={11} className="inline mr-0.5 -mt-px" aria-hidden="true" />Entry Level:</span>'
$subMap[('<span>' + $BULB + '</span>')] = '<Lightbulb size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />'
$subMap[($TAG + ' Visual Supply')] = '<Tag size={13} className="inline mr-1 -mt-px shrink-0" aria-hidden="true" />Visual Supply'
$subMap[('<span>' + $ZAP + '</span> Quick')] = '<Zap size={13} className="inline mr-1 -mt-px" aria-hidden="true" />Quick'

foreach ($f in $files) {
    if (-not (Test-Path $f)) { continue }
    $text = [System.IO.File]::ReadAllText($f)
    $n = 0
    foreach ($k in $subMap.Keys) {
        $c = [regex]::Matches($text, [regex]::Escape($k)).Count
        if ($c -gt 0) { $text = $text.Replace($k, $subMap[$k]); $n += $c }
    }
    [System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output ("{0}: {1}" -f (Split-Path $f -Leaf), $n)
}
