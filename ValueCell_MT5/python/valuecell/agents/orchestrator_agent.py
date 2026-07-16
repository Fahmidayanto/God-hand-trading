"""
Orchestrator Agent - Multi-Agent Consensus Engine

This agent coordinates all trading agents and generates consensus decisions:
1. Market Structure Agent - Detects structure signals
2. ML Prediction Agent - Validates signals with ML model
3. Risk Management Agent - Calculates position sizing & SL/TP
4. Sentiment Agent - Adjusts for news & economic events

Workflow:
- Parallel execution of independent agents
- Weighted voting system for signal consensus
- Conflict resolution logic
- Final decision with confidence score
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from loguru import logger

from .market_structure_agent import MarketStructureAgent
from .ml_prediction_agent import MLPredictionAgent
from .risk_management_agent import RiskManagementAgent
from .sentiment_agent import SentimentAgent


class VoteWeight(Enum):
    """Agent voting weights"""
    MARKET_STRUCTURE = 0.25  # 25%
    ML_PREDICTION = 0.40     # 40% (highest - ML model is most accurate)
    RISK_MANAGEMENT = 0.15   # 15%
    SENTIMENT = 0.20         # 20%


class ConsensusLevel(Enum):
    """Consensus strength levels"""
    UNANIMOUS = "unanimous"   # All agents agree (100%)
    STRONG = "strong"         # 80%+ agreement
    MODERATE = "moderate"     # 60-79% agreement
    WEAK = "weak"            # 50-59% agreement
    NO_CONSENSUS = "no_consensus"  # <50%


class OrchestratorAgent:
    """
    Orchestrator Agent - Coordinates all agents and generates consensus.
    
    Purpose:
    - Execute all agents in optimal order
    - Aggregate signals and confidence scores
    - Apply weighted voting for final decision
    - Resolve conflicts between agents
    - Generate comprehensive trade recommendations
    
    Workflow:
    1. Market Structure Agent analyzes price action
    2. ML Prediction Agent validates structure signal
    3. Sentiment Agent adjusts for news/events
    4. Risk Management Agent calculates position sizing
    5. Orchestrator generates weighted consensus
    """
    
    def __init__(
        self,
        enable_market_structure: bool = True,
        enable_ml_prediction: bool = True,
        enable_risk_management: bool = True,
        enable_sentiment: bool = True,
        consensus_threshold: float = 0.60,
        **agent_configs
    ):
        """
        Initialize Orchestrator Agent.
        
        Args:
            enable_*: Enable/disable specific agents
            consensus_threshold: Minimum weighted score for approval (0-1)
            **agent_configs: Configuration for individual agents
        """
        self.name = "OrchestratorAgent"
        self.version = "1.0.0"
        
        self.consensus_threshold = consensus_threshold
        
        # Initialize agents
        self.agents = {}
        
        if enable_market_structure:
            ms_config = agent_configs.get("market_structure", {})
            self.agents["market_structure"] = MarketStructureAgent(**ms_config)
        
        if enable_ml_prediction:
            ml_config = agent_configs.get("ml_prediction", {})
            self.agents["ml_prediction"] = MLPredictionAgent(**ml_config)
        
        if enable_risk_management:
            risk_config = agent_configs.get("risk_management", {})
            self.agents["risk_management"] = RiskManagementAgent(**risk_config)
        
        if enable_sentiment:
            sentiment_config = agent_configs.get("sentiment", {})
            self.agents["sentiment"] = SentimentAgent(**sentiment_config)
        
        self._latest_warmup_results = None
        
        logger.info(
            f"✅ {self.name} v{self.version} initialized | "
            f"Active agents: {len(self.agents)} | "
            f"Consensus threshold: {consensus_threshold:.0%}"
        )
    
    def analyze(
        self,
        market_data: Dict[str, Any],
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        veto_mode: str = "hard"
    ) -> Dict[str, Any]:
        """
        Orchestrate all agents and generate consensus decision.
        
        Args:
            market_data: Complete market data package containing:
                - df: DataFrame with OHLCV + indicators
                - current_bar: Current bar data
                - structure_events: Market structure events
                - h1_data: H1 timeframe data (optional)
                - m15_history: M15 history (optional)
                - news_headlines: Recent news (optional)
                - upcoming_events: Economic calendar (optional)
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Comprehensive consensus decision with all agent results
        """
        try:
            logger.debug(f"🎯 {self.name} orchestrating analysis for {symbol} {timeframe}...")
            
            start_time = datetime.now()
            agent_results = {}
            
            # === STEP 1: Market Structure Analysis ===
            if "market_structure" in self.agents:
                logger.debug("📊 Step 1: Market Structure Analysis...")
                ms_result = self.agents["market_structure"].analyze(
                    df_m15=market_data["df"],
                    symbol=symbol,
                    session=market_data.get("session", "Other"),
                    df_h1=market_data.get("h1_data"),   # Multi-TF EMA scoring H1
                    df_h4=market_data.get("h4_data"),   # Multi-TF EMA scoring H4
                    structure_events=market_data.get("structure_events"),
                    veto_mode=veto_mode,
                )
                agent_results["market_structure"] = ms_result
                logger.debug(f"   → Signal: {ms_result['signal']} | Confidence: {ms_result['confidence']:.3f}")
                # === STEP 2 & 3: ML Validation & Sentiment Analysis ===
            ms_result = agent_results.get("market_structure")
            if ms_result:
                ms_signal = ms_result["signal"]
                pre_signal = ms_result.get("pre_signal")
                is_warmup = ms_signal == "HOLD" and pre_signal is not None
                
                # Clear cache if the setup is IDLE (reset) or if it's a new setup formation
                if ms_result.get("phase") == "IDLE" or ms_result.get("is_new_setup") is True:
                    self._latest_warmup_results = None
                
                use_cache = (is_warmup or ms_signal in ["BUY", "SELL"]) and self._latest_warmup_results is not None
                
                run_ml = "ml_prediction" in self.agents and (ms_signal in ["BUY", "SELL"] or is_warmup)
                run_sent = "sentiment" in self.agents
                
                if use_cache:
                    # Run a fresh ML prediction on confirmed execution triggers (BUY/SELL)
                    # to match the feature alignment of the training dataset.
                    if ms_signal in ["BUY", "SELL"] and "ml_prediction" in self.agents:
                        logger.debug("🔍 Running fresh ML validation on execution trigger bar...")
                        ml_result = self.agents["ml_prediction"].analyze({
                                "current_bar": market_data["current_bar"],
                                "structure_events": market_data.get("structure_events", []),
                                "h1_data": market_data.get("h1_data"),
                                "h4_data": market_data.get("h4_data"),
                                "m15_history": market_data.get("m15_history"),
                                "session": market_data.get("session", "Other"),
                                "session_zone": market_data.get("session_zone"),
                                **{k: v for k, v in {
                                    "spread": market_data.get("spread"),
                                    "init_risk_points": market_data.get("init_risk_points"),
                                    "init_reward_points": market_data.get("init_reward_points"),
                                }.items() if v is not None}
                            },
                            structure_signal=ms_signal,
                            symbol=symbol,
                        )
                    else:
                        ml_result = self._latest_warmup_results.get("ml_prediction")
                        
                    agent_results["ml_prediction"] = ml_result
                    
                    if ms_signal in ["BUY", "SELL"]:
                        logger.info("⚡ Execution Trigger: Combining warmup news with current news for updated sentiment analysis...")
                        # Combine headlines from warmup and current execution
                        warmup_news = self._latest_warmup_results.get("news_headlines", [])
                        current_news = market_data.get("news_headlines", [])
                        
                        combined_news = []
                        seen_headlines = set()
                        for item in warmup_news + current_news:
                            hl = item.get("headline", "").strip()
                            if hl and hl not in seen_headlines:
                                seen_headlines.add(hl)
                                combined_news.append(item)
                                
                        warmup_events = self._latest_warmup_results.get("upcoming_events", [])
                        current_events = market_data.get("upcoming_events", [])
                        
                        combined_events = []
                        seen_events = set()
                        for item in warmup_events + current_events:
                            evt = item.get("event", "").strip()
                            if evt and evt not in seen_events:
                                seen_events.add(evt)
                                combined_events.append(item)
                                
                        # Run fresh sentiment analysis on combined news
                        sentiment_result = self.agents["sentiment"].analyze(
                            signal=ms_signal,
                            confidence=ms_result["confidence"],
                            current_time=market_data["current_bar"]["time"],
                            news_headlines=combined_news,
                            upcoming_events=combined_events,
                            symbol=symbol
                        )
                        agent_results["sentiment"] = sentiment_result
                    else:
                        # Fallback for other warmup states if any
                        sentiment_result = self._latest_warmup_results["sentiment"]
                        agent_results["sentiment"] = sentiment_result
                    
                    ml_prob = ml_result.get("probability", ml_result.get("expected_rr", 0.0))
                    prob_label = "Expected R:R" if "expected_rr" in ml_result else "Probability"
                    logger.debug(f"   → Execution (Cached) ML Signal: {ml_result['signal']} | {prob_label}: {ml_prob:.3f}")
                    logger.debug(f"   → Execution (Updated Combined) Sentiment Adjustment: {sentiment_result['confidence_adjustment']:+.3f} | Filtered: {sentiment_result['filtered']}")
                    
                elif is_warmup and run_ml and run_sent:
                    logger.debug("⚡ Warm-up mode: Executing ML Agent and Sentiment Agent in PARALLEL...")
                    
                    pre_dir = pre_signal.get("direction", "Bullish")
                    warmup_signal = "BUY" if pre_dir == "Bullish" else "SELL"
                    warmup_conf = pre_signal.get("initial_confidence", 0.40)
                    
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                        # Submit ML Agent
                        future_ml = executor.submit(
                            self.agents["ml_prediction"].analyze, {
                                "current_bar": market_data["current_bar"],
                                "structure_events": market_data.get("structure_events", []),
                                "h1_data": market_data.get("h1_data"),
                                "h4_data": market_data.get("h4_data"),
                                "m15_history": market_data.get("m15_history"),
                                "session": market_data.get("session", "Other"),
                                "session_zone": market_data.get("session_zone"),
                                **{k: v for k, v in {
                                    "spread": market_data.get("spread"),
                                    "init_risk_points": market_data.get("init_risk_points"),
                                    "init_reward_points": market_data.get("init_reward_points"),
                                }.items() if v is not None}
                            },
                            structure_signal=warmup_signal,
                            symbol=symbol,
                            timeframe=timeframe
                        )
                        
                        # Submit Sentiment Agent
                        future_sent = executor.submit(
                            self.agents["sentiment"].analyze,
                            signal=warmup_signal,
                            confidence=warmup_conf,
                            current_time=market_data["current_bar"]["time"],
                            news_headlines=market_data.get("news_headlines"),
                            upcoming_events=market_data.get("upcoming_events"),
                            symbol=symbol
                        )
                        
                        # Gather results
                        ml_result = future_ml.result()
                        sentiment_result = future_sent.result()
                        
                    agent_results["ml_prediction"] = ml_result
                    agent_results["sentiment"] = sentiment_result
                    
                    # Store to cache
                    self._latest_warmup_results = {
                        "ml_prediction": ml_result,
                        "sentiment": sentiment_result,
                        "news_headlines": market_data.get("news_headlines", []),
                        "upcoming_events": market_data.get("upcoming_events", [])
                    }
                    
                    ml_prob = ml_result.get("probability", ml_result.get("expected_rr", 0.0))
                    prob_label = "Expected R:R" if "expected_rr" in ml_result else "Probability"
                    logger.debug(f"   → Parallel Warm-up ML Signal: {ml_result['signal']} | {prob_label}: {ml_prob:.3f}")
                    logger.debug(f"   → Parallel Warm-up Sentiment Adjustment: {sentiment_result['confidence_adjustment']:+.3f} | Filtered: {sentiment_result['filtered']}")
                    
                else:
                    # Sequential mode (Normal mode or if one of the agents is disabled)
                    # --- STEP 2: ML Prediction Validation ---
                    ml_result = None
                    if run_ml:
                        logger.debug("🤖 Step 2: ML Prediction Validation...")
                        target_signal = ms_signal
                        ml_result = self.agents["ml_prediction"].analyze({
                                "current_bar": market_data["current_bar"],
                                "structure_events": market_data.get("structure_events", []),
                                "h1_data": market_data.get("h1_data"),
                                "h4_data": market_data.get("h4_data"),
                                "m15_history": market_data.get("m15_history"),
                                "session": market_data.get("session", "Other"),
                                **{k: v for k, v in {
                                    "spread": market_data.get("spread"),
                                    "init_risk_points": market_data.get("init_risk_points"),
                                    "init_reward_points": market_data.get("init_reward_points"),
                                }.items() if v is not None}
                            },
                            structure_signal=target_signal,
                            symbol=symbol,
                            timeframe=timeframe
                        )
                        agent_results["ml_prediction"] = ml_result
                        ml_prob = ml_result.get("probability", ml_result.get("expected_rr", 0.0))
                        prob_label = "Expected R:R" if "expected_rr" in ml_result else "Probability"
                        logger.debug(f"   → Signal: {ml_result['signal']} | {prob_label}: {ml_prob:.3f}")
                    elif "ml_prediction" in self.agents:
                        logger.debug(f"   → Skipped ML (MS signal: {ms_signal})")
                        
                    # --- STEP 3: Sentiment Analysis ---
                    if run_sent:
                        logger.debug("📰 Step 3: Sentiment Analysis...")
                        base_signal = ms_signal
                        base_confidence = ms_result["confidence"]
                        
                        if ml_result:
                            # ML overrides if it ran
                            base_confidence = ml_result["confidence"]
                            base_signal = ml_result["signal"]
                            
                        if base_signal in ["BUY", "SELL"]:
                            sentiment_result = self.agents["sentiment"].analyze(
                                signal=base_signal,
                                confidence=base_confidence,
                                current_time=market_data["current_bar"]["time"],
                                news_headlines=market_data.get("news_headlines"),
                                upcoming_events=market_data.get("upcoming_events"),
                                symbol=symbol
                            )
                            agent_results["sentiment"] = sentiment_result
                            logger.debug(f"   → Adjustment: {sentiment_result['confidence_adjustment']:+.3f} | Filtered: {sentiment_result['filtered']}")
                        else:
                            logger.debug(f"   → Skipped Sentiment (signal: {base_signal})")
            
            # === STEP 4: Calculate Consensus ===
            logger.debug(f"⚖️ Step 4: Calculating Consensus (Veto Mode: {veto_mode})...")
            consensus = self._calculate_consensus(agent_results, market_data, veto_mode=veto_mode)
            
            # === STEP 5: Risk Management (if consensus approved) ===
            if "risk_management" in self.agents and consensus["approved"] and consensus["final_signal"] in ["BUY", "SELL"]:
                logger.debug("💼 Step 5: Risk Management Calculation...")
                
                # Check if v5 regression results are available
                ml_res = agent_results.get("ml_prediction")
                is_v5 = ml_res and ml_res.get("model_type") in ("regression_v5", "regression_v5_unconstrained")
                
                if is_v5:
                    expected_rr = ml_res["expected_rr"]
                    predicted_mfe = ml_res["predicted_mfe"]
                    predicted_mae = ml_res["predicted_mae"]
                    
                    sl_dist = (predicted_mae * 2.0) / 100.0
                    tp_dist = predicted_mfe / 100.0
                    sl_pips = (predicted_mae * 2.0) / 10.0
                    
                    entry_price = float(market_data["current_bar"]["close"])
                    if consensus["final_signal"] == "BUY":
                        sl_price = entry_price - sl_dist
                        tp_price = entry_price + tp_dist
                    else:
                        sl_price = entry_price + sl_dist
                        tp_price = entry_price - tp_dist
                        
                    rm = self.agents["risk_management"]
                    
                    # Calculate dynamic lot multiplier based on expected_rr
                    if expected_rr >= 1.8:
                        mult = 4.0
                    elif expected_rr >= 1.5:
                        mult = 2.4
                    elif expected_rr >= 1.2:
                        mult = 1.6
                    else:
                        mult = 1.0
                        
                    # Standard analyze call to validate risk and get baseline lot sizing
                    risk_result = rm.analyze(
                        signal=consensus["final_signal"],
                        confidence=consensus["final_confidence"],
                        entry_price=entry_price,
                        atr=market_data.get("atr", 7.0),
                        current_time=market_data["current_bar"]["time"],
                        session=market_data.get("session", "Other"),
                        symbol=symbol
                    )
                    
                    if risk_result["approved"]:
                        # Multiply lot size by multiplier and clamp to max_lot
                        raw_lot = risk_result["lot_size"] * mult
                        lot_size = max(rm.min_lot, min(rm.max_lot, raw_lot))
                        
                        actual_risk_usd = lot_size * sl_pips * rm.pip_value_per_lot
                        actual_risk_pct = (actual_risk_usd / rm.account_balance) * 100 if rm.account_balance > 0 else 0
                        
                        consensus["risk_approved"] = True
                        consensus["position_sizing"] = {
                            "lot_size": round(lot_size, 2),
                            "risk_pct": round(actual_risk_pct, 2),
                            "risk_usd": round(actual_risk_usd, 2),
                            "multiplier": mult,
                        }
                        consensus["sl_tp"] = {
                            "entry_price": entry_price,
                            "sl_price": round(sl_price, 2),
                            "tp_price": round(tp_price, 2),
                            "sl_distance_pips": round(sl_pips, 1),
                            "tp_distance_pips": round(predicted_mfe / 10.0, 1),
                            "rr_ratio": round(expected_rr, 2)
                        }
                        
                        agent_results["risk_management"] = {
                            "approved": True,
                            "signal": consensus["final_signal"],
                            "confidence": consensus["final_confidence"],
                            "lot_size": round(lot_size, 2),
                            "sl_price": round(sl_price, 2),
                            "tp_price": round(tp_price, 2),
                            "rr_ratio": round(expected_rr, 2),
                            "reasoning": (
                                f"v5 dynamic approval: {consensus['final_signal']} @ {consensus['final_confidence']:.1%} confidence. "
                                f"ML regression_v5 predicted MAE={predicted_mae:.1f} / MFE={predicted_mfe:.1f} pips. "
                                f"Lot {round(lot_size, 2)} (base {risk_result['lot_size']:.2f} × {mult}x multiplier from R:R {expected_rr:.2f}). "
                                f"Risk {actual_risk_pct:.2f}% of balance. SL {round(sl_price, 2)} / TP {round(tp_price, 2)}."
                            ),
                            "note": f"v5 dynamic parameters: Expected R:R={expected_rr:.2f} (mult: {mult}x)",
                        }
                        
                        logger.debug(f"   → v5 Approved: Lot {lot_size:.2f} (mult: {mult}x) | SL {sl_price:.2f} | TP {tp_price:.2f}")
                    else:
                        consensus["approved"] = False
                        consensus["risk_approved"] = False
                        consensus["final_signal"] = "HOLD"
                        logger.debug(f"   → Rejected by risk management (v5)")
                else:
                    # Standard v4 risk management behavior
                    risk_result = self.agents["risk_management"].analyze(
                        signal=consensus["final_signal"],
                        confidence=consensus["final_confidence"],
                        entry_price=market_data["current_bar"]["close"],
                        atr=market_data.get("atr", 7.0),
                        current_time=market_data["current_bar"]["time"],
                        session=market_data.get("session", "Other"),
                        symbol=symbol
                    )
                    agent_results["risk_management"] = risk_result
                    
                    if risk_result["approved"]:
                        consensus["risk_approved"] = True
                        consensus["position_sizing"] = {
                            "lot_size": risk_result["lot_size"],
                            "risk_pct": risk_result["risk_pct"],
                            "risk_usd": risk_result["risk_usd"]
                        }
                        consensus["sl_tp"] = {
                            "entry_price": risk_result["entry_price"],
                            "sl_price": risk_result["sl_price"],
                            "tp_price": risk_result["tp_price"],
                            "sl_distance_pips": risk_result["sl_distance_pips"],
                            "tp_distance_pips": risk_result["tp_distance_pips"],
                            "rr_ratio": risk_result["rr_ratio"]
                        }
                        logger.debug(f"   → Approved: Lot {risk_result['lot_size']:.2f} | SL {risk_result['sl_price']:.2f} | TP {risk_result['tp_price']:.2f}")
                    else:
                        consensus["approved"] = False
                        consensus["risk_approved"] = False
                        consensus["final_signal"] = "HOLD"
                        logger.debug(f"   → Rejected by risk management")
            
            # === Build Final Response ===
            execution_time = (datetime.now() - start_time).total_seconds()
            
            response = {
                "orchestrator": self.name,
                "version": self.version,
                "timestamp": start_time.isoformat(),
                "symbol": symbol,
                "timeframe": timeframe,
                "execution_time_ms": round(execution_time * 1000, 2),
                
                # Consensus decision
                **consensus,
                
                # Individual agent results
                "agent_results": agent_results,
                
                # Configuration
                "active_agents": list(self.agents.keys()),
                "consensus_threshold": self.consensus_threshold,
            }
            
            logger.info(
                f"✅ {self.name} complete | "
                f"Signal: {consensus['final_signal']} | "
                f"Confidence: {consensus['final_confidence']:.3f} | "
                f"Consensus: {consensus['consensus_level']} | "
                f"Time: {execution_time*1000:.0f}ms"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ {self.name} orchestration failed: {e}")
            return self._error_response(str(e), symbol, timeframe)
    
    def _calculate_consensus(
        self,
        agent_results: Dict[str, Dict[str, Any]],
        market_data: Dict[str, Any],
        veto_mode: str = "hard"
    ) -> Dict[str, Any]:
        """Calculate weighted consensus from all agent results"""
        
        # Collect signals and confidences
        signals = {}
        confidences = {}
        
        # Market Structure
        if "market_structure" in agent_results:
            ms = agent_results["market_structure"]
            signals["market_structure"] = ms["signal"]
            confidences["market_structure"] = ms["confidence"]
        
        # ML Prediction (overrides structure signal if present)
        if "ml_prediction" in agent_results:
            ml = agent_results["ml_prediction"]
            signals["ml_prediction"] = ml["signal"]
            confidences["ml_prediction"] = ml["confidence"]
        
        # Sentiment (provides adjusted confidence)
        if "sentiment" in agent_results:
            sent = agent_results["sentiment"]
            signals["sentiment"] = sent["final_signal"]
            confidences["sentiment"] = sent["final_confidence"]
        
        # Calculate weighted votes for each signal type
        vote_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        
        for agent_name, signal in signals.items():
            if agent_name == "market_structure":
                weight = VoteWeight.MARKET_STRUCTURE.value
            elif agent_name == "ml_prediction":
                weight = VoteWeight.ML_PREDICTION.value
            elif agent_name == "sentiment":
                weight = VoteWeight.SENTIMENT.value
            else:
                weight = 0.0
            
            # Weight by confidence
            confidence = confidences.get(agent_name, 0.0)
            vote_scores[signal] += weight * confidence
        
        # Determine winning signal
        final_signal = max(vote_scores, key=vote_scores.get)
        
        # Force final_signal to HOLD if Market Structure signal is HOLD (pre-analysis / warm-up / hard veto)
        # or if we are in soft veto mode, MSA has low confidence (< 0.60), and ML is not strong
        ms_signal = agent_results.get("market_structure", {}).get("signal", "HOLD")
        ms_confidence = agent_results.get("market_structure", {}).get("confidence", 1.0)
        
        apply_veto = False
        is_veto_bypassed = False
        
        if ms_signal == "HOLD":
            apply_veto = True
        elif veto_mode == "soft" and ms_confidence < 0.60:
            # Candidate for soft veto bypass
            ml_res = agent_results.get("ml_prediction", {})
            ml_rr = ml_res.get("expected_rr", 0.0) if ml_res else 0.0
            is_ml_strong = ml_res and ml_res.get("signal") in ("BUY", "SELL") and ml_rr >= 1.35
            
            if not is_ml_strong:
                apply_veto = True
            else:
                is_veto_bypassed = True
                reasoning_parts.append(f"⚠️ [Veto Bypassed] MSA Veto bypassed due to strong ML signal (Expected R:R {ml_rr:.2f} >= 1.35).")
                
        if apply_veto:
            final_signal = "HOLD"
            final_score = vote_scores["HOLD"]
        else:
            final_score = vote_scores[final_signal]
        
        # Calculate consensus level
        total_possible = (VoteWeight.MARKET_STRUCTURE.value +
                         VoteWeight.ML_PREDICTION.value +
                         VoteWeight.SENTIMENT.value)
        
        consensus_pct = final_score / total_possible if total_possible > 0 else 0.0
        
        if consensus_pct >= 0.95:
            consensus_level = ConsensusLevel.UNANIMOUS
        elif consensus_pct >= 0.80:
            consensus_level = ConsensusLevel.STRONG
        elif consensus_pct >= 0.60:
            consensus_level = ConsensusLevel.MODERATE
        elif consensus_pct >= 0.50:
            consensus_level = ConsensusLevel.WEAK
        else:
            consensus_level = ConsensusLevel.NO_CONSENSUS
        
        # Check if approved
        approved = (
            final_signal in ["BUY", "SELL"] and
            (consensus_pct >= self.consensus_threshold or is_veto_bypassed)
        )
        
        # Build reasoning
        reasoning_parts = []
        reasoning_parts.append(f"Consensus: {consensus_level.value} ({consensus_pct:.0%}).")
        reasoning_parts.append(f"Vote scores: BUY={vote_scores['BUY']:.2f}, SELL={vote_scores['SELL']:.2f}, HOLD={vote_scores['HOLD']:.2f}.")
        
        # Agent agreements
        agent_signals = [f"{k}:{v}" for k, v in signals.items()]
        reasoning_parts.append(f"Agent signals: {', '.join(agent_signals)}.")
        
        if approved:
            reasoning_parts.append(f"✅ Consensus reached for {final_signal}.")
        else:
            if final_signal == "HOLD":
                reasoning_parts.append("❌ No tradeable signal.")
            else:
                reasoning_parts.append(f"❌ Consensus too weak ({consensus_pct:.0%} < {self.consensus_threshold:.0%}).")

        # Append detailed agent explanations
        ms_res = agent_results.get("market_structure")
        if ms_res and ms_res.get("phase") == "BOS_TRIGGERED" and ms_res.get("reasoning"):
            reasoning_parts.append(f"[Market Structure] {ms_res['reasoning']}")

        ml_res = agent_results.get("ml_prediction")
        if ml_res and ml_res.get("reasoning"):
            reasoning_parts.append(f"[ML Filter] {ml_res['reasoning']}")

        sent_res = agent_results.get("sentiment")
        if sent_res and sent_res.get("reasoning"):
            reasoning_parts.append(f"[Sentiment] {sent_res['reasoning']}")

        rm_res = agent_results.get("risk_management")
        if rm_res and rm_res.get("reasoning"):
            reasoning_parts.append(f"[Risk Manager] {rm_res['reasoning']}")
        
        return {
            "final_signal": final_signal,
            "final_confidence": round(consensus_pct, 3),
            "consensus_level": consensus_level.value,
            "vote_scores": {k: round(v, 3) for k, v in vote_scores.items()},
            "approved": approved,
            "reasoning": " ".join(reasoning_parts),
            "risk_approved": None,  # Will be filled by risk management
            "position_sizing": None,
            "sl_tp": None,
        }
    
    def _error_response(self, error: str, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "orchestrator": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "timeframe": timeframe,
            "final_signal": "HOLD",
            "final_confidence": 0.0,
            "consensus_level": "no_consensus",
            "approved": False,
            "reasoning": f"Orchestration error: {error}",
            "error": error,
            "agent_results": {},
            "active_agents": [],
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get orchestrator information"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "orchestrator",
            "description": "Multi-agent consensus engine with weighted voting",
            "active_agents": list(self.agents.keys()),
            "agent_count": len(self.agents),
            "voting_weights": {
                "market_structure": VoteWeight.MARKET_STRUCTURE.value,
                "ml_prediction": VoteWeight.ML_PREDICTION.value,
                "risk_management": VoteWeight.RISK_MANAGEMENT.value,
                "sentiment": VoteWeight.SENTIMENT.value,
            },
            "consensus_levels": [level.value for level in ConsensusLevel],
            "consensus_threshold": self.consensus_threshold,
            "workflow": [
                "1. Market Structure Analysis (25% weight)",
                "2. ML Prediction Validation (40% weight)",
                "3. Sentiment Analysis (20% weight)",
                "4. Weighted Consensus Calculation",
                "5. Risk Management (if approved)"
            ]
        }

    def reset_state(self) -> None:
        """Reset state machine for all sub-agents and clear the warmup cache."""
        if "market_structure" in self.agents:
            self.agents["market_structure"].reset_state()
        self._latest_warmup_results = None
        logger.info("[RESET] OrchestratorAgent state and warmup cache reset -> IDLE")


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    import pandas as pd
    import numpy as np
    
    logger.info("Testing OrchestratorAgent...")
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(
        consensus_threshold=0.60,
        market_structure={"swing_length": 5, "timeframe": "M15"},
        risk_management={"account_balance": 1000.0}
    )
    
    # Get info
    info = orchestrator.get_info()
    logger.info(f"Orchestrator: {info['name']} v{info['version']}")
    logger.info(f"Active agents: {info['agent_count']}")
    
    # Create sample market data
    dates = pd.date_range(start="2024-01-01", periods=150, freq="15min")
    base_price = 2350.0
    trend = np.linspace(0, 30, 150)  # Bullish trend
    noise = np.random.normal(0, 3, 150)
    close_prices = base_price + trend + noise
    
    df = pd.DataFrame({
        "time": dates,
        "open": close_prices - np.random.uniform(1, 3, 150),
        "high": close_prices + np.random.uniform(1, 4, 150),
        "low": close_prices - np.random.uniform(1, 4, 150),
        "close": close_prices,
        "volume": np.random.randint(1000, 5000, 150),
        "ema200": base_price + trend * 0.7
    })
    
    market_data = {
        "df": df,
        "current_bar": df.iloc[-1].to_dict(),
        "structure_events": [
            {
                "type": "BOS_BULLISH",
                "price": 2360.0,
                "time": dates[-10]
            }
        ],
        "atr": 7.2,
        "session": "London",
        "news_headlines": ["Gold rises on safe haven demand"],
        "upcoming_events": []
    }
    
    # Run orchestrator
    result = orchestrator.analyze(market_data, symbol="XAUUSD", timeframe="M15")
    
    # Print results
    logger.info("=" * 70)
    logger.info("🎯 ORCHESTRATOR RESULT")
    logger.info("=" * 70)
    logger.info(f"Final Signal: {result['final_signal']}")
    logger.info(f"Confidence: {result['final_confidence']:.3f}")
    logger.info(f"Consensus: {result['consensus_level']}")
    logger.info(f"Approved: {result['approved']}")
    logger.info(f"Execution Time: {result['execution_time_ms']:.2f}ms")
    logger.info("")
    logger.info(f"Vote Scores:")
    for signal, score in result['vote_scores'].items():
        logger.info(f"  {signal}: {score:.3f}")
    logger.info("")
    logger.info(f"Reasoning: {result['reasoning']}")
    
    if result.get("position_sizing"):
        logger.info("")
        logger.info(f"Position Sizing:")
        logger.info(f"  Lot: {result['position_sizing']['lot_size']:.2f}")
        logger.info(f"  Risk: {result['position_sizing']['risk_pct']:.2f}%")
    
    if result.get("sl_tp"):
        logger.info("")
        logger.info(f"SL/TP:")
        logger.info(f"  Entry: {result['sl_tp']['entry_price']:.2f}")
        logger.info(f"  SL: {result['sl_tp']['sl_price']:.2f}")
        logger.info(f"  TP: {result['sl_tp']['tp_price']:.2f}")
    
    logger.info("")
    logger.info("✅ OrchestratorAgent test complete!")
