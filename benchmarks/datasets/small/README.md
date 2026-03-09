# Small Test Datasets

This directory contains small test datasets randomly sampled from the full ESA 2025 dataset for faster benchmarking and testing.

## Files

- **`Mouse.PacBio_reads_50.grp.gz`**: 50 randomly selected graphs from the full dataset
- **`Mouse.PacBio_reads_50.flow_corrected.grp.gz`**: Flow-corrected version of the 50-graph dataset
- **`Mouse.PacBio_reads_500.grp.gz`**: 500 randomly selected graphs from the full dataset  
- **`Mouse.PacBio_reads_500.flow_corrected.grp.gz`**: Flow-corrected version of the 500-graph dataset

## How These Files Were Created

These files were generated using the [`create_small_dataset.py`](../../create_small_dataset.py) script, which:

1. Loads the full dataset from [`../esa2025/Mouse.PacBio_reads.grp.gz`](../esa2025/Mouse.PacBio_reads.grp.gz)
2. Randomly samples 50 or 500 graphs using a fixed random seed (42) for reproducibility
3. Saves the sampled graphs to this directory

The flow-corrected versions were then generated using the `MinErrorFlow` class. See the [Minimum Error Flow documentation](https://algbio.github.io/flowpaths/minimum-error-flow.html) for details.

## Regenerating the Datasets

To regenerate these datasets:

```bash
cd benchmarks
python create_small_dataset.py
```

Note: You may need to modify the script to generate both the 50 and 500 graph versions.
