#!/bin/bash
# sdc-tools pre-commit hook
# Runs the SDC checker on all staged .sdc / .tcl files.
# Returns non-zero if any file has errors, blocking the commit.
#
# Usage (plain git hook):
#   ln -s ../../.pre-commit-hooks/sdc-check.sh .git/hooks/pre-commit
#
# Usage (pre-commit framework):
#   # Add to .pre-commit-config.yaml (already present in repo)

set -e

# ── Configuration ──────────────────────────────────────────────────────────
# Set to "warn" to allow commits even with errors (just print warnings)
MODE="${SDC_TOOLS_MODE:-block}"
# ────────────────────────────────────────────────────────────────────────────

REPO_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
SDC_TOOLS="${REPO_DIR}/cli.py"

if [ ! -f "$SDC_TOOLS" ]; then
    echo "⚠  sdc-tools: cli.py not found at ${SDC_TOOLS}. Skipping SDC check."
    exit 0
fi

# Find staged .sdc and .tcl files
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(sdc|tcl)$' || true)

if [ -z "$STAGED" ]; then
    exit 0
fi

HAS_ERRORS=0
echo "🔧 sdc-tools: Checking staged SDC/TCL files..."

while IFS= read -r FILE; do
    if [ ! -f "${REPO_DIR}/${FILE}" ]; then
        continue
    fi

    # Run the checker — capture output but not exit code (we handle it)
    OUTPUT=$(python "$SDC_TOOLS" check "${REPO_DIR}/${FILE}" 2>&1) || true

    # Extract error count from output
    ERR_COUNT=$(echo "$OUTPUT" | grep -oP 'Errors:\s+\K\d+' || echo "0")
    WARN_COUNT=$(echo "$OUTPUT" | grep -oP 'Warnings:\s+\K\d+' || echo "0")

    if [ "$ERR_COUNT" -gt 0 ] || [ "$WARN_COUNT" -gt 0 ]; then
        echo ""
        echo "━━━ $FILE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$OUTPUT" | grep -E '\[SDC|\[CHG' || true
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        HAS_ERRORS=1
    else
        echo "  ✓ $FILE — clean"
    fi
done <<< "$STAGED"

if [ "$HAS_ERRORS" -eq 1 ]; then
    if [ "$MODE" = "warn" ]; then
        echo ""
        echo "⚠  sdc-tools: Issues found (non-blocking, SDC_TOOLS_MODE=warn)"
        exit 0
    else
        echo ""
        echo "❌ sdc-tools: Commit blocked — fix errors above or bypass with 'git commit --no-verify'"
        exit 1
    fi
fi

exit 0