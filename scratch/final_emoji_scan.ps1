# Scan final: emoji yang tampil di UI (bukan console/komentar) di seluruh app/mt5
$base = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5"
$total = 0
Get-ChildItem $base -Filter *.tsx -Recurse | ForEach-Object {
    $lines = [System.IO.File]::ReadAllLines($_.FullName)
    for ($n = 0; $n -lt $lines.Count; $n++) {
        $trim = $lines[$n].Trim()
        if ($trim.StartsWith("console.") -or $trim.StartsWith("//") -or $trim.StartsWith("*") -or $trim.StartsWith("{/*") -or $trim.StartsWith("/*")) { continue }
        $chars = $trim.ToCharArray()
        for ($i = 0; $i -lt $chars.Length; $i++) {
            $cp = [int]$chars[$i]
            if (($cp -ge 0x2600 -and $cp -le 0x27BF) -or ($cp -ge 0xD83C -and $cp -le 0xDBFF) -or ($cp -ge 0x2B00 -and $cp -le 0x2BFF) -or ($cp -eq 0xFE0F)) {
                Write-Output ("{0}:{1}: {2}" -f $_.Name, ($n + 1), $trim.Substring(0, [Math]::Min(100, $trim.Length)))
                $total++
                break
            }
        }
    }
}
Write-Output "TOTAL SISA EMOJI UI: $total"
