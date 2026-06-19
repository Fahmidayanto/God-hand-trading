# Jadwal Sesi Forex — GMT vs Server MT5 (GMT+2)

Dokumen ini merangkum 4 sesi utama pasar forex dan padanannya di **server time MT5 GMT+2** (MetaQuotes-Demo, IC Markets, Exness, FBS, dll. saat winter / non-DST).

> **Catatan DST:** Saat Daylight Saving Time aktif (akhir Maret – awal November), broker GMT+2 geser jadi **GMT+3**. Semua jam server di tabel akan **mundur 1 jam** selama periode itu.

---

## 4 Sesi Utama + Overlap

| # | Sesi | Pusat Finansial Utama | Waktu (GMT) | Waktu Server (GMT+2) | Waktu WIB (GMT+7) | Overlap dengan |
|---|------|----------------------|-------------|----------------------|--------------------|-----------------|
| 1 | **Sydney** | Sydney, Wellington | 21:00 – 06:00 | 23:00 – 08:00 | 04:00 – 13:00 | Tokyo (23:00–06:00 GMT) |
| 2 | **Tokyo (Asia)** | Tokyo, Hong Kong, Singapore | 23:00 – 08:00 | 01:00 – 10:00 | 06:00 – 15:00 | Sydney (23:00–06:00) · London (07:00–08:00) |
| 3 | **London** | London, Frankfurt, Paris, Zurich | 07:00 – 16:00 | 09:00 – 18:00 | 14:00 – 23:00 | Tokyo (07:00–08:00) · New York (12:00–16:00) |
| 4 | **New York** | New York, Toronto | 12:00 – 21:00 | 14:00 – 23:00 | 19:00 – 04:00 | London (12:00–16:00 GMT) |

---

## Detail Zona Overlap (Volatilitas Naik)

Saat 2 sesi aktif barengan, likuiditas dan pergerakan harga biasanya melonjak.

| # | Overlap | Durasi | Waktu (GMT) | Waktu Server (GMT+2) | Waktu WIB | Karakter |
|---|---------|--------|-------------|----------------------|-----------|----------|
| 1 | Sydney – Tokyo | 7 jam | 23:00 – 06:00 | 01:00 – 08:00 | 06:00 – 13:00 | Likuiditas Asia, range trading |
| 2 | Tokyo – London | 1 jam | 07:00 – 08:00 | 09:00 – 10:00 | 14:00 – 15:00 | Pendek, momentum transisi |
| 3 | **London – New York** | **4 jam** | **12:00 – 16:00** | **14:00 – 18:00** | **19:00 – 23:00** | **PALING RAMAI** — pergerakan terbesar, news driven |

---

## Versi Praktis (3 Sesi — Sydney digabung ke Asia)

Banyak trader menggabungkan Sydney + Tokyo karena keduanya overlap hampir sepenuhnya (7 dari 9 jam Sydney).

| Sesi | Waktu (GMT) | Waktu Server (GMT+2) | Waktu WIB |
|------|-------------|----------------------|-----------|
| **Asia** (Sydney + Tokyo) | 21:00 – 08:00 | 23:00 – 10:00 | 04:00 – 15:00 |
| **London** | 07:00 – 16:00 | 09:00 – 18:00 | 14:00 – 23:00 |
| **New York** | 12:00 – 21:00 | 14:00 – 23:00 | 19:00 – 04:00 |

---

## Window di EA `Dev_Bot_v10_H+BR+H4.cs`

Implementasi `GetCurrentSession()` setelah patch fixed-offset GMT+2 + label overlap Tokyo-London:

| Jam Server (GMT+2) | Sesi yang Dideteksi | Catatan |
|--------------------|---------------------|---------|
| 23:00 – 00:59 | `Sydney` | Sydney only (sebelum Tokyo open) |
| 01:00 – 07:59 | `Sydney_Tokyo_Overlap` | Sydney + Tokyo barengan (overlap likuiditas Asia) |
| 08:00 – 08:59 | `Asia` | Tokyo only (Sydney close jam 08:00 server) |
| 09:00 – 09:59 | `Tokyo_London_Overlap` | Transisi Tokyo wrap-up + London open |
| 10:00 – 13:59 | `London` | London murni (Tokyo sudah close) |
| 14:00 – 17:59 | `London_NewYork_Overlap` | Volatilitas tertinggi |
| 18:00 – 22:59 | `NewYork` | NY murni (London sudah close) |
| Sabtu / Minggu | `Weekend` | Filter no-trade |

**Visual shadow chart** menggambar **4 sesi** (Sydney / Asia / London / NewYork). Label overlap (Sydney-Tokyo, Tokyo-London, London-NY) tetap dideteksi di logika dan dicatat di logs/CSV, tapi secara visual terlihat dari **campuran warna** rectangle yang menumpuk (transparency 80% additive blend):

| Slot Visual (Server GMT+2) | Rectangle Aktif | Warna yang Muncul |
|----------------------------|-----------------|-------------------|
| 23:00 – 01:00 | Sydney | hijau pucat |
| 01:00 – 08:00 | Sydney + Asia | hijau + merah = coklat-zaitun |
| 08:00 – 09:00 | Asia | merah |
| 09:00 – 10:00 | Asia + London | merah + kuning = coklat/oranye |
| 10:00 – 14:00 | London | kuning |
| 14:00 – 18:00 | London + NewYork | kuning + biru = hijau-zaitun |
| 18:00 – 23:00 | NewYork | biru |

---

## Karakteristik per Sesi (XAUUSD / Gold)

| Sesi | Volatilitas | Karakter Pergerakan | Strategi Cocok |
|------|-------------|---------------------|----------------|
| Sydney | Rendah | Range tipis, gap weekend | Hindari (tidak banyak setup) |
| Asia (Tokyo) | Rendah – Menengah | Range, kadang trend lemah | Range trading, support/resistance |
| Tokyo – London Overlap | Menengah | Spike awal pembukaan London | Breakout dini, hati-hati fakeout |
| London | Tinggi | Trend kuat, breakout valid | Breakout, trend following |
| **London – NY Overlap** | **Tertinggi** | Momentum besar, news driven | Breakout, momentum |
| New York | Tinggi | Reversal sering, news US | Reversal, news trading |

---

## Konversi Cepat WIB → Server GMT+2

WIB **lebih cepat 5 jam** dari server GMT+2.

| Jam WIB | Jam Server (GMT+2) | Sesi Aktif |
|---------|--------------------|-------------|
| 04:00 | 23:00 (hari sebelumnya) | Sydney start |
| 06:00 | 01:00 | Asia (Tokyo) start |
| 13:00 | 08:00 | Sydney close |
| 14:00 | 09:00 | Tokyo–London Overlap start |
| 15:00 | 10:00 | London murni / Tokyo close |
| 19:00 | 14:00 | London–NY Overlap start |
| 23:00 | 18:00 | London close, NY murni |
| 04:00 (besoknya) | 23:00 | NY close, Sydney start lagi |

---

## Cek Offset Broker Sendiri

Tambahkan log singkat di `OnInit()`:

```mql5
PrintFormat("=== BROKER TIME INFO ===");
PrintFormat("Server time : %s", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
PrintFormat("GMT time    : %s", TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS));
PrintFormat("Offset GMT  : %+d jam", (int)((TimeCurrent() - TimeGMT()) / 3600));
```

Jika output offset selain `+2`, sesuaikan window jam di `GetCurrentSession()`.

---

## Referensi

- Standar pasar forex internasional (Bank for International Settlements)
- MetaQuotes-Demo server time = EET / EEST (GMT+2 winter, GMT+3 summer)
- File implementasi: `d:\Project\Project MT5\Dev_Bot_v10_H+BR+H4.cs`
