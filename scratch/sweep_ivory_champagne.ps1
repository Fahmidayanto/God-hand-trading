# Sweep Ivory Champagne - ganti warna tema lama ke palet Ivory Champagne
# Semantik TIDAK disentuh: rose/red (SELL), emerald/green/teal-lain (BUY), amber/yellow/orange (warning+brand)
$ErrorActionPreference = "Stop"

$dir = "B:\Project MT5\ValueCell_MT5\frontend\src\app\mt5"
$files = @(
  "$dir\simulation.tsx", "$dir\replay.tsx", "$dir\replay-original.tsx",
  "$dir\database.tsx", "$dir\trades.tsx", "$dir\performance.tsx",
  "$dir\rongsokan.tsx", "$dir\components\ChartToolbar.tsx",
  "$dir\components\LayoutDebugger.tsx"
)

# ── Peta kelas Tailwind: family -> shade -> hex ──
$maps = @{
  "cyan"    = @{ "200"="#FDFBF5"; "300"="#FCF8EE"; "400"="#FFFDF7"; "500"="#EFE3C8"; "600"="#E3D3AC"; "700"="#C9B98F"; "800"="#A69368"; "900"="#7D6C49"; "950"="#57492E" }
  "blue"    = @{ "200"="#F7EFDC"; "300"="#F0E4CB"; "400"="#E7D2A3"; "500"="#DCC08B"; "600"="#C4A469"; "700"="#9E8047"; "800"="#776034"; "900"="#54432A"; "950"="#382C1C" }
  "purple"  = @{ "200"="#F5EDDA"; "300"="#F0E9DA"; "400"="#E8DEC5"; "500"="#D8C9A7"; "600"="#C4AA7C"; "700"="#9C855C"; "800"="#6F5D40"; "900"="#4A3F2C"; "950"="#33291A" }
  "violet"  = @{ "200"="#F5EDDA"; "300"="#F0E9DA"; "400"="#E8DEC5"; "500"="#D8C9A7"; "600"="#C4AA7C"; "700"="#9C855C"; "800"="#6F5D40"; "900"="#4A3F2C"; "950"="#33291A" }
  "indigo"  = @{ "300"="#F0E9DA"; "400"="#E4D9C2"; "500"="#D3C3A0"; "600"="#B39D74"; "700"="#8F7B55"; "800"="#6B5C40"; "900"="#4A3F2C"; "950"="#33291A" }
  "sky"     = @{ "300"="#FFFDF7"; "400"="#FBF6EA"; "500"="#EFE3C8"; "600"="#DCC08B" }
  "fuchsia" = @{ "300"="#F5EDDA"; "400"="#E8DEC5"; "500"="#D8C9A7" }
}
$stems = @(
  "border-t","border-b","border-l","border-r","border-x","border-y","border-s","border-e",
  "text","bg","border","from","via","to","ring","fill","stroke","shadow",
  "decoration","divide","outline","accent","caret","placeholder"
)

# ── Peta literal langsung (rgba, hex, 0x) ──
$literals = [ordered]@{
  # rgba glow aksen lama
  "rgba(103,232,249"="rgba(255,253,247"; "rgba(165,243,252"="rgba(255,250,240"
  "rgba(34,211,238"="rgba(239,227,200";   "rgba(6,182,212"="rgba(227,211,172"
  "rgba(96,165,250"="rgba(231,210,163";   "rgba(59,130,246"="rgba(220,192,139"
  "rgba(37,99,235"="rgba(196,164,105";    "rgba(29,78,216"="rgba(158,128,71"
  "rgba(147,197,253"="rgba(240,228,203"
  "rgba(192,132,252"="rgba(232,222,199";  "rgba(168,85,247"="rgba(216,201,167"
  "rgba(147,51,234"="rgba(196,172,124";   "rgba(216,180,254"="rgba(240,233,218"
  "rgba(129,140,248"="rgba(228,217,194";  "rgba(99,102,241"="rgba(211,195,160"
  "rgba(79,70,229"="rgba(179,157,116"
  "rgba(56,189,248"="rgba(255,253,247";   "rgba(14,165,233"="rgba(239,227,200"
  "rgba(125,211,252"="rgba(255,250,240"
  "rgba(217,70,239"="rgba(216,201,167";   "rgba(232,121,249"="rgba(232,222,199"
  "rgba(240,171,252"="rgba(240,231,210"
  # permukaan navy/slate -> charcoal hangat
  "rgba(2,6,23"="rgba(11,10,8";           "rgba(15,23,42"="rgba(26,23,18"
  "rgba(30,41,59"="rgba(38,33,26";        "rgba(51,65,85"="rgba(53,45,34"
  "rgba(71,85,105"="rgba(74,63,48";       "rgba(100,116,139"="rgba(133,118,95"
  # hex string aksen lama
  "#67e8f9"="#FFFDF7"; "#a5f3fc"="#FFFDF7"; "#22d3ee"="#EFE3C8"; "#06b6d4"="#E3D3AC"
  "#0e7490"="#C9B98F"; "#155e75"="#A69368"; "#38bdf8"="#EFE3C8"; "#7dd3fc"="#FFFDF7"
  "#0ea5e9"="#E3D3AC"; "#0284c7"="#C4A469"; "#3b82f6"="#DCC08B"; "#60a5fa"="#E7D2A3"
  "#93c5fd"="#F0E4CB"; "#2563eb"="#C4A469"; "#1d4ed8"="#9E8047"; "#1e40af"="#776034"
  "#1e3a8a"="#54432A"; "#a78bfa"="#D9CDB4"; "#8b5cf6"="#CBBA94"; "#7c3aed"="#B39D74"
  "#6d28d9"="#9C855C"; "#c084fc"="#E8DEC5"; "#d8b4fe"="#F0E9DA"; "#a855f7"="#D3C3A0"
  "#9333ea"="#C4AA7C"; "#e9d5ff"="#F5EDDA"; "#818cf8"="#E4D9C2"; "#a5b4fc"="#F0E9DA"
  "#6366f1"="#D3C3A0"; "#4f46e5"="#B39D74"; "#3730a3"="#6B5C40"; "#e879f9"="#E8DEC5"
  "#d946ef"="#D8C9A7"; "#f0abfc"="#F0E7D2"; "#c026d3"="#C4AA7C"
  # hex navy/slate permukaan
  "#020617"="#0B0A08"; "#0f172a"="#1A1712"; "#1e293b"="#26211A"; "#334155"="#352D22"
  "#475569"="#4A3F2C"; "#64748b"="#856F5F"; "#0B0F19"="#12100C"; "#05070C"="#0B0A08"
  "#0E1424"="#1A1712"; "#182038"="#26211A"; "#243054"="#352D22"
  # Three.js 0x (aksen)
  "0x06b6d4"="0xEFE3C8"; "0x22d3ee"="0xEFE3C8"; "0x0891b2"="0xC9B98F"
  "0x0e7490"="0xA69368"; "0x155e75"="0x7D6C49"
  "0x3b82f6"="0xDCC08B"; "0x2563eb"="0xC4A469"; "0x60a5fa"="0xE7D2A3"
  "0xa78bfa"="0xD9CDB4"; "0x8b5cf6"="0xCBBA94"; "0xa855f7"="0xD3C3A0"
  "0xc084fc"="0xE8DEC5"; "0xec4899"="0xD9CDB4"
  # Three.js 0x (permukaan netral)
  "0x020617"="0x0B0A08"; "0x0f172a"="0x1A1712"; "0x1e293b"="0x26211A"; "0x334155"="0x352D22"
}

$totalAll = 0
foreach ($f in $files) {
  if (-not (Test-Path $f)) { Write-Output "SKIP (tidak ada): $f"; continue }
  $content = Get-Content $f -Raw
  $original = $content
  $count = 0

  # 1) Literal maps dulu
  foreach ($k in $literals.Keys) {
    $m = ([regex]::Matches($content, [regex]::Escape($k))).Count
    if ($m -gt 0) { $count += $m; $content = $content.Replace($k, $literals[$k]) }
  }

  # 2) Kelas Tailwind: stem-family-shade -> stem-[#hex]
  foreach ($family in $maps.Keys) {
    foreach ($shade in $maps[$family].Keys) {
      $hex = $maps[$family][$shade]
      foreach ($stem in $stems) {
        $pat = "(?<![A-Za-z0-9-])$stem-$family-$shade(?![\w-])"
        $rx = [regex]$pat
        $m = $rx.Matches($content).Count
        if ($m -gt 0) { $count += $m; $content = $rx.Replace($content, "$stem-[$hex]") }
      }
    }
  }

  if ($count -gt 0) {
    Set-Content -Path $f -Value $content -Encoding UTF8 -NoNewline
    Write-Output "$(Split-Path $f -Leaf): $count penggantian"
    $totalAll += $count
  } else {
    Write-Output "$(Split-Path $f -Leaf): 0 (bersih)"
  }
}
Write-Output "TOTAL: $totalAll penggantian"
