#!/bin/bash
# This script runs python on all .py files in the directory.

error_count=0
failed_files=()

for file in examples/*.py; do
    if [ -f "$file" ]; then
        echo "========================================"
        echo "Running: $file"
        echo "========================================"
        if python "$file"; then
            echo "✓ Success"
        else
            echo "✗ Failed with exit code $?"
            ((error_count++))
            failed_files+=("$file")
        fi
        echo ""
    fi
done

echo "========================================"
echo "Summary"
echo "========================================"
if [ $error_count -eq 0 ]; then
    echo "✓ All examples finished without errors!"
else
    echo "✗ $error_count example(s) failed:"
    for file in "${failed_files[@]}"; do
        echo "  - $file"
    done
    exit 1
fi