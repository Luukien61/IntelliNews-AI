"""
CPU Core Limiter - Must be imported FIRST before any AI libraries.

This module sets environment variables to limit CPU usage for:
- PyTorch (torch)
- NumPy (via OpenMP, MKL, OpenBLAS)
- Other numerical libraries

On Linux, also pins the process to specific CPU cores via sched_setaffinity
for a hard OS-level constraint.

IMPORTANT: Import this module at the very top of your application,
BEFORE importing any heavy libraries like torch, transformers, numpy, etc.

Usage:
    # At the top of main.py or any entry point
    import services.cpu_limiter  # This sets the limits immediately
"""
import os
import sys
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
    os.environ["BLIS_NUM_THREADS"] = cpu_limit         # BLIS (used by some scipy builds)

    logger.info(
        f"CPU thread limits set to {cpu_limit}: "
        f"OMP_NUM_THREADS, MKL_NUM_THREADS, NUMEXPR_NUM_THREADS, "
        f"OPENBLAS_NUM_THREADS, BLIS_NUM_THREADS"
    )

    return int(cpu_limit)


def set_cpu_affinity():
    """
    Pin this process to specific CPU cores using OS-level affinity (Linux only).

    This is a HARD constraint enforced by the kernel - the process will only
    be scheduled on the selected cores regardless of what libraries do internally.

    Selects the first ai_max_cores CPUs (e.g. cores 0-3 for ai_max_cores=4).
    """
    if sys.platform != "linux":
        logger.debug("CPU affinity pinning is only supported on Linux, skipping.")
        return

    try:
        import multiprocessing
        total_cores = multiprocessing.cpu_count()
        max_cores = min(settings.ai_max_cores, total_cores)

        # Pin to the LAST N cores to leave the first cores free for the OS / other apps.
        # E.g. on a 16-core machine with max_cores=4 → pin to cores 12,13,14,15
        # Change to `list(range(max_cores))` if you want the FIRST N cores instead.
        allowed_cores = set(range(total_cores - max_cores, total_cores))

        os.sched_setaffinity(0, allowed_cores)  # 0 = current process
        actual = os.sched_getaffinity(0)
        logger.info(
            f"CPU affinity set: process pinned to cores {sorted(actual)} "
            f"({len(actual)}/{total_cores} cores)"
        )
    except AttributeError:
        # os.sched_setaffinity not available on this platform
        logger.warning("os.sched_setaffinity not available, skipping CPU affinity pinning.")
    except PermissionError:
        logger.warning(
            "Permission denied when setting CPU affinity. "
            "Run without Docker CPU restrictions or grant CAP_SYS_NICE."
        )
    except Exception as e:
        logger.error(f"Failed to set CPU affinity: {e}")


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
        # set_num_interop_threads can only be called ONCE before the interop pool starts.
        # Wrap in try/except to handle the case where it was already initialized.
        try:
            torch.set_num_interop_threads(num_threads)
        except RuntimeError:
            pass  # Already initialized, intra-op limit via set_num_threads is enough
        logger.info(f"PyTorch threads limited to {num_threads}")
    except ImportError:
        logger.warning("PyTorch not available, skipping torch thread limiting")
    except Exception as e:
        logger.error(f"Failed to set PyTorch thread limits: {e}")


# ── Apply limits immediately on import ──────────────────────────────────────

# 1. Set env vars BEFORE any heavy library is imported
_cpu_limit = set_cpu_limits()

# 2. Pin process to N cores at the OS level (Linux hard constraint)
#    set_torch_threads() is NOT called here because torch hasn't been imported yet.
#    It is called later in AIProcessorService.__init__() after torch is available.
set_cpu_affinity()

# Export for convenience
__all__ = ['set_cpu_limits', 'set_cpu_affinity', 'set_torch_threads', '_cpu_limit']
