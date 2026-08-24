$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\settings.tsx"
$lines = [System.IO.File]::ReadAllLines($f)
for ($n = 0; $n -lt $lines.Count; $n++) {
    $chars = $lines[$n].ToCharArray()
    for ($i = 0; $i -lt $chars.Length; $i++) {
        $cp = [int]$chars[$i]
        if (($cp -ge 0x2600 -and $cp -le 0x27BF) -or ($cp -ge 0xD83C -and $cp -le 0xDBFF) -or ($cp -eq 0xFE0F)) {
            $ctx = ""
            for ($j = [Math]::Max(0, $i - 3); $j -lt [Math]::Min($chars.Length, $i + 4); $j++) { $ctx += "{0:X4} " -f [int]$chars[$j] }
            Write-Output ("Line {0} pos {1}: {2}" -f ($n + 1), $i, $ctx.Trim())
        }
    }
}
