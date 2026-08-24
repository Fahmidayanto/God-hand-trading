$targets = @(
    @("B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\rongsokan.tsx", 1950),
    @("B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\trades.tsx", 2163),
    @("B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\DraggableLayout.tsx", 76),
    @("B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\DraggableLayout.tsx", 84),
    @("B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\DraggableLayout.tsx", 93),
    @("B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\components\MT5Footer.tsx", 34)
)
foreach ($t in $targets) {
    $lines = [System.IO.File]::ReadAllLines($t[0])
    if ($t[1] -gt $lines.Count) { continue }
    $line = $lines[$t[1] - 1]
    $cps = ($line.ToCharArray() | ForEach-Object { $c = [int]$_; if ($c -gt 127) { "{0:X4}" -f $c } }) -join " "
    Write-Output ("{0}:{1}: [{2}] {3}" -f (Split-Path $t[0] -Leaf), $t[1], $cps, $line.Trim().Substring(0, [Math]::Min(100, $line.Trim().Length)))
}
