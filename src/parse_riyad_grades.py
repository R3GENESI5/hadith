"""
parse_riyad_grades.py
=====================
Extracts hadith grades for Riyad al-Salihin from two sources:
  1. Inline text in the app's hadith data (متفق عليه, رواه البخاري, etc.)
  2. Arnaut's footnotes from the DjVu OCR text (Archive.org)

Riyad al-Salihin is a compilation — Nawawi cited sources and Arnaut
added authentication. Most hadiths reference their original source
(Bukhari, Muslim, Tirmidhi, etc.) directly in the text.

Output: app/data/sunni/riyad_assalihin/grades.json

Usage:
    python src/parse_riyad_grades.py
"""

import json, re, glob
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data" / "sunni" / "riyad_assalihin"
DJVU = ROOT / "src" / "rijal_raw" / "riyad_arnaut.txt"
OUT = DATA / "grades.json"

# ── Grade extraction from inline Arabic text ────────────────────────
# Priority order: most specific first
INLINE_PATTERNS = [
    # Agreed upon (highest authenticity)
    (r'متفق عليه', 'Sahih'),
    # Bukhari and Muslim combined
    (r'رواه البخاري ومسلم', 'Sahih'),
    # Individual sahihayn
    (r'رواه البخاري', 'Sahih'),
    (r'رواه مسلم', 'Sahih'),
    # Explicit grade phrases
    (r'حديث صحيح', 'Sahih'),
    (r'حديث حسن صحيح', 'Sahih'),
    (r'إسناده صحيح', 'Sahih'),
    (r'صحيح لغيره', 'Sahih'),
    (r'حديث حسن', 'Hasan'),
    (r'إسناده حسن', 'Hasan'),
    (r'حسن لغيره', 'Hasan'),
    (r'إسناده ضعيف', "Da'if"),
    (r'حديث ضعيف', "Da'if"),
    # Source-based grades (known-sahih collections)
    (r'أخرجه البخاري', 'Sahih'),
    (r'أخرجه مسلم', 'Sahih'),
    # Sunan with authentication
    (r'رواه الترمذي.*?وقال.*?حسن صحيح', 'Sahih'),
    (r'رواه الترمذي.*?وقال.*?صحيح', 'Sahih'),
    (r'رواه الترمذي.*?وقال.*?حسن', 'Hasan'),
    (r'رواه أبو داود', 'Hasan'),  # Abu Dawud is generally hasan-level
    (r'رواه الترمذي', 'Hasan'),
    (r'رواه النسائي', 'Hasan'),
    (r'رواه ابن ماجه', 'Hasan'),
]

# ── Grade extraction from DjVu footnotes ────────────────────────────
FOOTNOTE_GRADE_PATTERNS = [
    (r'وإسناده صحيح', 'Sahih'),
    (r'إسناده صحيح', 'Sahih'),
    (r'وسنده صحيح', 'Sahih'),
    (r'سنده صحيح', 'Sahih'),
    (r'صححه ابن حبان', 'Sahih'),
    (r'صححه الحاكم', 'Sahih'),
    (r'صحيح الإسناد', 'Sahih'),
    (r'حديث صحيح', 'Sahih'),
    (r'وإسناده حسن', 'Hasan'),
    (r'إسناده حسن', 'Hasan'),
    (r'وسنده حسن', 'Hasan'),
    (r'سنده حسن', 'Hasan'),
    (r'حسن الإسناد', 'Hasan'),
    (r'حديث حسن', 'Hasan'),
    (r'إسناده ضعيف', "Da'if"),
    (r'وسنده ضعيف', "Da'if"),
    (r'حديث ضعيف', "Da'if"),
]


def extract_inline_grades():
    """Extract grades from the Arabic text already in the app data."""
    grades = {}
    total = 0

    for f in sorted(glob.glob(str(DATA / "[0-9]*.json"))):
        ch = json.load(open(f, encoding='utf-8'))
        for h in ch:
            total += 1
            text = h.get('arabic', '')
            hnum = str(h.get('idInBook', h.get('id', '')))

            for pattern, grade in INLINE_PATTERNS:
                if re.search(pattern, text):
                    grades[hnum] = grade
                    break

    return grades, total


def extract_djvu_grades():
    """Extract additional grades from Arnaut's DjVu footnotes.

    The DjVu text interleaves hadith text with footnotes.
    Footnotes contain grade annotations that apply to nearby hadiths.
    We extract grade lines and try to associate them with hadith numbers
    found in the surrounding text.
    """
    if not DJVU.exists():
        return {}

    text = DJVU.read_text(encoding='utf-8')
    lines = text.split('\n')

    # Extract all lines with grade annotations and nearby hadith references
    djvu_grades = {}

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Check if this line has a grade annotation
        grade = None
        for pattern, g in FOOTNOTE_GRADE_PATTERNS:
            if re.search(pattern, line):
                grade = g
                break

        if grade is None:
            continue

        # Try to find a hadith number reference in this line or nearby
        # Footnotes often reference hadith numbers in parentheses
        # Look for (NUM) pattern in the current and surrounding lines
        context = ' '.join(lines[max(0, i-3):i+3])
        num_matches = re.findall(r'\((\d{1,5})\)', context)
        for num in num_matches:
            n = int(num)
            if 1 <= n <= 1900:  # Riyad has ~1900 hadiths
                if str(n) not in djvu_grades:
                    djvu_grades[str(n)] = grade

    return djvu_grades


def main():
    print("Extracting Riyad al-Salihin grades...\n")

    # Phase 1: Inline grades from app text
    inline_grades, total = extract_inline_grades()
    print(f"Total hadiths: {total}")
    print(f"Phase 1 — Inline text grades: {len(inline_grades)} ({100*len(inline_grades)/total:.1f}%)")

    # Phase 2: DjVu footnote grades (fill gaps)
    djvu_grades = extract_djvu_grades()
    print(f"Phase 2 — DjVu footnote grades: {len(djvu_grades)} additional")

    # Merge: inline takes priority, DjVu fills gaps
    all_grades = {}
    all_grades.update(djvu_grades)
    all_grades.update(inline_grades)  # inline overwrites djvu

    filled = len(all_grades) - len(inline_grades)
    print(f"Combined: {len(all_grades)} ({100*len(all_grades)/total:.1f}%) — {filled} from DjVu")

    # Distribution
    dist = Counter(all_grades.values())
    print(f"\nGrade distribution:")
    for g, c in dist.most_common():
        print(f"  {g}: {c} ({100*c/len(all_grades):.1f}%)")

    # Save
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(all_grades, f, ensure_ascii=False)
    print(f"\nSaved to {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == '__main__':
    main()
