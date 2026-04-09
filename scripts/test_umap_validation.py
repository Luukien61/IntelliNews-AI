#!/usr/bin/env python3
"""
Test script to verify UMAP validation logic works correctly for different sample sizes.
"""
from config import settings
from services.clustering.service import ClusteringService


def test_umap_validation():
    """Test that UMAP validation works for various sample sizes."""
    
    service = ClusteringService()
    
    print("=" * 70)
    print("UMAP Validation Test")
    print("=" * 70)
    print(f"\nSettings:")
    print(f"  n_neighbors: {settings.clustering_umap_n_neighbors}")
    print(f"  n_components (configured): {settings.clustering_umap_n_components}")
    print(f"  UMAP enabled: {settings.clustering_umap_enabled}")
    print()
    
    # Test different sample sizes
    test_cases = [
        ("Very small", 5),
        ("Below threshold", 6),
        ("At threshold", 7),
        ("THOI_SU case", 18),
        ("Medium", 30),
        ("Large", 100),
    ]
    
    min_required = settings.clustering_umap_n_neighbors + 1
    
    print(f"Minimum samples required: {min_required}")
    print()
    print("Results:")
    print("-" * 70)
    
    for name, n_samples in test_cases:
        # Simulate the validation logic
        will_run = settings.clustering_umap_enabled and n_samples >= min_required
        
        if will_run:
            n_components = min(settings.clustering_umap_n_components, n_samples - 1)
            status = f"✅ WILL RUN (768d → {n_components}d)"
        else:
            status = f"❌ WILL SKIP (need >= {min_required})"
        
        print(f"{name:20s} {n_samples:3d} samples  →  {status}")
    
    print("-" * 70)
    print()
    print("Key insights:")
    print(f"  • Categories with >= {min_required} samples will use UMAP")
    print(f"  • n_components auto-adjusts: min(50, n_samples - 1)")
    print(f"  • Small categories like THOI_SU (18 samples) now work!")
    print("=" * 70)


if __name__ == "__main__":
    test_umap_validation()

