#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 清理旧会话，按 iPhone 15 移动端尺寸（390x844）以有头模式打开页面
playwright-cli close >/dev/null 2>&1 || true
rm -f "$SCRIPT_DIR/demo-flow.js"
playwright-cli open "http://localhost:5173" --device="iPhone 15" --headed
playwright-cli run-code --filename="$SCRIPT_DIR/demo-step1.js"
playwright-cli upload "$SCRIPT_DIR/sample-contract.txt"
playwright-cli run-code --filename="$SCRIPT_DIR/demo-step2.js"
