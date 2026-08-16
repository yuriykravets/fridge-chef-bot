"""Eval harness for ingredient detection.

Usage:
  1. Put fridge photos in evals/photos/ as e.g. fridge_01.jpg
  2. Next to each photo, create fridge_01.json:
       {"expected": ["eggs", "milk", "cabbage"]}
     List only items a human can clearly see.
  3. Run:  uv run python -m evals.run_eval

Reports precision (how many detections were real) and recall (how many real
items were found) per photo and overall. Rerun after any prompt/model change
to catch regressions.
"""

import json
from pathlib import Path
from unicodedata import normalize

PHOTOS_DIR = Path(__file__).parent / "photos"


def _norm(name: str) -> str:
    return normalize("NFKD", name).encode("ascii", "ignore").decode().strip().lower()


def _singular(name: str) -> str:
    return name[:-1] if name.endswith("s") and not name.endswith("ss") else name


def matches(predicted: str, expected: str) -> bool:
    """Fuzzy food-name match: substring either way, on singularized names."""
    p, e = _singular(_norm(predicted)), _singular(_norm(expected))
    return e in p or p in e


def evaluate_photo(name: str, detected: list[str], expected: list[str]) -> tuple[float, float, list[str], list[str]]:
    """Returns (precision, recall, false_positives, misses)."""
    misses = [e for e in expected if not any(matches(d, e) for d in detected)]
    false_pos = [d for d in detected if not any(matches(d, e) for e in expected)]
    tp = len(expected) - len(misses)
    precision = tp / len(detected) if detected else 0.0
    recall = tp / len(expected) if expected else 0.0
    return precision, recall, false_pos, misses


def main() -> None:
    from fridge_chef.vision import analyze_fridge_photos

    pairs = sorted(
        (p for p in PHOTOS_DIR.glob("*.jpg") if p.with_suffix(".json").exists()),
        key=lambda p: p.name,
    )
    if not pairs:
        print(f"No photo+json pairs found in {PHOTOS_DIR}. See module docstring.")
        return

    totals = {"tp": 0, "detected": 0, "expected": 0}
    for path in pairs:
        expected = json.loads(path.with_suffix(".json").read_text())["expected"]
        analysis = analyze_fridge_photos([path.read_bytes()])
        detected = [i.name for i in analysis.ingredients]
        precision, recall, fp, misses = evaluate_photo(path.name, detected, expected)
        totals["detected"] += len(detected)
        totals["expected"] += len(expected)
        totals["tp"] += len(expected) - len(misses)
        print(f"\n📷 {path.name}")
        print(f"   precision {precision:.0%}  recall {recall:.0%}  (detected {len(detected)}, expected {len(expected)})")
        if misses:
            print(f"   ❌ missed:      {', '.join(misses)}")
        if fp:
            print(f"   ⚠️  false alarm: {', '.join(fp)}")

    p = totals["tp"] / totals["detected"] if totals["detected"] else 0.0
    r = totals["tp"] / totals["expected"] if totals["expected"] else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    print(f"\n{'=' * 50}\nOVERALL: precision {p:.0%}  recall {r:.0%}  F1 {f1:.0%}  ({len(pairs)} photos)")


if __name__ == "__main__":
    main()
