"""
scrape_hadith_grades.py — Scrape per-hadith grades from sunnah.com
and patch them into the local hadith JSON files.

Covers: Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah (Al-Albani grades)
Bukhari and Muslim are auto-tagged as Sahih (no scraping needed).

Usage:
    python src/scrape_hadith_grades.py
    python src/scrape_hadith_grades.py --book abudawud --start 1 --end 100
"""

import json, re, os, time, argparse, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'app' / 'data' / 'sunni'

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Itqan-Research/1.0'})

# Sunnah.com collection names → our book IDs
SUNNAH_BOOKS = {
    'abudawud':  {'sunnah_name': 'abudawud',  'max_hadith': 5300},
    'tirmidhi':  {'sunnah_name': 'tirmidhi',  'max_hadith': 4100},
    'nasai':     {'sunnah_name': 'nasai',     'max_hadith': 5800},
    'ibnmajah':  {'sunnah_name': 'ibnmajah',  'max_hadith': 4400},
}

def fetch_grade(sunnah_name, num):
    """Fetch grade for a single hadith from sunnah.com"""
    url = f'https://sunnah.com/{sunnah_name}:{num}'
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            time.sleep(0.3)

            soup = BeautifulSoup(r.text, 'html.parser')
            grade_tds = soup.find_all('td', class_='english_grade')
            # Second td has the actual grade value
            if len(grade_tds) >= 2:
                raw = grade_tds[1].get_text(strip=True)
                # Clean: 'Hasan Sahih(Al-Albani)' → 'Hasan Sahih'
                clean = re.sub(r'\([^)]*\)', '', raw).strip()
                if clean:
                    return clean
            return None
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                return None

def scrape_book(book_id, start=1, end=None):
    """Scrape all grades for a book and save to a grade map."""
    info = SUNNAH_BOOKS[book_id]
    sunnah_name = info['sunnah_name']
    max_h = end or info['max_hadith']

    print(f'\nScraping {book_id} grades ({start}–{max_h})...')

    grades = {}
    nums = list(range(start, max_h + 1))
    done = 0

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch_grade, sunnah_name, n): n for n in nums}
        for future in as_completed(futures):
            num = futures[future]
            try:
                grade = future.result()
                if grade:
                    grades[num] = grade
            except Exception:
                pass
            done += 1
            if done % 200 == 0:
                print(f'  {done:>5}/{len(nums)} fetched, {len(grades):,} graded')

    print(f'  Done: {len(grades):,} grades for {book_id}')
    return grades

def apply_grades(book_id, grade_map):
    """Apply scraped grades to local hadith JSON files."""
    book_dir = DATA / book_id
    idx = json.load(open(book_dir / 'index.json', encoding='utf-8'))

    applied = 0
    # Build a sequential hadith number → (chapter_file, index_in_chapter) map
    seq_num = 0
    for ch in idx:
        cf = book_dir / ch['file']
        if not cf.exists():
            continue
        hadiths = json.load(open(cf, encoding='utf-8'))
        changed = False
        for h in hadiths:
            seq_num += 1
            # Try matching by sequential number
            grade = grade_map.get(seq_num)
            # Also try hadithNumber if present
            if not grade and h.get('hadithNumber'):
                grade = grade_map.get(h['hadithNumber'])
            if grade and not h.get('grade'):
                h['grade'] = grade
                applied += 1
                changed = True
        if changed:
            json.dump(hadiths, open(cf, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    print(f'  Applied {applied:,} grades to {book_id}')
    return applied

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--book', default='all', help='Book ID or "all"')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=None)
    args = parser.parse_args()

    books = [args.book] if args.book != 'all' else list(SUNNAH_BOOKS.keys())

    total = 0
    for book_id in books:
        if book_id not in SUNNAH_BOOKS:
            print(f'Unknown book: {book_id}')
            continue
        grades = scrape_book(book_id, args.start, args.end)
        if grades:
            # Save grade map for reuse
            grade_file = ROOT / 'src' / f'grades_{book_id}.json'
            json.dump(grades, open(grade_file, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f'  Saved {len(grades):,} grades to {grade_file.name}')
            applied = apply_grades(book_id, grades)
            total += applied

    print(f'\nTotal: {total:,} hadiths graded')

if __name__ == '__main__':
    main()
