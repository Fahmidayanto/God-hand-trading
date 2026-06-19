# Performance Page Filter Update

## Summary
Implementasi filter Year dan Month pada halaman Performance untuk menampilkan data berdasarkan tahun dan bulan dari folder `Backtest_result`.

## Changes Made

### 1. Backend Changes

#### `backend/app/services/performance_service.py`
- **Updated Function**: `get_monthly_pnl_from_csv()`
  - Added parameter `month: Optional[int] = None` untuk filter berdasarkan bulan
  - Mengubah logika untuk membaca semua file CSV yang sesuai dengan tahun yang dipilih
  - Menambahkan filter untuk bulan spesifik
  - Mendukung filter bulan tanpa tahun (across all years)
  - Logging lebih detail untuk debugging

#### `backend/app/api/v1/performance.py`
- **Updated Endpoint**: `GET /performance/monthly`
  - Added query parameters: `year` dan `month`
  - Meneruskan parameters ke service function
  
- **Updated Endpoint**: `GET /performance/monthly-pnl`
  - Meneruskan parameter `month` langsung ke service (bukan filter di endpoint)
  - Konsisten dengan endpoint `/monthly`

### 2. Frontend Changes

#### `frontend/src/app/mt5/performance.tsx`
- **Updated State Management**:
  - Menggunakan `selectedYear` dan `selectedMonth` untuk tracking filter yang aktif
  
- **Updated Function**: `loadPerformanceData()`
  - Membuat query string parameters untuk year dan month
  - Mengirim parameters ke semua endpoint yang relevan
  - Handle empty data dengan lebih baik
  
- **Updated Function**: `loadAvailableYears()`
  - Removed auto-selection of latest year
  - User dapat melihat semua data terlebih dahulu
  
- **Updated UI Components**:
  - Changed "Select Year" to "All Years" untuk lebih jelas
  - Removed disabled state pada month dropdown - user bisa filter hanya month tanpa year
  - Added "Clear Filters" button dengan icon 🔄
  - Added filter status indicator yang menampilkan filter aktif
  - Improved styling dan UX

## Features

### Filter Options
1. **All Data**: Tidak ada filter terpilih - menampilkan semua data dari semua tahun
2. **By Year**: Filter berdasarkan tahun spesifik - menampilkan semua bulan dalam tahun tersebut
3. **By Month**: Filter berdasarkan bulan spesifik - menampilkan bulan tersebut dari semua tahun
4. **By Year & Month**: Filter berdasarkan tahun dan bulan spesifik - menampilkan data satu bulan

### UI Improvements
- Clear Filters button muncul ketika ada filter aktif
- Filter status indicator menampilkan filter yang sedang aktif
- Smooth transitions dan hover effects
- Consistent styling dengan theme aplikasi

## Data Source
Data diambil dari CSV files di folder `Backtest_result`:
- Format: `Backtest_Results_XAUUSD_YYYY-MM-DD.csv`
- Service membaca semua file yang sesuai dengan filter
- Data di-aggregate per bulan dan tahun

## API Endpoints

### GET /api/v1/performance/available-years
Returns list of available years dari CSV files.

**Response:**
```json
{
  "years": [2020, 2021, 2022, 2023, 2024, 2025],
  "latest_year": 2025
}
```

### GET /api/v1/performance/monthly?year={year}&month={month}
Returns monthly performance data dengan optional filters.

**Query Parameters:**
- `year` (optional): Filter by specific year
- `month` (optional): Filter by specific month (1-12)

### GET /api/v1/performance/monthly-pnl?year={year}&month={month}
Returns detailed monthly P&L data untuk charting.

**Query Parameters:**
- `year` (optional): Filter by specific year
- `month` (optional): Filter by specific month (1-12)

## Testing

Test script tersedia di `test_performance_filter.py`:
```bash
cd "d:\Project\Project MT5\ValueCell_MT5"
python test_performance_filter.py
```

Test coverage:
- ✅ List available years
- ✅ Get all data (no filter)
- ✅ Filter by year only
- ✅ Filter by month only
- ✅ Filter by year and month

## Usage Example

### User Workflow
1. User membuka halaman Performance
2. Melihat semua data dari semua tahun (default)
3. Memilih tahun dari dropdown (e.g., 2025)
4. Data ter-filter menampilkan hanya tahun 2025
5. (Optional) Memilih bulan spesifik (e.g., June)
6. Data ter-filter menampilkan hanya June 2025
7. Click "Clear Filters" untuk kembali ke all data

### Filter Combinations
- **No filter**: Menampilkan semua data dari 2020-2025
- **Year = 2025**: Menampilkan semua bulan di 2025 (Jan-Dec 2025)
- **Month = 6**: Menampilkan June dari semua tahun (2020-2025)
- **Year = 2025, Month = 6**: Menampilkan hanya June 2025

## Browser Compatibility
- Modern browsers dengan ES6+ support
- React 18+
- Tested on Chrome, Firefox, Edge

## Performance
- Data loaded asynchronously
- Efficient CSV parsing (only reads relevant files)
- Caching di frontend untuk available years
- Automatic refresh setiap 10 detik (configurable)

## Future Improvements
1. Add date range picker untuk custom date range
2. Add export functionality untuk filtered data
3. Add comparison view (compare year-over-year)
4. Add caching di backend untuk improve performance
5. Add loading states dan skeleton loaders
6. Add error handling dengan user-friendly messages

## Notes
- Filter tidak mempengaruhi endpoint `/performance/stats` (still shows all-time stats)
- Monthly performance table dan charts ter-filter berdasarkan year/month selection
- Empty state handled gracefully dengan "No data available" message
