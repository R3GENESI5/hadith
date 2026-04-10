"""
parse_rijal_v2.py
=================
Config-driven parser for all 22 classical rijal texts.
Uses narrator_lexicon.py as the single source of truth for
name cleaning, grade extraction, and boundary detection.

Each source is defined by a minimal config dict. The parsing
logic is shared -- only the entry pattern and source-specific
quirks vary.

Output: src/rijal_parsed_v2/{source_id}.json

Usage:
    python src/parse_rijal_v2.py              # parse all
    python src/parse_rijal_v2.py taqrib       # parse one
    python src/parse_rijal_v2.py --compare    # compare v2 vs v1
"""

import json, re, sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "src" / "rijal_raw"
OUT  = ROOT / "src" / "rijal_parsed_v2"
OUT.mkdir(exist_ok=True)

# Import shared lexicon
sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrator_lexicon import (
    GRADE_KEYWORDS, GRADE_COLORS, COMPANION_MARKERS, BOOK_GRADE_DEFAULTS,
    DIACRITICS_RE, strip_diacritics,
    extract_grade, apply_book_default,
    clean_narrator_name, strip_book_prefix, fix_abd_compound,
    is_valid_name, is_cross_reference,
)
from arabic_year_parser import extract_death_year_word


# ── OpenITI utilities ────────────────────────────────────────────────

PAGE_RE = re.compile(r'PageV\d+P\d+')
MS_RE   = re.compile(r'ms\d+')


def join_lines(text):
    """Join OpenITI continuation lines (~~) and strip metadata."""
    lines = text.split('\n')
    joined = []
    for line in lines:
        line = line.rstrip()
        if line.startswith('#META#') or line.startswith('######'):
            continue
        if line.startswith('~~'):
            if joined:
                joined[-1] += ' ' + line[2:].strip()
            else:
                joined.append(line[2:].strip())
        else:
            joined.append(line)
    result = '\n'.join(joined)
    result = PAGE_RE.sub('', result)
    result = MS_RE.sub('', result)
    return result


def split_at_pattern(text, pattern):
    """Split text into (match, body) tuples at each regex match."""
    matches = list(pattern.finditer(text))
    entries = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        entries.append((m, body))
    return entries


def clean_body(body):
    """Strip # line markers from body text for analysis."""
    body = re.sub(r'^#\s+', '', body, flags=re.MULTILINE)
    body = re.sub(r'--- misc', '', body)
    body = re.sub(r'### NB.*', '', body)
    body = re.sub(r'\s+', ' ', body).strip()
    return body


def extract_kunya(text):
    """Extract kunya (أبو/أبي + name) from text."""
    m = re.search(r'(أب[وي]\s+[\u0600-\u06FF]+(?:\s+[\u0600-\u06FF]+)?)', text)
    if m:
        kunya = m.group(1)
        kunya = re.sub(r'\s+(?:نزيل|من|بن|بنت|مولى|صاحب|البصري|الكوفي|المدني|الشامي|المصري|البغدادي).*$', '', kunya)
        return kunya.strip()
    return ''


def extract_death(text):
    """Extract death year using word-form parser."""
    year = extract_death_year_word(strip_diacritics(text))
    if year:
        return str(year) + ' هـ'
    return ''


# ── Source configs ───────────────────────────────────────────────────

SOURCES = {
    'taqrib': {
        'file': 'taqrib_tahdhib.txt',
        'title': 'Taqrib al-Tahdhib (Ibn Hajar)',
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': True,
        'entry_type': 'inline',  # name + grade + death all on one line
    },
    'tahdhib_kamal': {
        'file': 'tahdhib_kamal.txt',
        'title': 'Tahdhib al-Kamal (al-Mizzi)',
        'entry_pattern': r'^### \$ (\d+)\s*[-\s]*(.+)',
        'has_sigla': True,
        'entry_type': 'header_body',
    },
    'tahdhib_tahdhib': {
        'file': 'tahdhib_tahdhib.txt',
        'title': 'Tahdhib al-Tahdhib (Ibn Hajar)',
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': True,
        'entry_type': 'header_body',
    },
    'mizan': {
        'file': 'mizan_itidal.txt',
        'title': "Mizan al-I'tidal (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'jarh': {
        'file': 'jarh_tadil.txt',
        'title': "Al-Jarh wa al-Ta'dil (Ibn Abi Hatim)",
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'thiqat': {
        'file': 'thiqat.txt',
        'title': 'Al-Thiqat (Ibn Hibban)',
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'kamil': {
        'file': 'kamil_duafa.txt',
        'title': "Al-Kamil fi Du'afa (Ibn 'Adi)",
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'tarikh': {
        'file': 'tarikh_baghdad.txt',
        'title': 'Tarikh Baghdad (al-Khatib)',
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'tabaqat': {
        'file': 'tabaqat_ibn_saad.txt',
        'title': "Tabaqat al-Kubra (Ibn Sa'd)",
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'siyar': {
        'file': 'siyar.txt',
        'title': "Siyar A'lam al-Nubala (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
        'strip_sigla_suffix': True,  # has * (sigla) at end of header
    },
    'isaba': {
        'file': 'isaba.txt',
        'title': 'Al-Isaba fi Tamyiz al-Sahaba (Ibn Hajar)',
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'tarikh_islam': {
        'file': 'tarikh_islam.txt',
        'title': 'Tarikh al-Islam (al-Dhahabi)',
        'entry_pattern': r'^### \$BIO_MAN\$\s*$',
        'has_sigla': False,
        'entry_type': 'bio_man',  # special: name is in body, death in [الوفاة: N]
    },
    'lisan_mizan': {
        'file': 'lisan_mizan.txt',
        'title': 'Lisan al-Mizan (Ibn Hajar)',
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'durar_kamina': {
        'file': 'durar_kamina.txt',
        'title': 'Al-Durar al-Kamina (Ibn Hajar)',
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.*)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'kashif': {
        'file': 'kashif.txt',
        'title': 'Al-Kashif (al-Dhahabi)',
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.*)',
        'has_sigla': False,
        'entry_type': 'header_body',
    },
    'tadhkirat_huffaz': {
        'file': 'tadhkirat_huffaz.txt',
        'title': 'Tadhkirat al-Huffaz (al-Dhahabi)',
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': True,
        'entry_type': 'header_body',
    },
    'mughni_ducafa': {
        'file': 'mughni_ducafa.txt',
        'title': "Al-Mughni fi al-Du'afa (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s*(.*)',
        'has_sigla': True,
        'entry_type': 'header_body',
        'default_grade': 'weak',
    },
    'diwan_ducafa': {
        'file': 'diwan_ducafa.txt',
        'title': "Diwan al-Du'afa (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
        'default_grade': 'weak',
    },
    'dhayl_diwan': {
        'file': 'dhayl_diwan.txt',
        'title': "Dhayl Diwan al-Du'afa (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s*-?\s*(.+)',
        'has_sigla': False,
        'entry_type': 'header_body',
        'default_grade': 'weak',
    },
    'mucjam_shuyukh': {
        'file': 'mucjam_shuyukh.txt',
        'title': "Mu'jam al-Shuyukh (al-Dhahabi)",
        'entry_pattern': r'^### \$ (.+)',
        'has_sigla': False,
        'entry_type': 'unnumbered',
    },
    'macrifa_qurra': {
        'file': 'macrifa_qurra.txt',
        'title': "Ma'rifat al-Qurra al-Kibar (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': True,
        'entry_type': 'header_body',
    },
    'mucin_tabaqat': {
        'file': 'mucin_tabaqat.txt',
        'title': "Al-Mu'in fi Tabaqat al-Muhaddithin (al-Dhahabi)",
        'entry_pattern': r'^### \$ (\d+)\s+(.+)',
        'has_sigla': True,
        'entry_type': 'header_body',
    },
}


# ── The universal parser ─────────────────────────────────────────────

def parse_source(source_id):
    """Parse a single source using its config + shared lexicon."""
    cfg = SOURCES[source_id]
    path = RAW / cfg['file']
    if not path.exists():
        print(f"  [SKIP] {cfg['title']} — file not found")
        return []

    text = path.read_text(encoding='utf-8')
    text = join_lines(text)

    entry_re = re.compile(cfg['entry_pattern'], re.MULTILINE)
    has_sigla = cfg.get('has_sigla', False)
    default_grade = cfg.get('default_grade')
    entry_type = cfg.get('entry_type', 'header_body')

    # Special case: Tarikh al-Islam uses $BIO_MAN$ markers
    if entry_type == 'bio_man':
        return _parse_bio_man(text, entry_re, source_id)

    raw_entries = split_at_pattern(text, entry_re)
    entries = []

    for idx, (match, body) in enumerate(raw_entries):
        # Extract entry number and header
        groups = match.groups()
        if entry_type == 'unnumbered':
            num = idx
            header = groups[0].strip() if groups else ''
        else:
            num = int(groups[0]) if groups[0] else idx
            header = groups[1].strip() if len(groups) > 1 else ''

        body_clean = clean_body(body)

        # ── Name extraction ──────────────────────────────────────
        # For sources where header might be empty or just sigla
        if header and re.search(r'[\u0600-\u06FF]', header):
            raw_name = header
        else:
            raw_name = body_clean[:200]

        # Siyar: strip trailing * (sigla)
        if cfg.get('strip_sigla_suffix'):
            raw_name = re.sub(r'\s*\*\s*(\([^)]*\)\s*)?\.?$', '', raw_name)

        # Lisan: strip (ز) editor marker
        raw_name = re.sub(r'^\s*\(ز\)\s*:?\s*', '', raw_name)

        # Clean name using shared lexicon
        name = clean_narrator_name(raw_name, has_sigla_prefix=has_sigla)

        # Take up to first comma for long names
        name_end = re.search(r'[،,.]', name)
        if name_end and name_end.start() > 5 and len(name) > 80:
            name = name[:name_end.start()].strip()

        if not name or len(name) < 3 or not re.search(r'[\u0600-\u06FF]', name):
            continue

        # ── Cross-reference detection ────────────────────────────
        is_xref, xref_target = is_cross_reference(name, body_clean[:100])
        if is_xref:
            continue  # skip alias entries

        # ── Grade extraction ─────────────────────────────────────
        grade_text = header + ' ' + body_clean[:600]
        grade_en, grade_ar = extract_grade(grade_text)

        # Apply default grade for du'afa books
        if not grade_en and default_grade:
            grade_en = default_grade
            grade_ar = ''

        # Apply book-membership default
        grade_en, grade_ar = apply_book_default(grade_en, grade_ar, source_id)

        # Companion detection from body markers
        if not grade_en or grade_en == 'unknown':
            if any(m in body_clean[:500] for m in COMPANION_MARKERS):
                grade_en = 'companion'
                grade_ar = 'صحابي'

        # ── Death year ───────────────────────────────────────────
        death = extract_death(body_clean[:600])
        if not death:
            death = extract_death(header)

        # ── Kunya ────────────────────────────────────────────────
        kunya = extract_kunya(name)

        entries.append({
            'id': num,
            'name': name,
            'kunya': kunya,
            'grade_en': grade_en or 'unknown',
            'grade_ar': grade_ar or '',
            'color': GRADE_COLORS.get(grade_en or 'unknown', '#95a5a6'),
            'death': death,
            'source': source_id,
        })

    return entries


def _parse_bio_man(text, entry_re, source_id):
    """Special parser for Tarikh al-Islam ($BIO_MAN$ entries)."""
    raw_entries = split_at_pattern(text, entry_re)
    entries = []

    for idx, (match, body) in enumerate(raw_entries):
        body_clean = clean_body(body)

        # Death year from [الوفاة: N ه] marker
        death = ''
        death_m = re.search(r'\[الوفاة\s*:\s*(\d+)(?:\s*-\s*\d+)?\s*ه\s*\]', body_clean)
        if death_m:
            death = death_m.group(1) + ' هـ'

        # Name: before [الوفاة]
        name_line = body_clean.split('[الوفاة')[0] if '[الوفاة' in body_clean else body_clean[:200]
        name = clean_narrator_name(name_line, has_sigla_prefix=True)

        # Take up to first comma for long names
        name_end = re.search(r'[،,.]', name)
        if name_end and name_end.start() > 5 and len(name) > 80:
            name = name[:name_end.start()].strip()

        if not name or len(name) < 3 or not re.search(r'[\u0600-\u06FF]', name):
            continue

        kunya = extract_kunya(name)
        grade_en, grade_ar = extract_grade(body_clean[:500])

        if not grade_en or grade_en == 'unknown':
            if any(m in body_clean[:400] for m in COMPANION_MARKERS):
                grade_en = 'companion'
                grade_ar = 'صحابي'

        grade_en, grade_ar = apply_book_default(grade_en, grade_ar, source_id)

        entries.append({
            'id': idx,
            'name': name,
            'kunya': kunya,
            'grade_en': grade_en or 'unknown',
            'grade_ar': grade_ar or '',
            'color': GRADE_COLORS.get(grade_en or 'unknown', '#95a5a6'),
            'death': death,
            'source': source_id,
        })

    return entries


# ── Main ─────────────────────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    compare_mode = '--compare' in sys.argv
    targets = args if args else list(SOURCES.keys())

    print(f"Rijal Parser v2 — {len(targets)} source(s)\n")

    grand_total = 0
    all_grades = Counter()

    for source_id in targets:
        if source_id not in SOURCES:
            print(f"  [ERROR] Unknown source: {source_id}")
            continue

        cfg = SOURCES[source_id]
        print(f"  Parsing {cfg['title']}...")
        entries = parse_source(source_id)

        grades = Counter(e['grade_en'] for e in entries)
        print(f"    -> {len(entries):,} entries")
        for g, c in grades.most_common():
            print(f"       {g}: {c:,}")
            all_grades[g] += c

        # Validate names
        invalid = sum(1 for e in entries if not is_valid_name(e['name']))
        ibn_start = sum(1 for e in entries if e['name'].startswith('بن '))
        if invalid or ibn_start:
            print(f"    ⚠ invalid names: {invalid}, بن-start: {ibn_start}")

        # Save
        out_path = OUT / f"{source_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        print(f"    -> {out_path.name} ({out_path.stat().st_size:,} bytes)")

        # Compare with v1 if requested
        if compare_mode:
            v1_path = ROOT / "src" / "rijal_parsed" / f"{source_id}.json"
            if v1_path.exists():
                v1 = json.load(open(v1_path, encoding='utf-8'))
                v1_grades = Counter(e['grade_en'] for e in v1)
                print(f"    v1: {len(v1):,} entries")
                for g in sorted(set(list(grades.keys()) + list(v1_grades.keys()))):
                    diff = grades.get(g, 0) - v1_grades.get(g, 0)
                    if diff != 0:
                        print(f"      {g}: {v1_grades.get(g, 0)} -> {grades.get(g, 0)} ({diff:+d})")

        grand_total += len(entries)
        print()

    print(f"Total: {grand_total:,} entries")
    print(f"\nGrade summary:")
    for g, c in all_grades.most_common():
        print(f"  {g}: {c:,}")


if __name__ == '__main__':
    main()
