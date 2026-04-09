"""
scrape_riyad_grades.py
======================
Scrapes hadith grades for Riyad al-Salihin from sunnah.com.
Each hadith page has the source/grade in bold brackets: [Al-Bukhari and Muslim].

Riyad al-Salihin has 1,896 hadiths on sunnah.com.
We scrape chapter pages (bulk) rather than individual hadiths.

Output: app/data/sunni/riyad_assalihin/grades.json

Usage:
    python src/scrape_riyad_grades.py
"""

import json, re, time, sys
from pathlib import Path
from urllib.request import urlopen, Request
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "data" / "sunni" / "riyad_assalihin" / "grades.json"
OUT_FULL = ROOT / "app" / "data" / "sunni" / "riyad_assalihin" / "arnaut_grades.json"

# sunnah.com has 19 books for Riyad al-Salihin, accessed via /riyadussalihin/N
TOTAL_BOOKS = 19


def fetch(url):
    """Fetch URL with polite delay."""
    req = Request(url, headers={'User-Agent': 'ItqanBot/1.0 (academic research)'})
    return urlopen(req, timeout=30).read().decode('utf-8')


# Source citation → normalized grade
SOURCE_GRADES = {
    'Al-Bukhari and Muslim': 'Sahih',
    'Al-Bukhari': 'Sahih',
    'Muslim': 'Sahih',
    'At-Tirmidhi': 'Hasan',
    'Abu Dawud': 'Hasan',
    'An-Nasa\'i': 'Hasan',
    'Abu Dawud and At-Tirmidhi': 'Hasan',
    'At-Tirmidhi and Abu Dawud': 'Hasan',
    'At-Tirmidhi, who categorized it as Hadith Hasan Sahih': 'Sahih',
    'Malik': 'Sahih',
    'Ahmad': 'Hasan',
    'Ibn Majah': 'Hasan',
}


def classify_source(source_text):
    """Classify a source citation into a grade."""
    s = source_text.strip()

    # Direct matches
    for key, grade in SOURCE_GRADES.items():
        if key.lower() in s.lower():
            return grade

    # Check for explicit grade words in the source text
    if 'sahih' in s.lower() or 'authentic' in s.lower():
        return 'Sahih'
    if 'hasan' in s.lower() or 'good' in s.lower():
        return 'Hasan'
    if "da'if" in s.lower() or 'weak' in s.lower():
        return "Da'if"

    return 'Hasan'  # Default for cited hadiths in Riyad


def scrape_book(book_num):
    """Scrape all hadiths from a book chapter page."""
    url = f"https://sunnah.com/riyadussalihin/{book_num}"
    html = fetch(url)

    grades = {}

    # Find all hadith containers
    # Pattern: id=h{number} ... then <b>[SOURCE]</b> in english text
    # Hadith reference: "Riyad as-Salihin NUM"
    ref_pattern = re.compile(
        r'hadith_reference_sticky[^>]*>Riyad as-Salihin (\d+)<'
    )
    # Source/grade in bold brackets in English text
    grade_pattern = re.compile(r'<b>\[([^\]]+)\]</b>')

    # Split by hadith containers
    containers = html.split('actualHadithContainer')

    for container in containers[1:]:  # skip first (before any hadith)
        # Find hadith number
        ref_m = ref_pattern.search(container)
        if not ref_m:
            continue
        hnum = ref_m.group(1)

        # Find grade/source citation
        grade_m = grade_pattern.search(container)
        if grade_m:
            source = grade_m.group(1)
            grade = classify_source(source)
            grades[hnum] = {
                'grade': grade,
                'source': source,
            }

    return grades


def main():
    print("Scraping Riyad al-Salihin grades from sunnah.com...\n")

    all_grades = {}

    for book in range(1, TOTAL_BOOKS + 1):
        try:
            grades = scrape_book(book)
            all_grades.update(grades)
            print(f"  Book {book:2d}: {len(grades)} hadiths")
            time.sleep(1)  # polite delay
        except Exception as e:
            print(f"  Book {book:2d}: ERROR — {e}")

    print(f"\nTotal hadiths graded: {len(all_grades)}")

    # Distribution
    dist = Counter(g['grade'] for g in all_grades.values())
    print(f"\nGrade distribution:")
    for g, c in dist.most_common():
        print(f"  {g}: {c} ({100*c/len(all_grades):.1f}%)")

    # Save compact grades (hadith_number → grade)
    compact = {k: v['grade'] for k, v in sorted(all_grades.items(), key=lambda x: int(x[0]))}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(compact, f, ensure_ascii=False)
    print(f"\nSaved compact grades: {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")

    # Save full grades with source info
    full = {k: v for k, v in sorted(all_grades.items(), key=lambda x: int(x[0]))}
    with open(OUT_FULL, 'w', encoding='utf-8') as f:
        json.dump(full, f, ensure_ascii=False, indent=1)
    print(f"Saved full grades: {OUT_FULL.relative_to(ROOT)} ({OUT_FULL.stat().st_size:,} bytes)")


if __name__ == '__main__':
    main()
