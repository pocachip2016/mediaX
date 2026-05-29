#!/usr/bin/env bash
# check_no_module_package_shadowing.sh
# Python 패키지 shadowing 감지: X.py + X/ 디렉토리가 같은 부모 아래 공존하면 exit 1.
# Pre-commit hook으로 사용. service.py + service/ 같은 사고 재발 방지.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

EXCLUDES=".venv|__pycache__|node_modules|.next|.git"

found=0

while IFS= read -r pyfile; do
  dir="$(dirname "$pyfile")"
  stem="$(basename "$pyfile" .py)"
  pkg_dir="$dir/$stem"
  if [ -f "$pkg_dir/__init__.py" ]; then
    echo "ERROR: Python module shadowing detected!"
    echo "  Module : $pyfile"
    echo "  Package: $pkg_dir/__init__.py"
    echo "  Python imports the package directory and ignores the .py file."
    echo "  Fix: remove one of the two (keep the .py file or convert fully to a package)."
    found=1
  fi
done < <(find "$BACKEND_DIR" -name "*.py" \
  | grep -Ev "$EXCLUDES" \
  | sort)

if [ "$found" -ne 0 ]; then
  exit 1
fi

echo "OK: no module/package shadowing detected."
exit 0
