"""
System Validator - Pre-Trading System Check

Validates all system components before trading:
1. MT5 connection and credentials
2. Database connections (Neon PostgreSQL, LanceDB)
3. All agents initialization
4. Safety mechanisms
5. Configuration files
6. Dependencies

Usage:
    python scripts/system_validator.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

from loguru import logger
import MetaTrader5 as mt5
from datetime import datetime
import json


class SystemValidator:
    """
    System Validator - Validates all components before trading
    """
    
    def __init__(self):
        self.name = "SystemValidator"
        self.version = "1.0.0"
        self.checks_passed = 0
        self.checks_failed = 0
        self.check_results = []
        
        logger.info(f"✅ {self.name} v{self.version} initialized")
    
    def run_check(self, check_name: str, check_func):
        """Run a validation check"""
        logger.info(f"\n{'='*70}")
        logger.info(f"CHECK: {check_name}")
        logger.info(f"{'='*70}")
        
        try:
            check_func()
            self.checks_passed += 1
            self.check_results.append({"name": check_name, "status": "✅ PASS"})
            logger.info(f"✅ {check_name} - PASSED")
            return True
        except Exception as e:
            self.checks_failed += 1
            self.check_results.append({"name": check_name, "status": f"❌ FAIL: {e}"})
            logger.error(f"❌ {check_name} - FAILED: {e}")
            return False
    
    def check_python_version(self):
        """Check 1: Python version"""
        logger.info(f"Python version: {sys.version}")
        major, minor = sys.version_info[:2]
        assert major == 3 and minor >= 8, f"Python 3.8+ required (found {major}.{minor})"
        logger.info("✅ Python version compatible")
    
    def check_dependencies(self):
        """Check 2: Required dependencies"""
        logger.info("Checking dependencies...")
        
        required_packages = [
            "MetaTrader5",
            "pandas",
            "numpy",
            "loguru",
            "psycopg2",
            "lancedb",
            "requests",
            "psutil"
        ]
        
        missing = []
        for package in required_packages:
            try:
                __import__(package)
                logger.info(f"   ✅ {package}")
            except ImportError:
                missing.append(package)
                logger.error(f"   ❌ {package} - NOT FOUND")
        
        assert len(missing) == 0, f"Missing packages: {', '.join(missing)}"
        logger.info(f"✅ All {len(required_packages)} dependencies installed")
    
    def check_mt5_connection(self):
        """Check 3: MT5 connection"""
        logger.info("Testing MT5 connection...")
        
        # Initialize
        initialized = mt5.initialize()
        assert initialized, f"MT5 initialization failed: {mt5.last_error()}"
        logger.info("   ✅ MT5 initialized")
        
        # Check account info
        account_info = mt5.account_info()
        assert account_info is not None, "Failed to get account info"
        logger.info(f"   ✅ Account: {account_info.login}")
        logger.info(f"   ✅ Server: {account_info.server}")
        logger.info(f"   ✅ Balance: ${account_info.balance:.2f}")
        
        # Test data fetching
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, 10)
        assert rates is not None, "Failed to fetch XAUUSD data"
        assert len(rates) > 0, "No data returned"
        logger.info(f"   ✅ Data fetching works ({len(rates)} bars)")
        
        # Shutdown
        mt5.shutdown()
        logger.info("✅ MT5 connection validated")
    
    def check_file_structure(self):
        """Check 4: File and directory structure"""
        logger.info("Checking file structure...")
        
        required_dirs = [
            "python/valuecell/adapters/mt5",
            "python/valuecell/agents",
            "python/valuecell/execution",
            "python/valuecell/safety",
            "scripts",
            "logs",
            "docs"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                logger.info(f"   ✅ {dir_path}")
            else:
                missing_dirs.append(dir_path)
                logger.error(f"   ❌ {dir_path} - NOT FOUND")
        
        assert len(missing_dirs) == 0, f"Missing directories: {', '.join(missing_dirs)}"
        
        # Check key files
        required_files = [
            "python/valuecell/trading_system.py",
            "python/valuecell/agents/orchestrator_agent.py",
            "python/valuecell/agents/state_machine_agent.py",
            "python/valuecell/execution/execution_agent.py",
            "python/valuecell/safety/circuit_breaker.py",
            "python/valuecell/safety/notifier.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if os.path.exists(file_path):
                logger.info(f"   ✅ {file_path}")
            else:
                missing_files.append(file_path)
                logger.error(f"   ❌ {file_path} - NOT FOUND")
        
        assert len(missing_files) == 0, f"Missing files: {', '.join(missing_files)}"
        logger.info("✅ File structure validated")
    
    def check_configuration(self):
        """Check 5: Configuration files"""
        logger.info("Checking configuration...")
        
        # Check .env file
        if os.path.exists(".env"):
            logger.info("   ✅ .env file exists")
            
            # Check Telegram config
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            telegram_chat = os.getenv("TELEGRAM_CHAT_ID", "")
            
            if telegram_token and telegram_chat:
                logger.info("   ✅ Telegram credentials configured")
            else:
                logger.warning("   ⚠️  Telegram credentials not configured (notifications disabled)")
        else:
            logger.warning("   ⚠️  .env file not found (using defaults)")
        
        logger.info("✅ Configuration checked")
    
    def check_agents_initialization(self):
        """Check 6: All agents can be initialized"""
        logger.info("Testing agent initialization...")
        
        # Market Structure Agent
        from valuecell.agents.market_structure_agent import MarketStructureAgent
        ms_agent = MarketStructureAgent(swing_length=5, timeframe="M15")
        logger.info("   ✅ Market Structure Agent")
        
        # ML Prediction Agent
        from valuecell.agents.ml_prediction_agent import MLPredictionAgent
        ml_agent = MLPredictionAgent()
        logger.info("   ✅ ML Prediction Agent")
        
        # Risk Management Agent
        from valuecell.agents.risk_management_agent import RiskManagementAgent
        risk_agent = RiskManagementAgent(account_balance=10000.0)
        logger.info("   ✅ Risk Management Agent")
        
        # Sentiment Agent
        from valuecell.agents.sentiment_agent import SentimentAgent
        sentiment_agent = SentimentAgent()
        logger.info("   ✅ Sentiment Agent")
        
        # Orchestrator Agent
        from valuecell.agents.orchestrator_agent import OrchestratorAgent
        orchestrator = OrchestratorAgent(
            consensus_threshold=0.60,
            market_structure={"swing_length": 5, "timeframe": "M15"},
            risk_management={"account_balance": 10000.0}
        )
        logger.info("   ✅ Orchestrator Agent")
        
        # State Machine Agent
        from valuecell.agents.state_machine_agent import StateMachineAgent
        state_machine = StateMachineAgent(state_file="test_validation_state.json")
        logger.info("   ✅ State Machine Agent")
        
        # Cleanup
        if os.path.exists("test_validation_state.json"):
            os.remove("test_validation_state.json")
        
        logger.info("✅ All agents initialized successfully")
    
    def check_execution_agent(self):
        """Check 7: Execution agent"""
        logger.info("Testing execution agent...")
        
        from valuecell.execution.execution_agent import ExecutionAgent
        
        execution = ExecutionAgent(
            symbol="XAUUSD",
            enable_paper_trading=True
        )
        logger.info("   ✅ Execution agent initialized (paper mode)")
        
        # Test paper trade
        result = execution.place_order(
            signal="BUY",
            lot_size=0.01,
            sl_price=2340.0,
            tp_price=2360.0,
            comment="System validation test"
        )
        
        assert result['success'], "Paper order failed"
        logger.info(f"   ✅ Paper order executed: Ticket #{result['ticket']}")
        
        # Close position
        execution.close_position(result['ticket'])
        logger.info("   ✅ Position closed")
        
        execution.shutdown()
        logger.info("✅ Execution agent validated")
    
    def check_safety_mechanisms(self):
        """Check 8: Safety mechanisms"""
        logger.info("Testing safety mechanisms...")
        
        # Circuit Breaker
        from valuecell.safety.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(
            max_consecutive_losses=3,
            max_daily_loss_pct=5.0,
            account_balance=10000.0
        )
        
        check = cb.check_before_trade()
        assert check['allowed'], "Circuit breaker blocking normal operation"
        logger.info("   ✅ Circuit Breaker initialized")
        
        # Notifier
        from valuecell.safety.notifier import Notifier
        notifier = Notifier(telegram_enabled=False)
        
        info = notifier.get_info()
        assert info['name'] == "Notifier", "Notifier info incorrect"
        logger.info("   ✅ Notifier initialized")
        
        logger.info("✅ Safety mechanisms validated")
    
    def check_database_connections(self):
        """Check 9: Database connections"""
        logger.info("Testing database connections...")
        
        # Neon PostgreSQL
        try:
            import psycopg2
            from dotenv import load_dotenv
            load_dotenv()
            
            db_url = os.getenv("DATABASE_URL")
            if db_url:
                conn = psycopg2.connect(db_url)
                conn.close()
                logger.info("   ✅ Neon PostgreSQL connection")
            else:
                logger.warning("   ⚠️  DATABASE_URL not configured")
        except Exception as e:
            logger.warning(f"   ⚠️  PostgreSQL connection failed: {e}")
        
        # LanceDB
        try:
            import lancedb
            db = lancedb.connect("knowledge/lancedb")
            logger.info("   ✅ LanceDB connection")
        except Exception as e:
            logger.warning(f"   ⚠️  LanceDB connection failed: {e}")
        
        logger.info("✅ Database connections checked")
    
    def check_logging(self):
        """Check 10: Logging system"""
        logger.info("Testing logging system...")
        
        # Test log directory
        os.makedirs("logs", exist_ok=True)
        logger.info("   ✅ Log directory exists")
        
        # Test log file creation
        test_log_file = f"logs/test_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logger.add(test_log_file, level="DEBUG")
        logger.debug("Test log entry")
        
        assert os.path.exists(test_log_file), "Log file not created"
        logger.info("   ✅ Log file created")
        
        # Clean up
        os.remove(test_log_file)
        
        logger.info("✅ Logging system validated")
    
    def run_all_checks(self):
        """Run all validation checks"""
        logger.info("\n" + "="*70)
        logger.info("🔍 SYSTEM VALIDATION - START")
        logger.info("="*70)
        
        # Run checks
        self.run_check("1. Python Version", self.check_python_version)
        self.run_check("2. Dependencies", self.check_dependencies)
        self.run_check("3. MT5 Connection", self.check_mt5_connection)
        self.run_check("4. File Structure", self.check_file_structure)
        self.run_check("5. Configuration", self.check_configuration)
        self.run_check("6. Agents Initialization", self.check_agents_initialization)
        self.run_check("7. Execution Agent", self.check_execution_agent)
        self.run_check("8. Safety Mechanisms", self.check_safety_mechanisms)
        self.run_check("9. Database Connections", self.check_database_connections)
        self.run_check("10. Logging System", self.check_logging)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print validation summary"""
        logger.info("\n" + "="*70)
        logger.info("📊 VALIDATION SUMMARY")
        logger.info("="*70)
        
        total = self.checks_passed + self.checks_failed
        pass_rate = (self.checks_passed / total * 100) if total > 0 else 0
        
        for result in self.check_results:
            logger.info(f"{result['status']} - {result['name']}")
        
        logger.info("\n" + "="*70)
        logger.info(f"Total Checks: {total}")
        logger.info(f"✅ Passed: {self.checks_passed}")
        logger.info(f"❌ Failed: {self.checks_failed}")
        logger.info(f"Pass Rate: {pass_rate:.1f}%")
        logger.info("="*70)
        
        if self.checks_failed == 0:
            logger.info("\n🎉 SYSTEM READY FOR TRADING!")
            logger.info("\nNext steps:")
            logger.info("  1. Configure Telegram (optional): Edit .env file")
            logger.info("  2. Run integration tests: run_test_integration.bat")
            logger.info("  3. Start paper trading: python -m valuecell.trading_system --mode paper")
        else:
            logger.warning(f"\n⚠️ {self.checks_failed} CHECK(S) FAILED - FIX BEFORE TRADING")
        
        logger.info("")
    
    def save_report(self):
        """Save validation report to file"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "validator": {
                "name": self.name,
                "version": self.version
            },
            "summary": {
                "total_checks": self.checks_passed + self.checks_failed,
                "passed": self.checks_passed,
                "failed": self.checks_failed,
                "pass_rate": (self.checks_passed / (self.checks_passed + self.checks_failed) * 100) if (self.checks_passed + self.checks_failed) > 0 else 0
            },
            "checks": self.check_results
        }
        
        os.makedirs("logs", exist_ok=True)
        filename = f"logs/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📝 Validation report saved to: {filename}")
        return filename


# ========== MAIN ENTRY POINT ==========

if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run validation
    validator = SystemValidator()
    validator.run_all_checks()
    validator.save_report()
    
    # Exit with appropriate code
    sys.exit(0 if validator.checks_failed == 0 else 1)
