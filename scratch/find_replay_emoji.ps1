$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\replay-original.tsx"
$lines = [System.IO.File]::ReadAllLines($f)
for ($n = 0; $n -lt $lines.Count; $n++) {
    $chars = $lines[$n].ToCharArray()
    $printed = $false
    for ($i = 0; $i -lt $chars.Length; $i++) {
        $cp = [int]$chars[$i]
        if (($cp -ge 0x2600 -and $cp -le 0x27BF) -or ($cp -ge 0xD83C -and $cp -le 0xDBFF) -or ($cp -ge 0x2B00 -and $cp -le 0x2BFF) -or ($cp -eq 0xFE0F)) {
            if (-not $printed) { Write-Output ("LINE {0}:" -f ($n + 1)); $printed = $true }
            Write-Output ("  pos {0}: {1:X4}" -f $i, $cp)
        }
    }
}
