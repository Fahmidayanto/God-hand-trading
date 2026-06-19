# 📊 Monthly Profit/Loss Chart Implementation - Checklist

## ✅ Backend Setup (Sudah Selesai)

### API Endpoints:
- **GET `/api/v1/trading/performance/monthly-pnl`** 
  - Returns detailed monthly P&L data from CSV
  - Used for Monthly Profit/Loss chart
  
- **GET `/api/v1/trading/performance/monthly`** 
  - Updated untuk menggunakan data CSV (bukan placeholder)

### Backend Functions:
- `get_monthly_pnl_from_csv()` - Baca CSV & group by month ✓
- `list_available_backtest_files()` - List backtest files ✓

## ✅ Frontend Setup (Sudah Selesai)

### File Modified:
- `frontend/src/app/mt5/performance.tsx`
  - Added `monthlyPNL` state
  - Added `monthlyProfitLossData` chart config
  - Added monthly profit/loss bar chart component
  - Fetch data dari `/api/v1/trading/performance/monthly-pnl`

## 🚀 Untuk Melihat di Frontend:

### Opsi 1: Development Mode (Recommended)
```bash
# Terminal 1: Start Backend
cd d:\Project\Project MT5\ValueCell_MT5\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Frontend (in a new terminal)
cd d:\Project\Project MT5\ValueCell_MT5\frontend
npm run dev
# or
bun run dev
```

Kemudian buka: http://localhost:5173 (atau port yang ditunjukkan)
Navigate ke: **MT5 → Performance** page

### Opsi 2: Production Build
```bash
# Build backend (if needed)
# Build frontend
npm run build
# or
bun run build
```

## 📊 Chart Details

**Location:** Performance page → Section "Monthly Profit/Loss Breakdown"
- **Type:** Stacked Bar Chart
- **Green bars:** Monthly profits
- **Red bars:** Monthly losses
- **Data source:** Real backtest CSV files

## 🧪 Testing

Jalankan test script untuk verify API:
```bash
python d:\Project\Project MT5\test_api_endpoint.py
```

Harus output:
```
✅ API endpoint is working!
Response:
  - Total months: 12
  - Total P&L: $3056.69
  - Total trades: 38
  - Avg monthly profit: $254.72
  - Best month: Mar 2025
  - Worst month: Jul 2025
```

## 📝 Data Source

- **File:** `d:\Project\Project MT5\Backtest_result\Backtest_Results_XAUUSD_2025-12-30.csv`
- **Months:** Jan 2025 - Dec 2025 (12 bulan)
- **Total Trades:** 38
- **Total Net Profit:** $3,056.69
- **Win Rate:** 60.53%

## ⚠️ Important Notes

1. Backend HARUS running di `http://localhost:8000` untuk frontend bisa fetch data
2. CSV files harus ada di `d:\Project\Project MT5\Backtest_result\`
3. Chart akan auto-refresh setiap 10 detik (sesuai `setInterval`)

## 🎯 Expected Result

Performance page akan menampilkan:
1. Existing charts (Equity Curve, Win/Loss Distribution, Monthly Returns, Drawdown)
2. **NEW:** Monthly Profit/Loss Breakdown chart dengan data real dari CSV
3. Summary statistics di bawah chart

---

Sudah siap! Tinggal jalankan backend & frontend untuk melihat hasilnya. 🎉
