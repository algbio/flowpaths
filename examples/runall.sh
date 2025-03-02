#!/bin/bash
# This script runs python on all .py files in the directory.

for file in *.py; do
    if [ -f "$file" ]; then
        echo "Running $file..."
        python "$file"
    fi
done