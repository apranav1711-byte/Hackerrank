"""
package_submission.py - Cross-platform script to build code.zip for HackerRank Orchestrate.
Strictly packages code/, README.md, requirements.txt, and docs/.
Excludes dataset/, .git/, virtualenvs, and __pycache__/.
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_ZIP = ROOT / "code.zip"

EXCLUDE_DIRS = {
    "dataset",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
}


def should_exclude(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return True
    if rel_path.suffix in EXCLUDE_EXTENSIONS:
        return True
    if rel_path.name == "code.zip":
        return True
    return False


def package():
    print(f"Creating submission package: {OUTPUT_ZIP}")
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    included_count = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Package code/ directory
        code_dir = ROOT / "code"
        if code_dir.exists():
            for p in sorted(code_dir.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(ROOT)
                    if not should_exclude(rel):
                        zf.write(p, rel.as_posix())
                        included_count += 1

        # 2. Package root files
        for fname in ["README.md", "requirements.txt"]:
            fpath = ROOT / fname
            if fpath.exists():
                zf.write(fpath, fname)
                included_count += 1

        # 3. Package docs/ directory
        docs_dir = ROOT / "docs"
        if docs_dir.exists():
            for p in sorted(docs_dir.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(ROOT)
                    if not should_exclude(rel):
                        zf.write(p, rel.as_posix())
                        included_count += 1

    print(f"Successfully packaged {included_count} files into {OUTPUT_ZIP.name} ({OUTPUT_ZIP.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    package()
