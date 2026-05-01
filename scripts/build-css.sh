#!/bin/bash
# Build script for Tailwind CSS + DaisyUI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TAILWIND_CLI="$PROJECT_ROOT/tools/tailwindcss-extra"
INPUT_CSS="$PROJECT_ROOT/web/static/css/input.css"
OUTPUT_CSS="$PROJECT_ROOT/web/static/css/tailwind.css"

# Check if CLI exists
if [ ! -f "$TAILWIND_CLI" ]; then
    echo "Error: tailwindcss-extra not found at $TAILWIND_CLI"
    echo "Please download it first:"
    echo "curl -sLO https://github.com/dobicinaitis/tailwind-cli-extra/releases/download/v2.7.5/tailwindcss-extra-linux-x64"
    echo "chmod +x tailwindcss-extra-linux-x64"
    echo "mv tailwindcss-extra-linux-x64 tools/tailwindcss-extra"
    exit 1
fi

# Parse mode
MODE="${1:-dev}"

case "$MODE" in
    dev)
        echo "Building CSS in development mode (watch)..."
        "$TAILWIND_CLI" -i "$INPUT_CSS" -o "$OUTPUT_CSS" --watch
        ;;
    prod)
        # 不 minify 進 git — readable 多行版方便 review diff / grep / blame。
        # 真要 minify 在部署 pipeline 做（GitHub Actions 等），不進版控。
        echo "Building CSS (readable multi-line, no minify)..."
        "$TAILWIND_CLI" -i "$INPUT_CSS" -o "$OUTPUT_CSS"
        ;;
    *)
        echo "Usage: $0 [dev|prod]"
        echo "  dev  - Development mode with watch (default)"
        echo "  prod - One-shot build, readable multi-line output"
        exit 1
        ;;
esac
