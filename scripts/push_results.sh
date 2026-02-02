#!/bin/bash
# Push test results back to GitHub for analysis, then clean up
# Usage: ./scripts/push_results.sh

BRANCH="claude/parallel-scraper-consolidation-D2RiE"

echo "=== Pushing test results to GitHub ==="

# Add all result and debug files
git add search_results/ debug_*.txt debug_*.png videos/*.webm 2>/dev/null

# Check if there's anything to commit
if git diff --cached --quiet; then
    echo "No new files to commit"
else
    git commit -m "Test results $(date +%Y%m%d_%H%M%S)"
    echo "✓ Committed new results"
fi

# Pull any remote changes and rebase
echo "Pulling latest changes..."
git pull --rebase origin "$BRANCH"

# Push to remote
echo "Pushing to GitHub..."
git push origin "$BRANCH"

# Clean up after successful push
echo ""
echo "=== Cleaning up local debug files ==="
rm -f debug_*.png debug_*.txt 2>/dev/null
rm -f search_results/*.json 2>/dev/null
rm -f videos/*.webm 2>/dev/null
echo "✓ Local debug files cleaned"

echo ""
echo "=== Done! Ready for next test ==="
