"""
CPU Core Limiter - Must be imported FIRST before any AI libraries.

This module sets environment variables to limit CPU usage for:
- PyTorch (torch)
- NumPy (via OpenMP, MKL, OpenBLAS)
- Other numerical libraries

IMPORTANT: Import this module at the very top of your application,
BEFORE importing any heavy libraries like torch, transformers, numpy, etc.

Usage:
    # At the top of main.py or any entry point
    import services.cpu_limiter  # This sets the limits immediately
"""
import os
import logging

# Get settings first
from config import settings

logger = logging.getLogger(__name__)

def set_cpu_limits():
    """Set CPU core limits for all numerical libraries."""
    cpu_limit = str(settings.ai_max_cores)
    
    # Set environment variables for various threading libraries
    os.environ["OMP_NUM_THREADS"] = cpu_limit          # OpenMP (used by numpy, torch)
    os.environ["MKL_NUM_THREADS"] = cpu_limit          # Intel MKL
    os.environ["NUMEXPR_NUM_THREADS"] = cpu_limit      # NumExpr
    os.environ["OPENBLAS_NUM_THREADS"] = cpu_limit     # OpenBLAS
    os.environ["VECLIB_MAXIMUM_THREADS"] = cpu_limit   # macOS Accelerate
    
    logger.info(
        f"CPU core limits set to {cpu_limit}: "
        f"OMP_NUM_THREADS, MKL_NUM_THREADS, NUMEXPR_NUM_THREADS, "
        f"OPENBLAS_NUM_THREADS, VECLIB_MAXIMUM_THREADS"
    )
    
    return int(cpu_limit)

def set_torch_threads(num_threads: int = None):
    """
    Set PyTorch thread limits. Must be called AFTER torch is imported.
    
    Args:
        num_threads: Number of threads (default: settings.ai_max_cores)
    """
    if num_threads is None:
        num_threads = settings.ai_max_cores
    
    try:
        import torch
        torch.set_num_threads(num_threads)
        torch.set_num_interop_threads(num_threads)
        logger.info(f"PyTorch threads limited to {num_threads}")
    except ImportError:
        logger.warning("PyTorch not available, skipping torch thread limiting")
    except Exception as e:
        logger.error(f"Failed to set PyTorch thread limits: {e}")

# Set limits immediately when this module is imported
_cpu_limit = set_cpu_limits()

# Export for convenience
__all__ = ['set_cpu_limits', 'set_torch_threads', '_cpu_limit']

