#!/usr/bin/env python3
"""
Test CPU core limiting functionality.
This script verifies that environment variables are properly set
and PyTorch respects the thread limits.
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_environment_variables():
    """Test that CPU limiting environment variables are set."""
    logger.info("=== Testing Environment Variables ===")
    
    # Import cpu_limiter first (this sets the env vars)
    import services.cpu_limiter
    
    env_vars = [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS"
    ]
    
    all_set = True
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            logger.info(f"✅ {var} = {value}")
        else:
            logger.warning(f"❌ {var} is not set")
            all_set = False
    
    return all_set

def test_pytorch_threads():
    """Test that PyTorch thread limits are properly set."""
    logger.info("\n=== Testing PyTorch Thread Limits ===")
    
    try:
        import torch
        
        num_threads = torch.get_num_threads()
        num_interop_threads = torch.get_num_interop_threads()
        
        logger.info(f"PyTorch num_threads: {num_threads}")
        logger.info(f"PyTorch num_interop_threads: {num_interop_threads}")
        
        from config import settings
        expected = settings.ai_max_cores
        
        if num_threads <= expected:
            logger.info(f"✅ PyTorch threads ({num_threads}) <= ai_max_cores ({expected})")
            return True
        else:
            logger.warning(f"⚠️ PyTorch threads ({num_threads}) > ai_max_cores ({expected})")
            return False
            
    except ImportError:
        logger.warning("PyTorch not available, skipping PyTorch test")
        return True

def test_numpy_threads():
    """Test NumPy thread configuration."""
    logger.info("\n=== Testing NumPy Thread Configuration ===")
    
    try:
        import numpy as np
        
        # Try to get thread info (may not work on all systems)
        try:
            # NumPy uses different backends, try to get info
            from numpy.core._multiarray_umath import __cpu_features__
            logger.info(f"NumPy CPU features: {list(__cpu_features__.keys())[:5]}...")
        except:
            pass
        
        # Check if OpenMP is being used
        omp_threads = os.environ.get("OMP_NUM_THREADS")
        logger.info(f"OMP_NUM_THREADS (for NumPy): {omp_threads}")
        
        # Test with a simple operation
        logger.info("Running simple NumPy operation to test threading...")
        arr = np.random.randn(1000, 1000)
        result = np.dot(arr, arr)
        logger.info(f"✅ NumPy operation completed (shape: {result.shape})")
        
        return True
        
    except Exception as e:
        logger.error(f"NumPy test failed: {e}")
        return False

def test_cpu_usage_simulation():
    """Simulate CPU-intensive operation and check actual CPU usage."""
    logger.info("\n=== CPU Usage Simulation ===")
    logger.info("This test will run a CPU-intensive operation.")
    logger.info("Monitor CPU usage with: top -p $(pgrep -f test_cpu_limiting)")
    
    try:
        import numpy as np
        import time
        from config import settings
        
        logger.info(f"ai_max_cores setting: {settings.ai_max_cores}")
        logger.info("Running matrix multiplication for 5 seconds...")
        logger.info("Please check CPU usage in another terminal!")
        
        start = time.time()
        iterations = 0
        while time.time() - start < 5:
            # CPU-intensive operation
            arr = np.random.randn(500, 500)
            _ = np.dot(arr, arr)
            iterations += 1
        
        logger.info(f"Completed {iterations} iterations in 5 seconds")
        logger.info("If CPU limiting works, you should see ~{} cores used".format(settings.ai_max_cores))
        
        return True
        
    except Exception as e:
        logger.error(f"CPU simulation failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("Testing CPU Core Limiting...")
    logger.info("="*60)
    
    results = []
    
    # Test 1: Environment Variables
    results.append(("Environment Variables", test_environment_variables()))
    
    # Test 2: PyTorch Threads
    results.append(("PyTorch Threads", test_pytorch_threads()))
    
    # Test 3: NumPy Configuration
    results.append(("NumPy Configuration", test_numpy_threads()))
    
    # Test 4: CPU Usage Simulation
    logger.info("\n" + "="*60)
    proceed = input("Run CPU usage simulation? (y/n): ").strip().lower()
    if proceed == 'y':
        results.append(("CPU Usage Simulation", test_cpu_usage_simulation()))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("=== Test Summary ===")
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        all_passed = all_passed and passed
    
    logger.info("="*60)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED")
        logger.info("\nNext steps:")
        logger.info("1. Start your application: python main.py or uvicorn main:app")
        logger.info("2. Monitor CPU usage: top -p $(pgrep -f main:app)")
        logger.info("3. Trigger some AI processing and verify CPU usage stays within limits")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())

