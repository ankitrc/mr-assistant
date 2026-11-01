#!/usr/bin/env bash
# Installs a git pre-commit hook that blocks commits containing banned terms.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cat > "$ROOT/.git/hooks/pre-commit" <<'HOOK'
#!/usr/bin/env bash
python scripts/check_banned_terms.py --staged
HOOK
chmod +x "$ROOT/.git/hooks/pre-commit"
echo "pre-commit hook installed"
