#!/bin/bash
# Clean up debug and result files before running tests
# Usage: ./scripts/clean_debug.sh

echo "=== Cleaning debug files ==="

# Remove debug files in root
rm -f debug_*.png debug_*.txt 2>/dev/null && echo "✓ Removed debug_*.png and debug_*.txt"

# Remove old search results (keep directory)
rm -f search_results/*.json 2>/dev/null && echo "✓ Removed old search results"

# Remove old videos
rm -f videos/*.webm 2>/dev/null && echo "✓ Removed old videos"

echo "=== Clean complete ==="
