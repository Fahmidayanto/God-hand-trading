"""
Market Structure Agent - Specialist Grafik (v3.0.0)

Membaca data secara langsung dari Neon PostgreSQL:
1. llhhbosdata_xauusd - Event struktur pasar (CHoCH, HH/LL, BoS) yang dideteksi oleh EA
2. marketdata_xauusd_m15, h1, h4 - Data harga historis & nilai EMA200 terbaru

Mengikuti DUA TAHAP kerja sesuai spesifikasi Flow_endtoend.md:
Tahap 1: Pre-Analysis (saat CHoCH + HH/LL terbentuk)
  - Diambil dari Neon DB
  - Query LanceDB: cari win rate historis pola BoS serupa di masa lalu
  - Hitung initial confidence & kirim pre_signal ke ML & Sentiment Agent
Tahap 2: Execution Trigger (saat BoS terkonfirmasi)
  - Diambil dari Neon DB (adanya event BoS baru)
  - Hitung confidence akhir menggunakan formula multi-timeframe EMA + win rate boost
  - Kirim sinyal final BUY/SELL/HOLD
"""

import os
import sys
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import psycopg2
import pandas as pd
from loguru import logger

from valuecell.knowledge.pattern_matcher import PatternMatcher


class AgentPhase(Enum):
    """State machine untuk dua tahap kerja MSA."""
    IDLE           = "IDLE"           # Belum ada setup
    PENDING_SETUP  = "PENDING_SETUP"  # CHoCH + HH terbentuk, menunggu BoS
    BOS_TRIGGERED  = "BOS_TRIGGERED"  # BoS dikonfirmasi, sinyal final dikirim


class MarketStructureAgent:
    """
    Market Structure Agent v3.0 - Specialist Grafik.

    Membaca event dari database Neon PostgreSQL (`llhhbosdata_xauusd`)
    dan nilai EMA200 dari `marketdata_xauusd_*`.
    """

    def __init__(
        self,
        swing_length: int = 5,
        timeframe: str = "M15",
        use_patterns: bool = True
    ):
        """Initialize Market Structure Agent."""
        self.name = "MarketStructureAgent"
        self.version = "3.0.0"
        self.swing_length = swing_length
        self.timeframe = timeframe
        self.use_patterns = use_patterns

        # Initialize pattern matcher (LanceDB)
        self.pattern_matcher = PatternMatcher() if use_patterns else None

        # State Machine
        self._phase: AgentPhase = AgentPhase.IDLE
        self._pending_hh_price: Optional[float] = None
        self._pending_ll_price: Optional[float] = None
        self._pending_analysis: Optional[Dict] = None
        self._pending_pre_signal: Optional[Dict] = None
        self._pending_evidence_snapshot: Optional[Dict] = None
        self._last_bos_direction: Optional[str] = None

        logger.info(
            f"[OK] {self.name} v{self.version} initialized | "
            f"Reading from Neon DB | Pattern matching: {use_patterns}"
        )

    # ── Database Connections ───────────────────────────────────────────────

    def _get_db_conn(self):
        """Create a connection to Neon PostgreSQL."""
        from dotenv import load_dotenv
        load_dotenv()
        
        # Coba load dari folder environment sistem
        try:
            from valuecell.utils.env import get_system_env_path
            sys_env = get_system_env_path()
            if sys_env.exists():
                load_dotenv(sys_env)
        except Exception:
            pass

        host = os.getenv("PGHOST")
        database = os.getenv("PGDATABASE")
        user = os.getenv("PGUSER")
        password = os.getenv("PGPASSWORD")
        sslmode = os.getenv("PGSSLMODE", "require")

        # Fallback ke konfigurasi app backend jika di-import di FastAPI
        if not all([host, database, user, password]):
            try:
                from app.config import get_settings
                s = get_settings()
                host = s.PGHOST or host
                database = s.PGDATABASE or database
                user = s.PGUSER or user
                password = s.PGPASSWORD or password
                sslmode = s.PGSSLMODE or sslmode
            except Exception:
                pass

        if not all([host, database, user, password]):
            raise ValueError(
                "Koneksi database gagal: variabel environment PGHOST, PGDATABASE, PGUSER, PGPASSWORD harus diset!"
            )

        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            sslmode=sslmode,
            connect_timeout=10
        )
        conn.autocommit = True
        return conn

    def _get_neon_ema200(self, conn, timeframe: str) -> Optional[float]:
        """Ambil nilai EMA200 terbaru dari Neon DB."""
        table_name = f"marketdata_xauusd_{timeframe.lower()}"
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT ema200, close FROM {table_name} ORDER BY time DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    ema200, close = row
                    return float(ema200) if ema200 is not None else float(close)
        except Exception as e:
            logger.warning(f"Gagal mengambil EMA200 untuk {timeframe} dari Neon: {e}")
        return None

    def _get_neon_current_price(self, conn) -> Optional[float]:
        """Ambil harga close M15 terbaru dari Neon DB."""
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT close FROM marketdata_xauusd_m15 ORDER BY time DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    return float(row[0])
        except Exception as e:
            logger.warning(f"Gagal mengambil harga terbaru dari Neon: {e}")
        return None

    def _fetch_neon_events(self, conn, limit: int = 50) -> List[Dict[str, Any]]:
        """Ambil event struktur pasar terbaru untuk M15 dari Neon DB."""
        events = []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT type, direction_action, price, time, timeframe, status
                    FROM llhhbosdata_xauusd
                    WHERE timeframe = 'M15' AND status IN ('Accepted', 'Confirmed')
                    ORDER BY time DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = cur.fetchall()
                for row in rows:
                    events.append({
                        "type": row[0].strip() if row[0] else "",
                        "direction_action": row[1].strip() if row[1] else "",
                        "price": float(row[2]) if row[2] else 0.0,
                        "time": row[3],
                        "timeframe": row[4],
                        "status": row[5]
                    })
        except Exception as e:
            logger.error(f"Gagal mengambil data event dari llhhbosdata_xauusd: {e}")
        return events

    # ── Public analyze Method ──────────────────────────────────────────────

    def analyze(
        self,
        df_m15: Optional[pd.DataFrame] = None,
        symbol: str = "XAUUSD",
        session: str = "Unknown",
        df_h1: Optional[pd.DataFrame] = None,
        df_h4: Optional[pd.DataFrame] = None,
        structure_events: Optional[List[Dict[str, Any]]] = None,
        veto_mode: str = "hard",
        price_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Analisis struktur pasar langsung dari Neon DB atau data historis jika dikirim.
        
        Args:
            df_m15: DataFrame M15 (digunakan untuk harga & EMA200 jika dalam simulasi)
            symbol: Simbol trading (default: XAUUSD)
            session: Sesi aktif (London, NewYork, Asia, Sydney)
            df_h1: DataFrame H1 (digunakan jika dalam simulasi)
            df_h4: DataFrame H4 (digunakan jika dalam simulasi)
            structure_events: Daftar event struktur historis jika dalam simulasi
            veto_mode: Mode veto filter tren makro (hard / soft / none)
            price_ratio: Skala normalisasi harga terhadap BaseReferencePrice 4500.0
        """
        conn = None
        try:
            # Mode Simulasi / Replay (data historis disediakan)
            if structure_events is not None and df_m15 is not None and len(df_m15) > 0:
                current_price = float(df_m15["close"].iloc[-1])
                if price_ratio is None:
                    price_ratio = round(current_price / 4500.0, 6) if current_price > 0 else 1.0
                
                # Baca EMA200 historis
                ema200_m15 = float(df_m15["ema200"].iloc[-1]) if "ema200" in df_m15.columns and not pd.isna(df_m15["ema200"].iloc[-1]) else current_price
                ema200_h1 = float(df_h1["ema200"].iloc[-1]) if df_h1 is not None and len(df_h1) > 0 and "ema200" in df_h1.columns and not pd.isna(df_h1["ema200"].iloc[-1]) else ema200_m15
                ema200_h4 = float(df_h4["ema200"].iloc[-1]) if df_h4 is not None and len(df_h4) > 0 and "ema200" in df_h4.columns and not pd.isna(df_h4["ema200"].iloc[-1]) else ema200_m15
                latest_candle = df_m15.iloc[-1].to_dict()
                
                # Map dan urutkan event struktur historis (time DESC)
                mapped_events = []
                for idx, ev in enumerate(structure_events):
                    mapped_events.append({
                        "type": (ev.get("type") or "").strip(),
                        "direction_action": (ev.get("direction") or "").strip(),
                        "price": float(ev["price"]) if ev.get("price") is not None else 0.0,
                        "time": ev.get("time"),
                        "timeframe": ev.get("timeframe"),
                        "status": ev.get("status"),
                        "_orig_idx": idx,
                    })
                
                events = [e for e in mapped_events if e.get("status") in ("Accepted", "Confirmed", None)]
                events.sort(key=lambda x: (x["time"] if x["time"] is not None else 0, x["_orig_idx"]), reverse=True)
                
                if len(events) < 3:
                    logger.warning(f"Jumlah event historis sangat sedikit: {len(events)} (butuh minimal 3)")
                    return self._no_signal_response("Data event historis terlalu sedikit")
            else:
                # Mode Live Trading (default Neon DB)
                conn = self._get_db_conn()
                
                # Ambil parameter terkini dari Neon DB
                current_price = self._get_neon_current_price(conn)
                if not current_price:
                    return self._no_signal_response("Gagal mendapatkan data harga close terbaru dari database")
                if price_ratio is None:
                    price_ratio = round(current_price / 4500.0, 6) if current_price > 0 else 1.0

                ema200_m15 = self._get_neon_ema200(conn, "M15")
                ema200_h1  = self._get_neon_ema200(conn, "H1")
                ema200_h4  = self._get_neon_ema200(conn, "H4")
                latest_candle = None

                # Ambil event terbaru dari llhhbosdata_xauusd
                events = self._fetch_neon_events(conn, limit=50)
                if len(events) < 3:
                    logger.warning(f"Jumlah event di DB sangat sedikit: {len(events)} (butuh minimal 3)")
                    return self._no_signal_response("Data event di database Neon terlalu sedikit")

            # Analisis sequence 3 event terbaru
            # e1: terbaru, e2: kedua terbaru, e3: ketiga terbaru
            e1 = events[0]
            e2 = events[1]
            e3 = events[2]

            logger.info(f"Analyzing 3 latest events: 1st={e1['type']} ({e1['direction_action']}), 2nd={e2['type']} ({e2['direction_action']}), 3rd={e3['type']} ({e3['direction_action']})")

            # Normalisasi tipe & arah
            t1 = e1["type"].upper()
            d1 = e1["direction_action"].upper()

            def _has_recent_choch(direction: str, max_lookback: int = 10) -> bool:
                """Match only the latest active CHoCH before e1.

                An opposite, newer CHoCH invalidates older CHoCH events. Continuing
                past it can turn a counter-swing into a new setup and overwrite the
                pending setup with the wrong direction.
                """
                for ev in events[1:max_lookback]:
                    t = ev["type"].upper()
                    d = ev["direction_action"].upper()
                    if "BOS" in t:
                        # BOS sudah terjadi, maka sequence CHoCH sebelumnya sudah selesai
                        return False
                    if "CHOCH" in t:
                        if direction == "Bullish":
                            return "BULL" in d or "UP" in d
                        return "BEAR" in d
                return False

            # ── Pemeriksaan Skenario ──

            # 0. CHoCH Aggressive Entry
            if "CHOCH" in t1:
                is_bullish = "BULL" in t1 or "BULL" in d1
                signal_result = self._on_choch_confirmed(
                    direction="Bullish" if is_bullish else "Bearish",
                    price=e1["price"],
                    event_timestamp=e1["time"],
                    current_price=current_price,
                    ema200_m15=ema200_m15,
                    ema200_h1=ema200_h1,
                    ema200_h4=ema200_h4,
                    session=session,
                    price_ratio=price_ratio,
                    veto_mode=veto_mode,
                )
                return self._build_response(
                    signal=signal_result["signal"],
                    confidence=signal_result["confidence"],
                    reasoning=signal_result["reasoning"],
                    phase=self._phase,
                    pre_signal=None,
                    events=events,
                    pattern_analysis=signal_result.get("pattern_analysis"),
                    current_price=current_price,
                    ema200=ema200_m15,
                    symbol=symbol,
                    price_ratio=price_ratio,
                )

            # 1. PENDING_SETUP - Bullish (CHoCH anywhere in recent events + HH terbentuk)
            if t1.startswith("HH") and _has_recent_choch("Bullish"):
                pre_signal = self._on_choch_hh_formed(
                    event_type="HH",
                    direction="Bullish",
                    price=e1["price"],
                    event_timestamp=e1["time"],
                    current_price=current_price,
                    ema200=ema200_m15,
                    ema200_h1=ema200_h1,
                    ema200_h4=ema200_h4,
                    session=session,
                    symbol=symbol,
                    price_ratio=price_ratio,
                    events=events,
                    latest_candle=latest_candle,
                )
                return self._build_response(
                    signal="HOLD",
                    confidence=pre_signal.get("initial_confidence", 0.4),
                    reasoning=pre_signal.get("reasoning", "CHoCH + HH terbentuk. Menunggu konfirmasi BoS."),
                    phase=self._phase,
                    pre_signal=pre_signal,
                    events=events,
                    pattern_analysis=self._pending_analysis,
                    current_price=current_price,
                    ema200=ema200_m15,
                    symbol=symbol,
                    is_new_setup=True,
                    price_ratio=price_ratio,
                )

            # 2. PENDING_SETUP - Bearish (CHoCH anywhere in recent events + LL terbentuk)
            elif t1.startswith("LL") and _has_recent_choch("Bearish"):
                pre_signal = self._on_choch_hh_formed(
                    event_type="LL",
                    direction="Bearish",
                    price=e1["price"],
                    event_timestamp=e1["time"],
                    current_price=current_price,
                    ema200=ema200_m15,
                    ema200_h1=ema200_h1,
                    ema200_h4=ema200_h4,
                    session=session,
                    symbol=symbol,
                    price_ratio=price_ratio,
                    events=events,
                    latest_candle=latest_candle,
                )
                return self._build_response(
                    signal="HOLD",
                    confidence=pre_signal.get("initial_confidence", 0.4),
                    reasoning=pre_signal.get("reasoning", "CHoCH + LL terbentuk. Menunggu konfirmasi BoS."),
                    phase=self._phase,
                    pre_signal=pre_signal,
                    events=events,
                    pattern_analysis=self._pending_analysis,
                    current_price=current_price,
                    ema200=ema200_m15,
                    symbol=symbol,
                    is_new_setup=True,
                    price_ratio=price_ratio,
                )

            # 3. TRIGGER - Bullish BoS (CHoCH -> HH -> BoS), atau BoS lanjutan
            # (cycle 2, 3+) di swing bullish yang sama tanpa CHoCH baru.
            elif "BOS" in t1 and ("BULL" in d1 or "UP" in d1) and (
                (self._phase == AgentPhase.PENDING_SETUP and self._pending_pre_signal and self._pending_pre_signal.get("direction") == "Bullish")
                or (self._phase == AgentPhase.BOS_TRIGGERED and self._last_bos_direction == "Bullish")
            ):
                signal_result = self._on_bos_confirmed(
                    direction="Bullish",
                    price=e1["price"],
                    current_price=current_price,
                    ema200_m15=ema200_m15,
                    ema200_h1=ema200_h1,
                    ema200_h4=ema200_h4,
                    session=session,
                    veto_mode=veto_mode,
                )
                return self._build_response(
                    signal=signal_result["signal"],
                    confidence=signal_result["confidence"],
                    reasoning=signal_result["reasoning"],
                    phase=self._phase,
                    pre_signal=self._pending_pre_signal,
                    events=events,
                    pattern_analysis=self._pending_analysis,
                    current_price=current_price,
                    ema200=ema200_m15,
                    symbol=symbol,
                    price_ratio=price_ratio,
                )

            # 4. TRIGGER - Bearish BoS (CHoCH -> LL -> BoS), atau BoS lanjutan
            # (cycle 2, 3+) di swing bearish yang sama tanpa CHoCH baru.
            elif "BOS" in t1 and "BEAR" in d1 and (
                (self._phase == AgentPhase.PENDING_SETUP and self._pending_pre_signal and self._pending_pre_signal.get("direction") == "Bearish")
                or (self._phase == AgentPhase.BOS_TRIGGERED and self._last_bos_direction == "Bearish")
            ):
                signal_result = self._on_bos_confirmed(
                    direction="Bearish",
                    price=e1["price"],
                    current_price=current_price,
                    ema200_m15=ema200_m15,
                    ema200_h1=ema200_h1,
                    ema200_h4=ema200_h4,
                    session=session,
                    veto_mode=veto_mode,
                )
                return self._build_response(
                    signal=signal_result["signal"],
                    confidence=signal_result["confidence"],
                    reasoning=signal_result["reasoning"],
                    phase=self._phase,
                    pre_signal=self._pending_pre_signal,
                    events=events,
                    pattern_analysis=self._pending_analysis,
                    current_price=current_price,
                    ema200=ema200_m15,
                    symbol=symbol,
                    price_ratio=price_ratio,
                )

            # 5. Default Neutral / HOLD
            return self._build_response(
                signal="HOLD",
                confidence=0.3,
                reasoning=f"Kondisi struktur saat ini: {e1['type']} ({e1['direction_action']}) pada {e1['time']}. Belum memenuhi sequence CHoCH -> HH/LL -> BoS.",
                phase=self._phase,
                pre_signal=None,
                events=events,
                pattern_analysis=None,
                current_price=current_price,
                ema200=ema200_m15,
                symbol=symbol,
                price_ratio=price_ratio,
            )

        except Exception as e:
            logger.error(f"[ERROR] {self.name} gagal menganalisis: {e}")
            return self._error_response(str(e))
        finally:
            if conn:
                conn.close()

    def reset_state(self) -> None:
        """Reset state machine ke IDLE."""
        self._phase = AgentPhase.IDLE
        self._pending_hh_price = None
        self._pending_ll_price = None
        self._pending_analysis = None
        self._pending_pre_signal = None
        self._pending_evidence_snapshot = None
        self._last_bos_direction = None
        logger.info(f"[RESET] {self.name} state reset -> IDLE")

    def get_pending_setup(self) -> Optional[Dict]:
        """Ambil data pre-signal yang sedang dalam antrean (PENDING_SETUP)."""
        if self._phase == AgentPhase.PENDING_SETUP:
            return self._pending_pre_signal
        return None

    def get_info(self) -> Dict[str, Any]:
        """Info agent."""
        return {
            "name": self.name,
            "version": self.version,
            "type": "market_structure",
            "description": "Membaca data struktur pasar langsung dari Neon DB, mendukung logic sequence 2-Tahap.",
            "capabilities": [
                "Membaca event dari llhhbosdata_xauusd",
                "Kalkulasi multi-TF EMA (M15, H1, H4) dari Neon DB",
                "State machine dua tahap (Pre-Analysis -> Execution Trigger)",
                "Pencocokan pola historis menggunakan LanceDB",
            ],
            "voting_weight": 0.25,
            "config": {
                "swing_length": self.swing_length,
                "timeframe": self.timeframe,
                "use_patterns": self.use_patterns,
                "current_phase": self._phase.value,
            }
        }

    # ── Tahap 1: Pre-Analysis ──────────────────────────────────────────────

    def _on_choch_hh_formed(
        self,
        event_type: str,
        direction: str,
        price: float,
        event_timestamp: Any,
        current_price: float,
        ema200: float,
        ema200_h1: Optional[float],
        ema200_h4: Optional[float],
        session: str,
        symbol: str,
        price_ratio: float,
        events: List[Dict[str, Any]],
        latest_candle: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Tahap 1 - Dijalankan saat CHoCH + HH/LL terbentuk."""
        logger.info(f"[PRE-ANALYSIS] Tahap 1: Pre-Analysis | {event_type} @ {price:.2f}")

        # Simpan level referensi
        if direction == "Bullish":
            self._pending_hh_price = price
        else:
            self._pending_ll_price = price

        # Query LanceDB: Mencocokkan kesamaan pola BoS jika kelak tertembus (Step 3)
        pattern_analysis = None
        if self.use_patterns and self.pattern_matcher:
            pattern_analysis = self._analyze_patterns(
                event_type="BoS",
                direction=direction,
                price=price,
                ema200=ema200,
                session=session,
                timeframe=self.timeframe,
                prior_choch=True,
                timestamp=event_timestamp,
                price_ratio=price_ratio,
            )
        self._pending_analysis = pattern_analysis

        # Hitung initial confidence awal (Step 4)
        initial_conf = 0.4
        win_rate = 0.0
        if pattern_analysis and pattern_analysis.get("total_count", 0) >= 5:
            win_rate = pattern_analysis.get("win_rate", 0.0)
            initial_conf = self._apply_winrate_boost(initial_conf, win_rate)

        action_dir = "di atas HH" if direction == "Bullish" else "di bawah LL"
        reasoning = (
            f"Tahap 1: Setup awal terdeteksi ({event_type} - {direction}). "
            f"Menunggu konfirmasi penutupan harga {action_dir} ({price:.2f}) untuk konfirmasi BoS. "
            f"Win rate historis: {win_rate:.1%} ({pattern_analysis.get('total_count', 0) if pattern_analysis else 0} pola serupa)."
        )

        pre_signal = {
            "setup_id": self._build_setup_id(
                symbol=symbol,
                timeframe=self.timeframe,
                event_type=event_type,
                direction=direction,
                event_timestamp=event_timestamp,
                trigger_price=price,
            ),
            "event_type": event_type,
            "direction": direction,
            "hh_price": self._pending_hh_price,
            "ll_price": self._pending_ll_price,
            "initial_confidence": round(initial_conf, 3),
            "win_rate_historical": win_rate,
            "pattern_count": pattern_analysis.get("total_count", 0) if pattern_analysis else 0,
            "session": session,
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "market_event_timestamp": event_timestamp,
            "price_ratio": price_ratio,
            "reasoning": reasoning,
            "status": "PENDING_SETUP - menunggu BoS",
        }

        self._pending_evidence_snapshot = self._build_evidence_snapshot(
            pre_signal=pre_signal,
            events=events,
            pattern_analysis=pattern_analysis,
            current_price=current_price,
            ema200_m15=ema200,
            ema200_h1=ema200_h1,
            ema200_h4=ema200_h4,
            price_ratio=price_ratio,
            latest_candle=latest_candle,
        )

        # Pindah state ke PENDING_SETUP
        self._phase = AgentPhase.PENDING_SETUP
        self._pending_pre_signal = pre_signal

        logger.info(f"[OK] Tahap 1 Selesai | State: PENDING_SETUP | Win Rate: {win_rate:.1%}")
        return pre_signal

    def _on_choch_confirmed(
        self,
        direction: str,
        price: float,
        event_timestamp: Any,
        current_price: float,
        ema200_m15: float,
        ema200_h1: Optional[float],
        ema200_h4: Optional[float],
        session: str,
        price_ratio: float,
        veto_mode: str = "hard",
    ) -> Dict[str, Any]:
        """Dijalankan saat CHoCH langsung terkonfirmasi untuk entri agresif."""
        logger.info(f"[TRIGGER] CHoCH langsung terkonfirmasi @ {price:.2f}")

        is_bullish = direction == "Bullish"

        # Kalkulasi multi-TF EMA
        tf_score, tf_reasoning = self._calculate_multi_tf_score(
            is_bullish=is_bullish,
            current_price=current_price,
            ema200_m15=ema200_m15,
            ema200_h1=ema200_h1,
            ema200_h4=ema200_h4,
        )

        confidence = 0.5 + tf_score

        # Boost/Penalty dari win rate historis pola CHoCH
        win_rate = 0.0
        pattern_count = 0
        pattern_reasoning = ""
        
        # Query LanceDB untuk pola CHoCH
        pattern_analysis = None
        if self.use_patterns and self.pattern_matcher:
            try:
                pattern_analysis = self._analyze_patterns(
                    event_type="CHoCH",
                    direction=direction,
                    price=price,
                    ema200=ema200_m15,
                    session=session,
                    timeframe=self.timeframe,
                    prior_choch=False,
                    timestamp=event_timestamp,
                    price_ratio=price_ratio,
                )
            except Exception as e:
                logger.warning(f"Gagal mencari pola CHoCH di LanceDB: {e}")
                
        if pattern_analysis and pattern_analysis.get("total_count", 0) >= 5:
            win_rate = pattern_analysis.get("win_rate", 0.0)
            pattern_count = pattern_analysis.get("total_count", 0)
            avg_profit = pattern_analysis.get("avg_profit", 0.0)
            confidence = self._apply_winrate_boost(confidence, win_rate)
            pattern_reasoning = self._winrate_reasoning(win_rate, pattern_count, avg_profit)
        else:
            pattern_reasoning = "Data historis tidak mencukupi untuk penyesuaian skor."

        confidence = round(max(0.0, min(1.0, confidence)), 3)
        signal = "BUY" if is_bullish else "SELL"

        # Veto jika confidence kurang dari 60% dan veto_mode adalah hard
        if confidence < 0.6 and veto_mode == "hard":
            signal = "HOLD"
            logger.warning(f"[VETO] Sinyal CHoCH diubah ke HOLD karena confidence ({confidence:.2f}) < 0.60")

        reasoning = (
            f"CHoCH {direction} langsung terkonfirmasi pada level {price:.2f}. "
            f"{tf_reasoning} "
            f"{pattern_reasoning}"
        )

        logger.info(f"[OK] Sinyal CHoCH Final: {signal} | Confidence: {confidence:.2f}")

        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "win_rate": win_rate,
            "pattern_count": pattern_count,
            "tf_score": tf_score,
            "pattern_analysis": pattern_analysis,
        }

    # ── Tahap 2: Execution Trigger ─────────────────────────────────────────

    def _on_bos_confirmed(
        self,
        direction: str,
        price: float,
        current_price: float,
        ema200_m15: float,
        ema200_h1: Optional[float],
        ema200_h4: Optional[float],
        session: str,
        veto_mode: str = "hard",
    ) -> Dict[str, Any]:
        """Tahap 2 - Dijalankan saat BoS terkonfirmasi."""
        logger.info(f"[TRIGGER] Tahap 2: BoS terkonfirmasi @ {price:.2f}")

        is_bullish = direction == "Bullish"

        # Kalkulasi multi-TF EMA
        tf_score, tf_reasoning = self._calculate_multi_tf_score(
            is_bullish=is_bullish,
            current_price=current_price,
            ema200_m15=ema200_m15,
            ema200_h1=ema200_h1,
            ema200_h4=ema200_h4,
        )

        confidence = 0.5 + tf_score

        # Boost/Penalty dari win rate historis (dari data Tahap 1)
        win_rate = 0.0
        pattern_count = 0
        pattern_reasoning = ""
        if self._pending_analysis and self._pending_analysis.get("total_count", 0) >= 5:
            win_rate = self._pending_analysis.get("win_rate", 0.0)
            pattern_count = self._pending_analysis.get("total_count", 0)
            avg_profit = self._pending_analysis.get("avg_profit", 0.0)
            confidence = self._apply_winrate_boost(confidence, win_rate)
            pattern_reasoning = self._winrate_reasoning(win_rate, pattern_count, avg_profit)
        else:
            pattern_reasoning = "Data historis tidak mencukupi untuk penyesuaian skor."

        confidence = round(max(0.0, min(1.0, confidence)), 3)
        signal = "BUY" if is_bullish else "SELL"

        # Veto jika confidence kurang dari 60% dan veto_mode adalah hard
        if confidence < 0.6 and veto_mode == "hard":
            signal = "HOLD"
            logger.warning(f"[VETO] Sinyal diubah ke HOLD karena confidence ({confidence:.2f}) < 0.60")

        reasoning = (
            f"BoS {direction} terkonfirmasi pada level {price:.2f}. "
            f"{tf_reasoning} "
            f"{pattern_reasoning}"
        )

        # Ubah phase
        self._phase = AgentPhase.BOS_TRIGGERED
        self._last_bos_direction = direction

        logger.info(f"[OK] Tahap 2 Selesai | Sinyal Final: {signal} | Confidence: {confidence:.2f}")

        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "win_rate": win_rate,
            "pattern_count": pattern_count,
            "tf_score": tf_score,
        }

    # ── Helpers ────────────────────────────────────────────────────────────

    def _calculate_multi_tf_score(
        self,
        is_bullish: bool,
        current_price: float,
        ema200_m15: float,
        ema200_h1: Optional[float],
        ema200_h4: Optional[float],
    ) -> tuple[float, str]:
        """Kalkulasi skor keselarasan EMA200 multi-timeframe."""
        score = 0.0
        parts = []

        # M15 (+0.2 / 0.0)
        m15_aligned = current_price > ema200_m15 if is_bullish else current_price < ema200_m15
        if m15_aligned:
            score += 0.2
            parts.append(f"M15 EMA Aligned (+0.2, EMA={ema200_m15:.2f})")
        else:
            parts.append(f"M15 EMA Misaligned (+0.0, EMA={ema200_m15:.2f})")

        # H1 (+0.1 / -0.1)
        if ema200_h1 is not None:
            h1_aligned = current_price > ema200_h1 if is_bullish else current_price < ema200_h1
            if h1_aligned:
                score += 0.1
                parts.append(f"H1 EMA Aligned (+0.1, EMA={ema200_h1:.2f})")
            else:
                score -= 0.1
                parts.append(f"H1 EMA Misaligned (-0.1, EMA={ema200_h1:.2f})")
        else:
            parts.append("H1 EMA N/A")

        # H4 (+0.1 / -0.1)
        if ema200_h4 is not None:
            h4_aligned = current_price > ema200_h4 if is_bullish else current_price < ema200_h4
            if h4_aligned:
                score += 0.1
                parts.append(f"H4 EMA Aligned (+0.1, EMA={ema200_h4:.2f})")
            else:
                score -= 0.1
                parts.append(f"H4 EMA Misaligned (-0.1, EMA={ema200_h4:.2f})")
        else:
            parts.append("H4 EMA N/A")

        reasoning = " | ".join(parts) + "."
        return round(score, 2), reasoning

    def _apply_winrate_boost(self, confidence: float, win_rate: float) -> float:
        """Boost / Penalty confidence berdasarkan win rate historis."""
        if win_rate >= 0.75:
            confidence += 0.3
        elif win_rate >= 0.60:
            confidence += 0.2
        elif win_rate >= 0.45:
            confidence += 0.1
        else:
            confidence -= 0.1
        return confidence

    def _winrate_reasoning(self, win_rate: float, count: int, avg_profit: float) -> str:
        """Keterangan win rate historis."""
        if win_rate >= 0.75:
            return f"Win rate historis sangat baik ({win_rate:.1%}, {count} pola, avg {avg_profit:.1f} pips) → +0.3 boost."
        elif win_rate >= 0.60:
            return f"Win rate historis baik ({win_rate:.1%}, {count} pola, avg {avg_profit:.1f} pips) → +0.2 boost."
        elif win_rate >= 0.45:
            return f"Win rate historis sedang ({win_rate:.1%}, {count} pola) → +0.1 boost."
        else:
            return f"[WARNING] Win rate historis rendah ({win_rate:.1%}, {count} pola) -> -0.1 penalty."

    def _analyze_patterns(
        self,
        event_type: str,
        direction: str,
        price: float,
        ema200: float,
        session: str,
        timeframe: str,
        prior_choch: bool = False,
        timestamp: Any = None,
        price_ratio: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Query ke database vektor LanceDB untuk melihat kesamaan pola."""
        try:
            result = self.pattern_matcher.find_similar_patterns(
                event_type=event_type,
                direction=direction,
                price=price,
                ema200=ema200,
                session=session,
                timeframe=timeframe,
                limit=1000,
                min_similarity=0.7,
                prior_choch=prior_choch,
                timestamp=timestamp,
                price_ratio=price_ratio,
            )
            return result
        except Exception as e:
            logger.error(f"Pencarian pola di LanceDB gagal: {e}")
            return None

    @staticmethod
    def _build_setup_id(
        symbol: str,
        timeframe: str,
        event_type: str,
        direction: str,
        event_timestamp: Any,
        trigger_price: float,
    ) -> str:
        identity = "|".join([
            symbol,
            timeframe,
            event_type,
            direction,
            str(event_timestamp),
            f"{trigger_price:.5f}",
        ])
        return f"msa-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"

    def _build_evidence_snapshot(
        self,
        pre_signal: Dict[str, Any],
        events: List[Dict[str, Any]],
        pattern_analysis: Optional[Dict[str, Any]],
        current_price: float,
        ema200_m15: Optional[float],
        ema200_h1: Optional[float],
        ema200_h4: Optional[float],
        price_ratio: float,
        latest_candle: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        warnings = []
        atr_value = None
        candle_quality = {
            "body_ratio": None,
            "range": None,
            "direction": None,
        }

        if latest_candle:
            raw_atr = latest_candle.get("atr")
            if raw_atr is not None and not pd.isna(raw_atr):
                atr_value = float(raw_atr)

            required = ("open", "high", "low", "close")
            if all(latest_candle.get(key) is not None and not pd.isna(latest_candle.get(key)) for key in required):
                open_price = float(latest_candle["open"])
                high_price = float(latest_candle["high"])
                low_price = float(latest_candle["low"])
                close_price = float(latest_candle["close"])
                candle_range = high_price - low_price
                candle_quality = {
                    "body_ratio": abs(close_price - open_price) / candle_range if candle_range > 0 else 0.0,
                    "range": candle_range,
                    "direction": "BULLISH" if close_price > open_price else "BEARISH" if close_price < open_price else "DOJI",
                }

        if atr_value is None:
            warnings.append("ATR unavailable")
        if candle_quality["body_ratio"] is None:
            warnings.append("Candle OHLC quality unavailable")
        if pattern_analysis is None:
            warnings.append("Historical pattern evidence unavailable")

        trigger_price = pre_signal["hh_price"] or pre_signal["ll_price"]
        raw_distance = abs(current_price - trigger_price)

        return {
            "schema_version": "msa-evidence-v1",
            "setup_id": pre_signal["setup_id"],
            "generated_at": datetime.now().isoformat(),
            "market_event_timestamp": pre_signal["market_event_timestamp"],
            "setup": {
                "symbol": pre_signal["symbol"],
                "timeframe": self.timeframe,
                "event_type": pre_signal["event_type"],
                "direction": pre_signal["direction"],
                "session": pre_signal["session"],
                "status": pre_signal["status"],
            },
            "structure_context": {
                "trigger_price": trigger_price,
                "current_price": current_price,
                "raw_distance_to_trigger": raw_distance,
                "price_ratio_scaled_distance": raw_distance / price_ratio if price_ratio > 0 else None,
                "atr_multiple_to_trigger": raw_distance / atr_value if atr_value and atr_value > 0 else None,
                "recent_events": events[:5],
            },
            "market_context": {
                "price_ratio": price_ratio,
                "base_reference_price": 4500.0,
                "ema200": {
                    "M15": ema200_m15,
                    "H1": ema200_h1,
                    "H4": ema200_h4,
                },
                "atr": {"value": atr_value, "timeframe": self.timeframe},
                "candle_quality": candle_quality,
            },
            "historical_evidence": pattern_analysis,
            "data_quality": {
                "is_complete": not warnings,
                "warnings": warnings,
            },
            "llm_constraints": {
                "role": "context_critic",
                "may_create_trade_signal": False,
                "may_reverse_direction": False,
                "may_set_lot_sl_tp": False,
                "may_change_msa_state": False,
                "may_bypass_risk_management": False,
            },
        }

    def _build_response(
        self,
        signal: str,
        confidence: float,
        reasoning: str,
        phase: AgentPhase,
        pre_signal: Optional[Dict],
        events: List[Dict],
        pattern_analysis: Optional[Dict],
        current_price: float,
        ema200: Optional[float],
        symbol: str,
        is_new_setup: bool = False,
        price_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Hasilkan format response dictionary standar."""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "timeframe": self.timeframe,
            "signal": signal,
            "confidence": round(confidence, 3),
            "reasoning": reasoning,
            "phase": phase.value,
            "is_new_setup": is_new_setup,
            "pre_signal": pre_signal,
            "structure_events": events[:5],  # 5 event terakhir
            "current_state": {
                "phase": phase.value,
                "pending_hh": self._pending_hh_price,
                "pending_ll": self._pending_ll_price,
            },
            "pattern_analysis": pattern_analysis,
            "evidence_snapshot": self._pending_evidence_snapshot,
            "metadata": {
                "total_events_checked": len(events),
                "current_price": current_price,
                "price_ratio": price_ratio if price_ratio is not None else (round(current_price / 4500.0, 6) if current_price > 0 else 1.0),
                "base_reference_price": 4500.0,
                "ema200_m15": ema200,
                "price_vs_ema": "ABOVE" if ema200 and current_price > ema200 else "BELOW" if ema200 else "N/A",
            }
        }

    def _no_signal_response(self, reason: str) -> Dict[str, Any]:
        """Response standar saat tidak ada sinyal."""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": reason,
            "phase": self._phase.value,
            "pre_signal": None,
            "structure_events": [],
            "current_state": {},
            "pattern_analysis": None,
            "metadata": {}
        }

    def _error_response(self, error: str) -> Dict[str, Any]:
        """Response standar saat error."""
        return {
            "agent": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": f"Analisis error: {error}",
            "phase": self._phase.value,
            "pre_signal": None,
            "structure_events": [],
            "current_state": {},
            "pattern_analysis": None,
            "metadata": {"error": error}
        }


if __name__ == "__main__":
    logger.info("Menjalankan test local untuk MarketStructureAgent v3.0.0...")
    agent = MarketStructureAgent(use_patterns=False)
    # Coba jalankan analyze
    try:
        res = agent.analyze(session="London")
        logger.info(f"Hasil Sinyal: {res['signal']} | Confidence: {res['confidence']} | Phase: {res['phase']}")
        logger.info(f"Reasoning: {res['reasoning']}")
    except Exception as exc:
        logger.exception(f"Test gagal: {exc}")
