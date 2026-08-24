$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay-original.tsx"
$text = [System.IO.File]::ReadAllText($f)
$zap = [char]::ConvertFromUtf32(0x26A1)
$target = [char]::ConvertFromUtf32(0x1F3AF)
Write-Output ("zap contains: {0}" -f $text.Contains($zap))
Write-Output ("zap+space+Daftar: {0}" -f $text.Contains(($zap + " Daftar Posisi")))
Write-Output ("target+TotalPosisi: {0}" -f $text.Contains(($target + " Total Posisi")))
$idx = $text.IndexOf($zap)
if ($idx -ge 0) {
    $seg = $text.Substring($idx, [Math]::Min(30, $text.Length - $idx))
    $codes = ($seg.ToCharArray() | ForEach-Object { "{0:X4}" -f [int]$_ }) -join " "
    Write-Output "Segmen di idx zap pertama: $codes"
}
