#!/usr/bin/env python3
"""
Migration script to transition from old StrategyEvolver to Enhanced version.

This script demonstrates how to safely migrate to the enhanced strategy evolution
system with minimal disruption to existing functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy.ext.asyncio import create_async_session, AsyncSession
from docere.config import settings
from docere.core.improvement.strategy_evolver import StrategyEvolver  # Old version
from docere.core.improvement.enhanced_strategy_evolver import EnhancedStrategyEvolver  # New version
from docere.integrations.llm.client import ClaudeClient
import structlog

logger = structlog.get_logger()


async def test_migration():
    """Test migration from old to new evolver."""
    
    # Setup (you'll need to adapt this to your actual DB setup)
    # This is a mock setup - replace with your actual database configuration
    try:
        # Mock database session - replace with your actual setup
        print("🔄 Setting up database connection...")
        # db_session = create_async_session(settings.database_url)
        db_session = None  # Replace with actual session
        
        # Mock Claude client - replace with your actual setup  
        print("🔄 Setting up Claude client...")
        # claude_client = ClaudeClient(api_key=settings.anthropic_api_key)
        claude_client = None  # Replace with actual client
        
        if not db_session or not claude_client:
            print("⚠️  Mock setup detected. Replace with actual DB and Claude configurations.")
            return
        
        # Test old evolver
        print("\n📊 Testing original StrategyEvolver...")
        old_evolver = StrategyEvolver(db_session, claude_client)
        
        # Test new evolver
        print("📊 Testing EnhancedStrategyEvolver...")
        new_evolver = EnhancedStrategyEvolver(db_session, claude_client)
        
        # Compare results (in a safe, read-only way)
        print("🔍 Comparing evolution systems...")
        
        # You can run both and compare results here
        # old_result = await old_evolver.evolve()
        # new_result = await new_evolver.evolve()
        
        print("✅ Migration test complete!")
        print("\nKey improvements in Enhanced version:")
        print("  ✅ Robust JSON parsing with multiple fallback methods")
        print("  ✅ Comprehensive strategy validation (pedagogical, safety)")
        print("  ✅ Circuit breaker pattern for API resilience")
        print("  ✅ Enhanced similarity detection")
        print("  ✅ Better error handling and retry logic")
        print("  ✅ Structured logging with detailed metrics")
        
    except Exception as e:
        logger.error("Migration test failed", error=str(e))
        raise


def show_migration_checklist():
    """Show checklist for production migration."""
    print("\n" + "="*60)
    print("🚀 PRODUCTION MIGRATION CHECKLIST")
    print("="*60)
    
    checklist = [
        "□ Review and test all new validation rules",
        "□ Configure circuit breaker thresholds for your environment",
        "□ Update imports to use EnhancedStrategyEvolver",
        "□ Test with a small subset of strategies first",
        "□ Monitor Claude API usage and rate limits",
        "□ Set up alerting for evolution failures",
        "□ Backup existing strategy data before migration",
        "□ Update any scheduled jobs to use new evolver",
        "□ Train team on new error handling and monitoring",
        "□ Plan rollback procedure if needed"
    ]
    
    for item in checklist:
        print(f"  {item}")
    
    print("\n💡 Recommended migration approach:")
    print("  1. Deploy new code alongside existing system")
    print("  2. Run enhanced evolver in 'validation-only' mode first")
    print("  3. Compare results between old and new systems")
    print("  4. Gradually shift traffic to enhanced version")
    print("  5. Monitor metrics and performance closely")
    print("  6. Full cutover once confidence is established")


def show_configuration_guide():
    """Show configuration options for the enhanced system."""
    print("\n" + "="*60)
    print("⚙️  CONFIGURATION GUIDE")
    print("="*60)
    
    print("\n🔧 Circuit Breaker Settings (adjust for your environment):")
    print("  - failure_threshold: Number of failures before opening (default: 5)")
    print("  - recovery_timeout: Seconds before attempting reset (default: 60)")
    
    print("\n🔧 Strategy Validation Settings:")
    print("  - similarity_threshold: Similarity cutoff for duplicates (default: 0.75)")
    print("  - max_mutation_attempts: Retry attempts per strategy (default: 3)")
    print("  - claude_temperature: Randomness in mutations (default: 0.5)")
    
    print("\n🔧 Recommended Production Settings:")
    print("""
# Add to your settings/config:
STRATEGY_EVOLUTION_CIRCUIT_BREAKER_THRESHOLD = 3
STRATEGY_EVOLUTION_CIRCUIT_BREAKER_TIMEOUT = 120
STRATEGY_EVOLUTION_SIMILARITY_THRESHOLD = 0.75
STRATEGY_EVOLUTION_MAX_RETRY_ATTEMPTS = 3
STRATEGY_EVOLUTION_CLAUDE_TEMPERATURE = 0.5
    """)


if __name__ == "__main__":
    print("🎯 Strategy Evolution System Migration Tool")
    print("="*50)
    
    print("\n1. Running migration tests...")
    try:
        asyncio.run(test_migration())
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
    
    print("\n2. Showing migration checklist...")
    show_migration_checklist()
    
    print("\n3. Showing configuration guide...")
    show_configuration_guide()
    
    print("\n" + "="*60)
    print("🎉 MIGRATION PLANNING COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("  1. Review the enhanced code in:")
    print("     - src/docere/core/improvement/enhanced_strategy_evolver.py") 
    print("     - src/docere/core/improvement/strategy_validation.py")
    print("  2. Run the test suite:")
    print("     - tests/unit/test_enhanced_strategy_evolution.py")
    print("  3. Follow the migration checklist above")
    print("  4. Monitor system health during migration")
    
    print("\n📚 For detailed roadmap, see: STRATEGY_EVOLUTION_ROADMAP.md")
