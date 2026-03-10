#!/bin/bash

# Example script showing how to run the benchmark suite
# This demonstrates a complete workflow from running benchmarks to generating tables

echo "=================================="
echo "Flowpaths Benchmark Suite Example"
echo "=================================="
echo ""

# Navigate to benchmarks directory
cd "$(dirname "$0")"

# Get output directory from parameter or use default
OUTPUT_DIR="${1:-results}"
# Get benchmark time limit (seconds) from parameter or use default
TIME_LIMIT="${2:-300}"

# Create results directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Step 1: Running MinFlowDecomp benchmark on small dataset"
echo ""

# Run benchmark on the small dataset
python benchmark_minflowdecomp.py \
    --datasets datasets/esa2025/Mouse.PacBio_reads_5_perwidth.flow_corrected.grp.gz \
    --min-width 1 \
    --max-width 6 \
    --time-limit "$TIME_LIMIT"

echo ""
echo "Step 2: Viewing results in console"
echo ""

# Display results in console
python aggregate_results.py MinFlowDecomp

echo ""
echo "Step 3: Generating markdown table"
echo ""

# Generate markdown table
python aggregate_results.py MinFlowDecomp \
    --format markdown \
    --output "$OUTPUT_DIR/Mouse.PacBio_reads_1_perwidth.flow_corrected.grp.md" \
    --metric mean