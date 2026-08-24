# Ganti emoji 📊 (U+1F4CA) tersisa di settings.tsx dengan ikon Lucide
$ErrorActionPreference = "Stop"
$f = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5\settings.tsx"
$text = [System.IO.File]::ReadAllText($f)
$bar = [char]::ConvertFromUtf32(0x1F4BC)
$idx = $text.IndexOf($bar)
if ($idx -ge 0) {
    $new = $text.Remove($idx, $bar.Length).Insert($idx, '<SlidersHorizontal size={18} aria-hidden="true" className="inline shrink-0" />')
    [System.IO.File]::WriteAllText($f, $new, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output "OK: emoji diganti pada index $idx"
} else {
    Write-Output "Tidak ditemukan"
}
# Verifikasi akhir seluruh file
$after = [System.IO.File]::ReadAllText($f)
$left = 0
foreach ($ch in $after.ToCharArray()) {
    $cp = [int]$ch
    if (($cp -ge 0x2600 -and $cp -le 0x27BF) -or ($cp -ge 0xD83C -and $cp -le 0xDBFF) -or ($cp -eq 0xFE0F)) { $left++ }
}
Write-Output "Sisa unit emoji: $left"
