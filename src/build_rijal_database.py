"""
build_rijal_database.py
=======================
Builds the narrator database from scratch using v2 parsed entries.
Single script: merge all 22 sources -> unified JSON -> split files -> CSVs.

Pipeline:
  1. Load AR-Sanad as foundation (18,298 profiles with teacher-student links)
  2. Merge v2 parsed entries by name matching (exact -> prefix -> death year)
  3. Apply grade authority chain (Taqrib > Mizan > Thiqat > book default)
  4. Apply enrichment (Kaggle global IDs, teacher-student links)
  5. Clean all names using shared lexicon
  6. Validate
  7. Write unified JSON + split files + CSVs + manifest

Usage:
    python src/build_rijal_database.py              # full rebuild
    python src/build_rijal_database.py --dry-run    # preview stats only
    python src/build_rijal_database.py --restore    # restore from backup
"""

import ast
import csv
import json
import os
import re
import sys
import tempfile
import shutil
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "src" / "rijal_parsed_v2"
ARSANAD = ROOT / "src" / "arsanad_narrators.csv"
KAGGLE = ROOT / "src" / "kaggle_rawis.csv"
OUT_UNIFIED = ROOT / "app" / "data" / "narrator_unified.json"
OUT_RIJAL = ROOT / "app" / "data" / "rijal"
BACKUP = ROOT / "app" / "data" / "narrator_unified_v1_backup.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrator_lexicon import (
    GRADE_KEYWORDS, GRADE_COLORS, ABD_COMPOUNDS, BOOK_GRADE_DEFAULTS,
    COMPANION_MARKERS, DIACRITICS_RE, strip_diacritics,
    extract_grade, apply_book_default,
    clean_narrator_name, fix_abd_compound, is_valid_name,
)

# ── Grade authority chain ────────────────────────────────────────────
# When multiple sources give different grades, which one wins?
# Lower number = higher authority
GRADE_PRIORITY = {
    'taqrib': 1,           # Ibn Hajar's final word
    'mizan': 2,            # Al-Dhahabi's critical assessment
    'lisan_mizan': 3,      # Ibn Hajar's expansion of Mizan
    'jarh': 4,             # Ibn Abi Hatim
    'thiqat': 5,           # Ibn Hibban's reliable list
    'kamil': 6,            # Ibn 'Adi's weak catalog
    'mughni_ducafa': 7,    # Al-Dhahabi's concise weak list
    'diwan_ducafa': 8,     # Al-Dhahabi's weak register
    'dhayl_diwan': 9,      # Supplement
    'kashif': 10,          # Al-Dhahabi's condensed Tahdhib
    'isaba': 11,           # Ibn Hajar's companion encyclopedia
    'siyar': 12,           # Al-Dhahabi's biographical encyclopedia
    'tahdhib_kamal': 13,   # Al-Mizzi's encyclopedia
    'tahdhib_tahdhib': 14, # Ibn Hajar's condensed version
    'tarikh_islam': 15,    # Al-Dhahabi's chronological history
    'tabaqat': 16,         # Ibn Sa'd
    'tarikh': 17,          # Al-Khatib's Baghdad history
    'tadhkirat_huffaz': 18,
    'durar_kamina': 19,
    'macrifa_qurra': 20,
    'mucin_tabaqat': 21,
    'mucjam_shuyukh': 22,
}

GRADE_STRENGTH = {
    'companion': 6, 'reliable': 5, 'mostly_reliable': 4,
    'weak': 3, 'abandoned': 2, 'fabricator': 1, 'unknown': 0,
}


# ── Normalization ────────────────────────────────────────────────────

ALEF_RE = re.compile(r'[أإآا]')

def normalize(name):
    n = DIACRITICS_RE.sub('', name)
    n = ALEF_RE.sub('ا', n)
    n = n.replace('\u0640', '').replace('ہ', 'ه').replace('ی', 'ي').replace('ک', 'ك')
    return re.sub(r'\s+', ' ', n).strip()


def ibn_parts(name):
    return [p.strip() for p in re.split(r'\s+بن\s+', normalize(name)) if p.strip()]


def death_yr(val):
    m = re.search(r'(\d+)', val or '')
    return int(m.group(1)) if m else None


# ── Step 1: Load AR-Sanad foundation ─────────────────────────────────

def load_arsanad():
    """Load AR-Sanad as the foundation profile set."""
    profiles = {}
    by_name = {}

    with open(ARSANAD, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            pid = int(row['id'])
            name = row['name'].split('،')[0].strip()  # take primary name
            name = clean_narrator_name(name, has_sigla_prefix=False)
            name = fix_abd_compound(name)

            # Parse teacher/student IDs
            try:
                teachers = ast.literal_eval(row.get('narrated_from', '[]') or '[]')
            except:
                teachers = []
            try:
                students = ast.literal_eval(row.get('narrated_to', '[]') or '[]')
            except:
                students = []

            profile = {
                'id': pid,
                'full_name': name,
                'kunya': row.get('kunia', ''),
                'grade_en': 'unknown',
                'grade_ar': '',
                'color': '#95a5a6',
                'death': row.get('death_year', ''),
                'tabaqat': row.get('tabaqa', ''),
                'city': row.get('living_city', ''),
                'laqab': row.get('laqab', ''),
                'nasab': row.get('nasab', ''),
                'dhahabi': row.get('zahabi_rank', ''),
                'namings': [],
                'classical_sources': {},
            }

            if teachers:
                profile['teachers'] = teachers
            if students:
                profile['students'] = students

            # Parse all name variants
            try:
                namings = ast.literal_eval(row.get('namings', '[]') or '[]')
            except:
                namings = [name]
            profile['namings'] = namings

            profiles[str(pid)] = profile

            # Index all name variants
            for n in namings:
                by_name[n] = {
                    'id': pid,
                    'grade_en': 'unknown',
                    'grade_ar': '',
                    'color': '#95a5a6',
                    'death': row.get('death_year', ''),
                    'full_name': name,
                    'kunya': row.get('kunia', ''),
                }

    return profiles, by_name


# ── Step 2: Merge parsed entries ─────────────────────────────────────

def build_name_index(profiles, by_name):
    """Build lookup indices for name matching."""
    norm_index = {}
    for name, entry in by_name.items():
        norm = normalize(name)
        if norm not in norm_index:
            norm_index[norm] = str(entry['id'])

    prefix_index = defaultdict(set)
    for name, entry in by_name.items():
        norm = normalize(name)
        tokens = norm.split()
        if len(tokens) >= 3:
            prefix_index[' '.join(tokens[:3])].add(str(entry['id']))
        if len(tokens) >= 4:
            prefix_index[' '.join(tokens[:4])].add(str(entry['id']))

    return norm_index, prefix_index


def merge_all_sources(profiles, by_name):
    """Merge all v2 parsed entries into the profile database."""
    # Source processing order: authority chain
    source_order = sorted(
        [f.stem for f in PARSED.glob('*.json')],
        key=lambda s: GRADE_PRIORITY.get(s, 99)
    )

    norm_index, prefix_index = build_name_index(profiles, by_name)
    next_id = max(int(k) for k in profiles.keys()) + 1

    stats = {'matched': 0, 'new': 0, 'grade_upgrades': 0, 'source_additions': 0}

    for src in source_order:
        path = PARSED / f"{src}.json"
        if not path.exists():
            continue

        entries = json.load(open(path, encoding='utf-8'))
        src_matched = src_new = 0

        for entry in entries:
            entry_name = normalize(entry['name'])
            profile_id = norm_index.get(entry_name)

            # Fuzzy fallback: prefix matching
            if not profile_id:
                tokens = entry_name.split()
                candidates = set()
                if len(tokens) >= 4:
                    candidates = prefix_index.get(' '.join(tokens[:4]), set())
                if not candidates and len(tokens) >= 3:
                    candidates = prefix_index.get(' '.join(tokens[:3]), set())
                if len(candidates) == 1:
                    profile_id = next(iter(candidates))

            if profile_id and profile_id in profiles:
                profile = profiles[profile_id]
                src_matched += 1

                # Add classical source reference
                if src not in profile.get('classical_sources', {}):
                    profile.setdefault('classical_sources', {})[src] = {
                        'entry_id': entry.get('id'),
                        'grade_en': entry.get('grade_en', 'unknown'),
                        'grade_ar': entry.get('grade_ar', ''),
                    }
                    stats['source_additions'] += 1

                # Grade upgrade by authority chain
                current_grade = profile.get('grade_en', 'unknown')
                new_grade = entry.get('grade_en', 'unknown')
                matching_sources = [
                    GRADE_PRIORITY.get(s, 99)
                    for s in profile.get('classical_sources', {})
                    if profile['classical_sources'][s].get('grade_en') == current_grade
                ]
                current_priority = min(matching_sources) if matching_sources else 99
                new_priority = GRADE_PRIORITY.get(src, 99)

                if new_grade != 'unknown' and (current_grade == 'unknown' or new_priority < current_priority):
                    profile['grade_en'] = new_grade
                    profile['grade_ar'] = entry.get('grade_ar', '')
                    profile['color'] = GRADE_COLORS.get(new_grade, '#95a5a6')
                    stats['grade_upgrades'] += 1

                # Fill empty fields
                if not profile.get('death') and entry.get('death'):
                    profile['death'] = entry['death']
                if not profile.get('kunya') and entry.get('kunya'):
                    profile['kunya'] = entry['kunya']

            else:
                # New profile
                new_id = str(next_id)
                next_id += 1

                new_profile = {
                    'id': int(new_id),
                    'full_name': entry['name'],
                    'kunya': entry.get('kunya', ''),
                    'grade_en': entry.get('grade_en', 'unknown'),
                    'grade_ar': entry.get('grade_ar', ''),
                    'color': GRADE_COLORS.get(entry.get('grade_en', 'unknown'), '#95a5a6'),
                    'death': entry.get('death', ''),
                    'tabaqat': '',
                    'city': '',
                    'laqab': '',
                    'nasab': '',
                    'dhahabi': '',
                    'namings': [entry['name']],
                    'classical_sources': {
                        src: {
                            'entry_id': entry.get('id'),
                            'grade_en': entry.get('grade_en', 'unknown'),
                            'grade_ar': entry.get('grade_ar', ''),
                        }
                    },
                }

                profiles[new_id] = new_profile

                norm = normalize(entry['name'])
                norm_index[norm] = new_id
                by_name[entry['name']] = {
                    'id': int(new_id),
                    'grade_en': new_profile['grade_en'],
                    'grade_ar': new_profile['grade_ar'],
                    'color': new_profile['color'],
                    'death': new_profile.get('death', ''),
                    'full_name': entry['name'],
                    'kunya': entry.get('kunya', ''),
                }

                # Add to prefix index
                tokens = norm.split()
                if len(tokens) >= 3:
                    prefix_index[' '.join(tokens[:3])].add(new_id)
                if len(tokens) >= 4:
                    prefix_index[' '.join(tokens[:4])].add(new_id)

                src_new += 1
                stats['new'] += 1

        stats['matched'] += src_matched
        print(f"    {src:25s} {src_matched:>6,} matched, {src_new:>6,} new")

    return stats


# ── Step 3: Enrichment (Kaggle) ──────────────────────────────────────

def apply_kaggle(profiles, by_name):
    """Add global IDs and structured death dates from Kaggle dataset."""
    if not KAGGLE.exists():
        print("  [skip] Kaggle dataset not found")
        return 0

    with open(KAGGLE, encoding='utf-8') as f:
        kaggle = list(csv.DictReader(f))

    arabic_re = re.compile(r'[\u0600-\u06FF][\u0600-\u06FF\s\u0640]+')

    # Build name index
    norm_index = {}
    for name, entry in by_name.items():
        norm = normalize(name)
        if norm not in norm_index:
            norm_index[norm] = str(entry['id'])

    enriched = 0
    for r in kaggle:
        m = arabic_re.search(r.get('name', ''))
        if not m:
            continue
        ar = normalize(m.group(0).strip())
        ar = re.sub(r'\s*رضي?\s*الله\s*عن[هاـ].*', '', ar).strip()
        ar = re.sub(r'\s*صلي?\s*الله\s*علي[هـ].*', '', ar).strip()

        pid = norm_index.get(ar)
        if not pid or pid not in profiles:
            continue

        p = profiles[pid]
        if 'global_id' not in p:
            p['global_id'] = int(r['scholar_indx'])
            enriched += 1

        if not p.get('death') and r.get('death_date_hijri', '').strip() not in ('', 'NA', '-'):
            p['death'] = r['death_date_hijri'] + ' هـ'

        gen_m = re.search(r'\[(\d+)\w*\s+Generation\]', r.get('grade', ''))
        if gen_m and not p.get('generation'):
            p['generation'] = int(gen_m.group(1))

    return enriched


# ── Step 4: Validate and clean ───────────────────────────────────────

def validate_all(profiles, by_name):
    """Final validation pass: fix names, remove garbage."""
    fixed = 0
    deleted = []

    for pid, p in profiles.items():
        name = p.get('full_name', '')

        # Fix عبد compounds
        name = fix_abd_compound(name)
        if name != p['full_name']:
            p['full_name'] = name
            fixed += 1

        # Delete empty/invalid
        if not name or len(name.strip()) < 3 or not re.search(r'[\u0600-\u06FF]', name):
            deleted.append(pid)

    for pid in deleted:
        del profiles[pid]

    # Clean by_name
    valid_ids = set(int(k) for k in profiles.keys())
    by_name_clean = {n: e for n, e in by_name.items() if e.get('id') in valid_ids}

    return fixed, len(deleted), by_name_clean


# ── Step 5: Write output ─────────────────────────────────────────────

def write_database(profiles, by_name):
    """Write unified JSON + split files + CSVs + manifest."""
    # Unified
    data = {'profiles': profiles, 'by_name': by_name}
    tmp = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', dir=str(ROOT), delete=False)
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    if OUT_UNIFIED.exists():
        OUT_UNIFIED.unlink()
    shutil.move(tmp.name, str(OUT_UNIFIED))
    print(f"  Unified: {OUT_UNIFIED.stat().st_size:,} bytes")

    # Split by grade
    OUT_RIJAL.mkdir(exist_ok=True)
    grade_files = {
        'companion': 'profiles_companion.json',
        'reliable': 'profiles_reliable.json',
        'mostly_reliable': 'profiles_mostly_reliable.json',
        'weak': 'profiles_weak.json',
        'abandoned': 'profiles_abandoned.json',
        'fabricator': 'profiles_fabricator.json',
        'unknown': 'profiles_unknown.json',
    }

    buckets = {g: {} for g in grade_files}
    for pid, p in profiles.items():
        g = p.get('grade_en', 'unknown')
        if g not in buckets:
            g = 'unknown'
        buckets[g][pid] = p

    total = 0
    for grade, fname in grade_files.items():
        path = OUT_RIJAL / fname
        tmp_path = str(path) + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(buckets[grade], f, ensure_ascii=False)
        if path.exists():
            path.unlink()
        os.rename(tmp_path, str(path))
        total += len(buckets[grade])
        print(f"    {fname:35s} {len(buckets[grade]):>7,}")

    # by_name
    bn_path = OUT_RIJAL / 'by_name.json'
    tmp_path = str(bn_path) + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(by_name, f, ensure_ascii=False)
    if bn_path.exists():
        bn_path.unlink()
    os.rename(tmp_path, str(bn_path))
    print(f"    {'by_name.json':35s} {len(by_name):>7,} variants")

    # CSVs
    csv_dir = OUT_RIJAL / 'csv'
    csv_dir.mkdir(exist_ok=True)
    for grade, fname in grade_files.items():
        csv_path = csv_dir / f'{grade}.csv'
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'full_name', 'kunya', 'grade_ar', 'death', 'sources', 'teachers', 'students'])
            for pid, p in sorted(buckets[grade].items(), key=lambda x: int(x[0])):
                writer.writerow([
                    pid, p.get('full_name', ''), p.get('kunya', ''), p.get('grade_ar', ''),
                    p.get('death', ''), ','.join(p.get('classical_sources', {}).keys()),
                    len(p.get('teachers', [])), len(p.get('students', []))
                ])

    # Manifest
    manifest = {
        'files': [{'name': 'by_name.json', 'type': 'name_index'}] + [
            {'name': grade_files[g], 'type': 'profiles', 'grade': g, 'count': len(buckets[g])}
            for g in grade_files
        ],
        'total_profiles': total,
        'total_variants': len(by_name),
        'classical_texts': 22,
        'version': '3.0',
    }
    with open(OUT_RIJAL / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return total


# ── Main ─────────────────────────────────────────────────────────────

def main():
    if '--restore' in sys.argv:
        if BACKUP.exists():
            shutil.copy2(str(BACKUP), str(OUT_UNIFIED))
            print(f"Restored from backup: {BACKUP}")
        else:
            print("No backup found!")
        return

    dry_run = '--dry-run' in sys.argv

    print("=" * 60)
    print("BUILD RIJAL DATABASE v3.0")
    print("=" * 60)

    # Step 1: Foundation
    print("\n[1/5] Loading AR-Sanad foundation...")
    profiles, by_name = load_arsanad()
    print(f"  {len(profiles):,} profiles, {len(by_name):,} name variants")

    # Step 2: Merge all sources
    print("\n[2/5] Merging 22 classical text sources...")
    stats = merge_all_sources(profiles, by_name)
    print(f"\n  Matched: {stats['matched']:,}")
    print(f"  New profiles: {stats['new']:,}")
    print(f"  Grade upgrades: {stats['grade_upgrades']:,}")
    print(f"  Source cross-refs: {stats['source_additions']:,}")
    print(f"  Total profiles: {len(profiles):,}")

    # Step 3: Kaggle enrichment
    print("\n[3/5] Applying Kaggle enrichment...")
    kaggle_count = apply_kaggle(profiles, by_name)
    print(f"  {kaggle_count:,} profiles enriched with global IDs")

    # Step 4: Validate
    print("\n[4/5] Validating and cleaning...")
    fixed, deleted, by_name = validate_all(profiles, by_name)
    print(f"  Fixed names: {fixed:,}")
    print(f"  Deleted invalid: {deleted}")
    print(f"  Profiles: {len(profiles):,}")

    # Grade distribution
    grades = Counter(p.get('grade_en', 'unknown') for p in profiles.values())
    print(f"\n  Grade distribution:")
    for g, c in grades.most_common():
        print(f"    {g:20s} {c:>7,} ({100*c/len(profiles):5.1f}%)")

    if dry_run:
        print("\n[DRY RUN] No files written.")
        return

    # Step 5: Write
    print("\n[5/5] Writing database...")
    total = write_database(profiles, by_name)
    print(f"\n  DONE: {total:,} profiles, v3.0")
    print(f"  Restore command: python src/build_rijal_database.py --restore")


if __name__ == '__main__':
    main()
