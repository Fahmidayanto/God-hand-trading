use chrono::{DateTime, Datelike, Duration as ChronoDuration, NaiveDateTime, TimeZone, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

const DATA_DIR: &str = r"D:\Project\Project MT5\Other\Backtest_rongsokan";
const DEFAULT_FROM: &str = "2020-01-01";
const LIMIT_RECENT: usize = 30_000;
const LIMIT_FULL: usize = 200_000;
const LIMIT_WINDOW: usize = 20_000;

#[derive(Debug, Clone, Serialize)]
pub struct Candle {
    pub time: i64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub ema200: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TimezoneInfo {
    pub broker_offset_hours: i32,
    pub display_mode: String,
    pub candle_times_are_utc: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CandleRequest {
    pub symbol: String,
    pub timeframe: String,
    pub mode: String,
    pub from_date: Option<String>,
    pub center_date: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CandleResponse {
    pub symbol: String,
    pub timeframe: String,
    pub candles: Vec<Candle>,
    pub candles_count: usize,
    pub mode: String,
    pub from_date: String,
    pub center_date: Option<String>,
    pub timezone: TimezoneInfo,
}

#[derive(Debug, Deserialize)]
pub struct CandleRow {
    #[serde(rename = "Time")]
    pub time: String,
    #[serde(rename = "Open")]
    pub open: String,
    #[serde(rename = "High")]
    pub high: String,
    #[serde(rename = "Low")]
    pub low: String,
    #[serde(rename = "Close")]
    pub close: String,
    #[serde(rename = "EMA200")]
    pub ema200: Option<String>,
}

type CacheKey = (String, String);

fn cache() -> &'static Mutex<HashMap<CacheKey, Vec<Candle>>> {
    static CACHE: OnceLock<Mutex<HashMap<CacheKey, Vec<Candle>>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

#[cfg(test)]
pub fn clear_cache() {
    cache().lock().unwrap().clear();
}

pub fn parse_row(row: &CandleRow) -> Result<Candle, String> {
    let naive = NaiveDateTime::parse_from_str(&row.time, "%Y.%m.%d %H:%M:%S")
        .map_err(|e| format!("invalid time '{}': {}", row.time, e))?;
    let dt: DateTime<Utc> = Utc.from_utc_datetime(&naive);
    Ok(Candle {
        time: dt.timestamp(),
        open: parse_float(&row.open)?,
        high: parse_float(&row.high)?,
        low: parse_float(&row.low)?,
        close: parse_float(&row.close)?,
        ema200: row.ema200.as_ref().and_then(|v| parse_float(v).ok()),
    })
}

fn parse_float(s: &str) -> Result<f64, String> {
    s.trim()
        .parse::<f64>()
        .map_err(|e| format!("invalid float '{}': {}", s, e))
}

fn data_dir() -> PathBuf {
    PathBuf::from(DATA_DIR)
}

fn market_data_files(symbol: &str, timeframe: &str) -> Vec<PathBuf> {
    let dir = data_dir();
    let pattern = dir.join(format!("MarketData_{}_{}_*.csv", symbol, timeframe));
    let mut files: Vec<PathBuf> = match glob::glob(&pattern.to_string_lossy()) {
        Ok(paths) => paths.filter_map(Result::ok).collect(),
        Err(_) => vec![],
    };
    files.sort();
    files
}

fn load_candles(symbol: &str, timeframe: &str) -> Result<Vec<Candle>, String> {
    let files = market_data_files(symbol, timeframe);
    let mut candles: Vec<Candle> = Vec::new();
    for path in files {
        let mut reader = csv::Reader::from_path(&path)
            .map_err(|e| format!("failed to open {:?}: {}", path, e))?;
        for result in reader.deserialize::<CandleRow>() {
            match result {
                Ok(row) => match parse_row(&row) {
                    Ok(c) => candles.push(c),
                    Err(e) => log::warn!("skip row in {:?}: {}", path, e),
                },
                Err(e) => log::warn!("deserialize error in {:?}: {}", path, e),
            }
        }
    }
    Ok(prepare_candles(&mut candles))
}

pub fn prepare_candles(candles: &mut Vec<Candle>) -> Vec<Candle> {
    candles.sort_by_key(|c| c.time);
    let mut seen = HashMap::<i64, bool>::new();
    candles.retain(|c| {
        if seen.contains_key(&c.time) {
            false
        } else {
            seen.insert(c.time, true);
            true
        }
    });
    candles.clone()
}

fn get_cached(symbol: &str, timeframe: &str) -> Result<Vec<Candle>, String> {
    let key = (symbol.to_string(), timeframe.to_string());
    {
        let cache = cache().lock().unwrap();
        if let Some(candles) = cache.get(&key) {
            return Ok(candles.clone());
        }
    }
    let candles = load_candles(symbol, timeframe)?;
    let mut cache = cache().lock().unwrap();
    cache.insert(key, candles.clone());
    Ok(candles)
}

fn parse_ymd(s: &str) -> Result<DateTime<Utc>, String> {
    let naive = NaiveDateTime::parse_from_str(&format!("{} 00:00:00", s), "%Y-%m-%d %H:%M:%S")
        .map_err(|e| format!("invalid date '{}': {}", s, e))?;
    Ok(Utc.from_utc_datetime(&naive))
}

pub fn quick_range(from_date: Option<String>) -> Result<(String, Option<String>), String> {
    let year = Utc::now().year();
    let from = from_date.unwrap_or_else(|| format!("{}-01-01", year));
    Ok((from, None))
}

pub fn window_range(center_date: &str) -> Result<(String, String), String> {
    let center = parse_ymd(center_date)?;
    let from = (center - ChronoDuration::days(90))
        .format("%Y-%m-%d")
        .to_string();
    let to = (center + ChronoDuration::days(90))
        .format("%Y-%m-%d")
        .to_string();
    Ok((from, to))
}

fn filter_and_limit(
    candles: &[Candle],
    from: DateTime<Utc>,
    to: Option<DateTime<Utc>>,
    limit: usize,
) -> Vec<Candle> {
    candles
        .iter()
        .filter(|c| {
            let t = match Utc.timestamp_opt(c.time, 0).single() {
                Some(dt) => dt,
                None => return false,
            };
            t >= from && to.as_ref().map(|x| t <= *x).unwrap_or(true)
        })
        .take(limit)
        .cloned()
        .collect()
}

#[tauri::command]
pub fn get_rongsokan_candles(req: CandleRequest) -> Result<CandleResponse, String> {
    let all = get_cached(&req.symbol, &req.timeframe)?;

    let (from_str, to_opt, limit, mode) = match req.mode.as_str() {
        "quick" => {
            let (from, _) = quick_range(req.from_date.clone())?;
            (from, None, LIMIT_RECENT, "quick".to_string())
        }
        "recent" => {
            let from = req
                .from_date
                .clone()
                .unwrap_or_else(|| DEFAULT_FROM.to_string());
            (from, None, LIMIT_RECENT, "recent".to_string())
        }
        "full" => (
            DEFAULT_FROM.to_string(),
            None,
            LIMIT_FULL,
            "full".to_string(),
        ),
        "window" => {
            let center = req
                .center_date
                .as_ref()
                .ok_or("center_date required for window mode")?;
            let (from, to) = window_range(center)?;
            (from, Some(to), LIMIT_WINDOW, "window".to_string())
        }
        other => return Err(format!("unknown mode '{}'", other)),
    };

    let from_dt = parse_ymd(&from_str)?;
    let to_dt = to_opt.as_ref().map(|t| parse_ymd(t)).transpose()?;
    let filtered = filter_and_limit(&all, from_dt, to_dt, limit);

    Ok(CandleResponse {
        symbol: req.symbol.clone(),
        timeframe: req.timeframe.clone(),
        candles_count: filtered.len(),
        candles: filtered,
        mode,
        from_date: from_str,
        center_date: req.center_date,
        timezone: TimezoneInfo {
            broker_offset_hours: 0,
            display_mode: "utc".to_string(),
            candle_times_are_utc: true,
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_candle_row() {
        let row = CandleRow {
            time: "2026.01.02 00:00:00".to_string(),
            open: "2650.00".to_string(),
            high: "2651.20".to_string(),
            low: "2649.80".to_string(),
            close: "2650.50".to_string(),
            ema200: Some("2648.10".to_string()),
        };
        let candle = parse_row(&row).unwrap();
        assert_eq!(candle.time, 1_736_361_600);
        assert_eq!(candle.open, 2650.00);
        assert_eq!(candle.ema200, Some(2648.10));
    }

    #[test]
    fn test_dedup_and_sort_candles() {
        let mut candles = vec![
            Candle {
                time: 200,
                open: 1.0,
                high: 2.0,
                low: 0.5,
                close: 1.5,
                ema200: None,
            },
            Candle {
                time: 100,
                open: 1.0,
                high: 2.0,
                low: 0.5,
                close: 1.5,
                ema200: None,
            },
            Candle {
                time: 200,
                open: 2.0,
                high: 3.0,
                low: 1.5,
                close: 2.5,
                ema200: None,
            },
        ];
        let out = prepare_candles(&mut candles);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].time, 100);
        assert_eq!(out[1].time, 200);
    }

    #[test]
    fn test_quick_mode_uses_current_year_january() {
        let (from, _) = quick_range(None).unwrap();
        let expected = format!("{}-01-01", Utc::now().year());
        assert_eq!(from, expected);
    }

    #[test]
    fn test_window_mode_center_date() {
        let (from, to) = window_range("2026-04-01").unwrap();
        assert_eq!(from, "2026-01-01");
        assert_eq!(to, "2026-07-01");
    }

    #[test]
    fn test_cache_returns_same_vec() {
        clear_cache();
        let req = CandleRequest {
            symbol: "XAUUSD".to_string(),
            timeframe: "M15".to_string(),
            mode: "full".to_string(),
            from_date: Some("2026-01-01".to_string()),
            center_date: None,
        };
        let a = get_rongsokan_candles(req.clone()).unwrap();
        let b = get_rongsokan_candles(req).unwrap();
        assert_eq!(a.candles_count, b.candles_count);
    }
}
