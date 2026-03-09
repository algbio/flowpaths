#!/bin/bash

# Example script showing how to run the benchmark suite
# This demonstrates a complete workflow from running benchmarks to generating tables

echo "=================================="
echo "Flowpaths Benchmark Suite Example"
echo "=================================="
echo ""

# Navigate to benchmarks directory
cd "$(dirname "$0")"

# Create results directory if it doesn't exist
mkdir -p results

echo "Step 1: Running MinFlowDecomp benchmark on small dataset"
echo ""

# Run benchmark on the small dataset
python benchmark_minflowdecomp.py \
    --datasets datasets/small/Mouse.PacBio_reads_500.flow_corrected.grp.gz \
    --min-width 1 \
    --max-width 100

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
    --output results/Mouse.PacBio_reads_500.flow_corrected.grp.md \
    --metric mean

echo "Markdown table saved to: example_results.md"
echo ""

echo "Step 4: Generating LaTeX table"
echo ""

# Generate LaTeX table with median times
python aggregate_results.py MinFlowDecomp \
    --format latex \
    --output results/Mouse.PacBio_reads_500.flow_corrected.grp.tex \
    --metric median

echo "LaTeX table saved to: example_results.tex"
echo ""

echo "=================================="
echo "Example complete!"
echo ""
echo "You can now:"
echo "  - View example_results.md for markdown table"
echo "  - View example_results.tex for LaTeX table"
echo "  - Check results/ directory for raw JSON data"
echo ""
echo "=================================="
