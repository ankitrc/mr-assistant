"""Block commits that contain banned terms (e.g. real company or brand names).

The term list lives in `.banned_terms` at the repo root: one term per line,
`#` for comments, case-insensitive. That file is gitignored on purpose -
committing it would publish the very terms it protects.

Scans text files line by line and Parquet files cell by cell (all text and
text-list columns, plus column names).

    python scripts/check_banned_terms.py            # whole repo
    python scripts/check_banned_terms.py --staged   # only files staged for commit (pre-commit hook)
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS_FILE = ROOT / ".banned_terms"
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "pgdata"}
SKIP_FILES = {".banned_terms"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".toml", ".json", ".sql", ".cfg", ".ini", ".sh",
                 ".env", ".example", ".csv", ".html", ".js", ".ts", ".tsx", ".jsx", ".css", ""}


def load_terms():
    if not TERMS_FILE.exists():
        sys.exit("Missing .banned_terms at the repo root. Create it (see .banned_terms.example); "
                 "the check never runs without it.")
    terms = [t.strip() for t in TERMS_FILE.read_text().splitlines() if t.strip() and not t.startswith("#")]
    if not terms:
        sys.exit(".banned_terms is empty.")
    return re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)


def files_to_scan(staged):
    if staged:
        out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        return [ROOT / f for f in out]
    return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]


def scan_text(path, pattern):
    hits = []
    try:
        lines = path.read_text(errors="strict").splitlines()
    except (UnicodeDecodeError, OSError):
        return hits
    for i, line in enumerate(lines, 1):
        m = pattern.search(line)
        if m:
            hits.append(f"{path.relative_to(ROOT)}:{i}: '{m.group(0)}'")
    return hits


def scan_parquet(path, pattern):
    try:
        import duckdb
    except ImportError:
        sys.exit("duckdb is required to scan Parquet files: pip install duckdb")
    con = duckdb.connect()
    hits = []
    cols = con.execute(f"DESCRIBE SELECT * FROM '{path}'").fetchall()
    for name, ctype, *_ in cols:
        if pattern.search(name):
            hits.append(f"{path.relative_to(ROOT)}: column name '{name}'")
        if "VARCHAR" not in ctype:
            continue
        rows = con.execute(f'SELECT DISTINCT CAST("{name}" AS VARCHAR) FROM \'{path}\' WHERE "{name}" IS NOT NULL').fetchall()
        for (value,) in rows:
            m = pattern.search(value)
            if m:
                hits.append(f"{path.relative_to(ROOT)}: column '{name}' contains '{m.group(0)}'")
                break
    return hits


def main():
    pattern = load_terms()
    hits = []
    for path in files_to_scan("--staged" in sys.argv):
        if path.name in SKIP_FILES or not path.exists():
            continue
        if path.suffix == ".parquet":
            hits += scan_parquet(path, pattern)
        elif path.suffix in TEXT_SUFFIXES or path.name.startswith("."):
            hits += scan_text(path, pattern)
    if hits:
        print("Banned terms found:")
        print("\n".join(f"  {h}" for h in hits))
        sys.exit(1)
    print("No banned terms found.")


if __name__ == "__main__":
    main()
