"""
Test LanceDB Setup

Tests:
1. LanceDB connection
2. Collection creation
3. Pattern insertion
4. Similarity search
5. Statistics retrieval
"""

import sys
from pathlib import Path

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "python"))

from datetime import datetime, timedelta
from loguru import logger

from valuecell.knowledge.lance_db import LanceDBManager
from valuecell.knowledge.pattern_matcher import PatternMatcher


def test_lancedb_connection():
    """Test 1: LanceDB Connection"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: LanceDB Connection")
    logger.info("="*70)
    
    try:
        db = LanceDBManager()
        logger.info("✅ LanceDB connected successfully")
        
        # Get stats
        stats = db.get_stats()
        logger.info(f"📊 Collections: {len(stats['collections'])}")
        for col in stats['collections']:
            logger.info(f"   - {col['name']}: {col['count']} records")
        
        return db, True
        
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return None, False


def test_add_patterns(db: LanceDBManager):
    """Test 2: Add Sample Patterns"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Add Sample Patterns")
    logger.info("="*70)
    
    # Sample patterns to add
    patterns = [
        {
            "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "BoS",
            "direction": "Bullish",
            "price": 2350.50,
            "ema200": 2345.60,
            "session": "London",
            "outcome": "WIN",
            "profit_pips": 40.0,
            "duration_minutes": 17
        },
        {
            "timestamp": (datetime.now() - timedelta(days=4)).isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "BoS",
            "direction": "Bullish",
            "price": 2348.20,
            "ema200": 2343.10,
            "session": "London",
            "outcome": "WIN",
            "profit_pips": 35.0,
            "duration_minutes": 22
        },
        {
            "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "CHoCH",
            "direction": "Bullish",
            "price": 2352.80,
            "ema200": 2346.50,
            "session": "London",
            "outcome": "LOSS",
            "profit_pips": -20.0,
            "duration_minutes": 8
        },
        {
            "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "BoS",
            "direction": "Bearish",
            "price": 2355.10,
            "ema200": 2348.20,
            "session": "NewYork",
            "outcome": "WIN",
            "profit_pips": 30.0,
            "duration_minutes": 15
        },
        {
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "event_type": "BoS",
            "direction": "Bullish",
            "price": 2351.40,
            "ema200": 2346.80,
            "session": "London",
            "outcome": "WIN",
            "profit_pips": 45.0,
            "duration_minutes": 20
        }
    ]
    
    success_count = 0
    for i, pattern in enumerate(patterns, 1):
        success = db.add_structure_pattern(pattern)
        if success:
            success_count += 1
            logger.info(f"✅ Added pattern {i}/{len(patterns)}: {pattern['event_type']} {pattern['direction']}")
        else:
            logger.error(f"❌ Failed pattern {i}/{len(patterns)}")
    
    logger.info(f"\n📊 Added {success_count}/{len(patterns)} patterns successfully")
    return success_count == len(patterns)


def test_similarity_search(db: LanceDBManager):
    """Test 3: Similarity Search"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Similarity Search")
    logger.info("="*70)
    
    # Query pattern (looking for similar BoS Bullish in London)
    query_pattern = {
        "timestamp": datetime.now().isoformat(),
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "event_type": "BoS",
        "direction": "Bullish",
        "price": 2350.00,
        "ema200": 2345.00,
        "session": "London"
    }
    
    logger.info(f"🔍 Query: {query_pattern['event_type']} {query_pattern['direction']} in {query_pattern['session']}")
    
    similar = db.search_similar_patterns(query_pattern, limit=10, min_similarity=0.5)
    
    if similar:
        logger.info(f"✅ Found {len(similar)} similar patterns:")
        for i, pattern in enumerate(similar[:5], 1):
            logger.info(
                f"   {i}. {pattern['event_type']} {pattern['direction']} | "
                f"Outcome: {pattern['outcome']} | "
                f"Profit: {pattern['profit_pips']:.1f} pips | "
                f"Similarity: {pattern.get('similarity', 0):.3f}"
            )
        return True
    else:
        logger.warning("⚠️ No similar patterns found")
        return False


def test_pattern_matcher():
    """Test 4: PatternMatcher High-level API"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: PatternMatcher API")
    logger.info("="*70)
    
    try:
        matcher = PatternMatcher()
        
        # Find similar patterns
        result = matcher.find_similar_patterns(
            event_type="BoS",
            direction="Bullish",
            price=2350.50,
            ema200=2345.60,
            session="London",
            timeframe="M15",
            limit=10
        )
        
        logger.info(f"📊 Pattern Analysis Results:")
        logger.info(f"   Total patterns: {result['total_count']}")
        logger.info(f"   Win rate: {result['win_rate']:.1%}")
        logger.info(f"   Avg profit: {result['avg_profit']:.1f} pips")
        logger.info(f"   Recommendation: {result['recommendation']}")
        logger.info(f"   Confidence: {result['confidence']:.3f}")
        logger.info(f"   Reasoning: {result['reasoning']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ PatternMatcher test failed: {e}")
        return False


def test_add_trade_outcome(db: LanceDBManager):
    """Test 5: Add Trade Outcome"""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Add Trade Outcome")
    logger.info("="*70)
    
    trade = {
        "ticket": 123456789,
        "timestamp": datetime.now().isoformat(),
        "symbol": "XAUUSD",
        "type": "BUY",
        "entry_price": 2350.50,
        "exit_price": 2354.50,
        "profit_pips": 40.0,
        "duration_minutes": 17,
        "outcome": "WIN",
        "structure_event": "BoS",
        "session": "London",
        "consensus_score": 0.754
    }
    
    success = db.add_trade_outcome(trade)
    
    if success:
        logger.info(f"✅ Trade outcome added: #{trade['ticket']} | {trade['outcome']} | +{trade['profit_pips']} pips")
        return True
    else:
        logger.error("❌ Failed to add trade outcome")
        return False


def test_database_stats(db: LanceDBManager):
    """Test 6: Database Statistics"""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: Database Statistics")
    logger.info("="*70)
    
    stats = db.get_stats()
    
    logger.info(f"📊 LanceDB Statistics:")
    logger.info(f"   Total collections: {len(stats['collections'])}")
    logger.info(f"   Total patterns: {stats['total_patterns']}")
    logger.info(f"\n   Collection breakdown:")
    
    for col in stats['collections']:
        logger.info(f"   - {col['name']}: {col['count']} records")
    
    return True


def main():
    """Run all tests"""
    logger.info("="*70)
    logger.info("🧪 LANCEDB SETUP TESTS")
    logger.info("="*70)
    
    results = {}
    
    # Test 1: Connection
    db, success = test_lancedb_connection()
    results["Connection"] = success
    
    if not success:
        logger.error("\n❌ Connection test failed, aborting remaining tests")
        return
    
    # Test 2: Add patterns
    results["Add Patterns"] = test_add_patterns(db)
    
    # Test 3: Similarity search
    results["Similarity Search"] = test_similarity_search(db)
    
    # Test 4: PatternMatcher
    results["PatternMatcher"] = test_pattern_matcher()
    
    # Test 5: Trade outcomes
    results["Trade Outcomes"] = test_add_trade_outcome(db)
    
    # Test 6: Statistics
    results["Statistics"] = test_database_stats(db)
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*70)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\n   Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("\n" + "="*70)
        logger.info("✅ ALL TESTS PASSED - LANCEDB READY FOR PRODUCTION!")
        logger.info("="*70)
    else:
        logger.warning("\n⚠️ Some tests failed, please review")


if __name__ == "__main__":
    main()
