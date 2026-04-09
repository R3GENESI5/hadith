"""
parse_isnad_chains.py
=====================
Parses narrator chains from Arabic hadith text using transmission verb detection.
Outputs isnad_graph.json — precomputed Sankey data per book.

Transmission verbs (isnad indicators):
  حدثنا / حدثني  — narrated to us/me
  أخبرنا / أخبرني — informed us/me
  سمعت / سمع     — I/he heard
  روى             — reported
  عن              — on the authority of
  قال             — said (secondary)
"""

import json, re, glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'app' / 'data'

def strip_diacritics(t):
    return re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]', '', t)

# Transmission verb patterns (stripped of diacritics)
TRANS_VERBS = [
    'حدثنا', 'حدثني', 'حدثه', 'حدثهم',
    'اخبرنا', 'اخبرني', 'اخبره', 'اخبرهم',
    'انبانا', 'انباني',
    'سمعت', 'سمعنا', 'سمع',
    'روى', 'رواه',
    'عن',
    'قال',
]

# Build pattern: match verb then capture up to next verb or sentence end
TRANS_PATTERN = re.compile(
    r'(?:' + '|'.join(re.escape(v) for v in TRANS_VERBS) + r')\s+([^،,،\n]{5,80}?)(?=\s*(?:' +
    '|'.join(re.escape(v) for v in TRANS_VERBS) + r'|\Z|،|قال\s*:))',
    re.UNICODE
)

# Father-son lookup for resolving عن أبيه / عن أبي
FATHER_MAP_PATH = Path(__file__).parent / 'isnad_father_map.json'
FATHER_MAP = {}
if FATHER_MAP_PATH.exists():
    with open(FATHER_MAP_PATH, encoding='utf-8') as f:
        raw = json.load(f)
        FATHER_MAP = {strip_diacritics(k): strip_diacritics(v)
                      for k, v in raw.items() if not k.startswith('_')}

# Kunya → real name lookup for tooltip display
KUNYA_MAP_PATH = Path(__file__).parent / 'isnad_kunya_map.json'
KUNYA_MAP = {}
if KUNYA_MAP_PATH.exists():
    with open(KUNYA_MAP_PATH, encoding='utf-8') as f:
        raw = json.load(f)
        KUNYA_MAP = {strip_diacritics(k): v
                     for k, v in raw.items() if not k.startswith('_')}

# Grandfather lookup for resolving عن جده
GRANDFATHER_MAP_PATH = Path(__file__).parent / 'isnad_grandfather_map.json'
GRANDFATHER_MAP = {}
if GRANDFATHER_MAP_PATH.exists():
    with open(GRANDFATHER_MAP_PATH, encoding='utf-8') as f:
        raw = json.load(f)
        GRANDFATHER_MAP = {strip_diacritics(k): strip_diacritics(v)
                           for k, v in raw.items() if not k.startswith('_')}

# Mother lookup for resolving عن أمه
MOTHER_MAP_PATH = Path(__file__).parent / 'isnad_mother_map.json'
MOTHER_MAP = {}
if MOTHER_MAP_PATH.exists():
    with open(MOTHER_MAP_PATH, encoding='utf-8') as f:
        raw = json.load(f)
        MOTHER_MAP = {strip_diacritics(k): strip_diacritics(v)
                      for k, v in raw.items() if not k.startswith('_')}

# Grandmother lookup for resolving عن جدته
GRANDMOTHER_MAP_PATH = Path(__file__).parent / 'isnad_grandmother_map.json'
GRANDMOTHER_MAP = {}
if GRANDMOTHER_MAP_PATH.exists():
    with open(GRANDMOTHER_MAP_PATH, encoding='utf-8') as f:
        raw = json.load(f)
        GRANDMOTHER_MAP = {strip_diacritics(k): strip_diacritics(v)
                           for k, v in raw.items() if not k.startswith('_')}

# Uncle lookup for resolving standalone عن عمه
UNCLE_MAP_PATH = Path(__file__).parent / 'isnad_uncle_map.json'
UNCLE_MAP = {}
if UNCLE_MAP_PATH.exists():
    with open(UNCLE_MAP_PATH, encoding='utf-8') as f:
        raw = json.load(f)
        UNCLE_MAP = {strip_diacritics(k): strip_diacritics(v)
                     for k, v in raw.items() if not k.startswith('_')}

# Name cleanup
def clean_name(s):
    s = strip_diacritics(s.strip())
    # Remove kashida (tatweel) used for text stretching
    s = s.replace('\u0640', '')
    # Remove honorifics (رضي or رضى الله عنه/عنها/عنهما)
    s = re.sub(r'\s*رض[يى]\s*الله\s*عنه[ما]*\s*', '', s)
    s = re.sub(r'[ـ\s]*عليه\s*السلام[ـ\s]*', '', s)
    s = re.sub(r'[ـ\s]*صلى\s*الله\s*عليه[ـ\s]*.*', '', s)
    s = re.sub(r'^\s*ان\s+', '', s)
    s = re.sub(r'^\s*انه\s+', '', s)
    # Remove trailing قال: or قال and quotes
    s = re.sub(r'\s*قال\s*:?\s*"?\s*$', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def extract_chain(arabic_text):
    """Extract narrator chain from Arabic hadith text."""
    clean = strip_diacritics(arabic_text)
    # Split on transmission verbs to get segments
    segments = re.split(
        r'\b(?:حدثنا|حدثني|حدثه|اخبرنا|اخبرني|سمعت|سمعنا|انبانا|عن)\s+',
        clean
    )
    chain = []
    segs = segments[1:]  # skip text before first verb
    for idx, seg in enumerate(segs):
        # Take up to the next verb, comma, or paragraph break
        name_part = re.split(r'[،,\n]|(?:\s+(?:قال|ان|انه)\s)', seg)[0]
        name_part = clean_name(name_part)

        # Kunya repair: if name_part is just أبي/أبو, peek at next segment
        # to see if it forms a kunya (e.g. أبي + صالح = أبي صالح)
        if name_part in ('أبي', 'أبو', 'ابي', 'ابو') and idx + 1 < len(segs):
            next_seg = re.split(r'[،,\n]|(?:\s+(?:قال|ان|انه)\s)', segs[idx + 1])[0]
            next_name = clean_name(next_seg)
            if next_name and len(next_name) >= 2 and next_name not in ('الله', 'رسول', 'النبي'):
                # This is a kunya: أبي + صالح = أبي صالح
                name_part = name_part + ' ' + next_name
                segs[idx + 1] = ''  # consume the next segment

        # Filter: must be 3+ chars, no digits, not a common Arabic particle
        if (len(name_part) >= 3
                and not re.search(r'\d', name_part)
                and name_part not in ('الله', 'رسول', 'النبي', 'ذلك', 'هذا', 'كان')):
            # Relative references: عن مولاه X, عن عمه X, عن أمه X
            # If the name follows the relative term, use the name; otherwise drop
            RELATIVE_TERMS = {
                'عمه', 'عمي', 'عمته', 'عمتي',
                'أمه', 'أمي',
                'أخيه', 'أخي', 'أخته', 'أختي',
                'خاله', 'خالي', 'خالته', 'خالتي',
                'ابنه', 'ابني', 'ابنته', 'ابنتي',
                'جدته', 'جدتي',
                'زوجها', 'زوجي', 'زوجته',
                'مولاه', 'مولاي', 'مولاته', 'مولاها',
            }
            # Case 1: name_part is JUST the relative term (e.g. "عمه")
            # The actual name may be after a comma in the SAME segment
            # e.g. segment = "عمه، واسع بن حبان،" → name_part = "عمه"
            # but "واسع بن حبان" is the real narrator
            if name_part in RELATIVE_TERMS:
                resolved = False
                # First: check the rest of the current segment after the comma
                raw_seg = segs[idx]
                comma_parts = re.split(r'[،,]', raw_seg)
                if len(comma_parts) >= 2:
                    after_comma = clean_name(comma_parts[1])
                    if (after_comma and len(after_comma) >= 3
                            and after_comma not in ('الله', 'رسول', 'النبي')
                            and not after_comma.startswith('أن')
                            and not after_comma.startswith('قال')):
                        name_part = after_comma
                        resolved = True
                # Second: peek at next segment
                if not resolved and idx + 1 < len(segs):
                    next_seg = re.split(r'[،,\n]|(?:\s+(?:قال|ان|انه)\s)', segs[idx + 1])[0]
                    next_name = clean_name(next_seg)
                    if (next_name and len(next_name) >= 3
                            and next_name not in ('الله', 'رسول', 'النبي', 'ذلك', 'هذا', 'كان')
                            and not next_name.startswith('أن')
                            and not next_name.startswith('قال')):
                        name_part = next_name
                        segs[idx + 1] = ''
                        resolved = True
                # Third: try lookup tables (mother, grandmother, uncle)
                if not resolved and chain:
                    prev = chain[-1]
                    lookup_maps = {
                        'أمه': MOTHER_MAP, 'أمي': MOTHER_MAP,
                        'جدته': GRANDMOTHER_MAP, 'جدتي': GRANDMOTHER_MAP,
                        'عمه': UNCLE_MAP, 'عمي': UNCLE_MAP,
                    }
                    lmap = lookup_maps.get(name_part)
                    if lmap:
                        looked_up = lmap.get(prev)
                        if looked_up:
                            name_part = looked_up
                            resolved = True
                if not resolved:
                    continue  # truly standalone, drop

            # Case 2: name_part STARTS with relative term + name
            # e.g. "مولاه عبد الله بن الحارث" → extract "عبد الله بن الحارث"
            else:
                for rel in RELATIVE_TERMS:
                    if name_part.startswith(rel + ' ') and len(name_part) > len(rel) + 2:
                        name_part = name_part[len(rel):].strip()
                        name_part = re.sub(r'^[،,]\s*', '', name_part).strip()
                        break
            # Resolve relative references using previous narrator in chain
            # أبيه / أبي = "his father", جده = "his grandfather"
            if name_part in ('أبيه', 'ابيه', 'أبي') and chain:
                prev = chain[-1]
                father = FATHER_MAP.get(prev)
                if father:
                    name_part = father
                else:
                    continue  # skip unresolvable reference
            elif name_part.startswith('جده') and chain:
                prev = chain[-1]
                grandfather = GRANDFATHER_MAP.get(prev)
                if grandfather:
                    name_part = grandfather
                else:
                    continue  # skip unresolvable جده
            chain.append(name_part)
        if len(chain) >= 8:  # max chain depth
            break
    return chain

def book_isnad_graph(book_id, hadiths, grade_lookup):
    """Build Sankey node/link data for one book."""
    edge_counts = defaultdict(int)
    narrator_hadith_count = defaultdict(int)
    total_parsed = 0

    for h in hadiths:
        arabic = h.get('arabic', '')
        if not arabic or len(arabic) < 50:
            continue
        chain = extract_chain(arabic)
        if len(chain) < 2:
            continue
        total_parsed += 1
        for name in chain:
            narrator_hadith_count[name] += 1
        for i in range(len(chain) - 1):
            edge_counts[(chain[i], chain[i+1])] += 1

    if not edge_counts:
        return None

    # Build nodes (top 50 by hadith count)
    top_narrators = sorted(narrator_hadith_count.items(), key=lambda x: -x[1])[:60]
    node_set = {n for n, _ in top_narrators}

    nodes = []
    node_idx = {}
    for name, count in top_narrators:
        grade_data = grade_lookup.get(name, {})
        # Look up kunya → real name
        name_stripped = strip_diacritics(name)
        kunya_data = KUNYA_MAP.get(name_stripped, {})
        node = {
            'id':       name,
            'count':    count,
            'grade_en': grade_data.get('grade_en', 'unknown'),
            'grade_ar': grade_data.get('grade_ar', ''),
            'color':    grade_data.get('color', '#95a5a6'),
            'death':    grade_data.get('death', ''),
            'places':   grade_data.get('places', ''),
        }
        if kunya_data:
            node['real_name'] = kunya_data.get('real', '')
            node['name_en']   = kunya_data.get('en', '')
            node['bio']       = kunya_data.get('note', '')
        nodes.append(node)
        node_idx[name] = len(node_idx)

    # Build links (only between nodes in our top set)
    links = []
    for (src, tgt), count in edge_counts.items():
        if src in node_set and tgt in node_set and count >= 2:
            links.append({
                'source': node_idx[src],
                'target': node_idx[tgt],
                'value':  count,
            })

    return {
        'book':        book_id,
        'total_parsed': total_parsed,
        'nodes':       nodes,
        'links':       links,
    }

# ── Main ─────────────────────────────────────────────────────────────────────
print('Loading narrator grades...')
grades_data = json.load(open(DATA / 'narrator_grades.json', encoding='utf-8'))
grade_lookup = grades_data['grade_lookup']
print(f'  {len(grade_lookup):,} graded narrators')

print('\nParsing isnad chains by book...')
graphs = {}
books_to_parse = ['bukhari', 'muslim', 'abudawud', 'nasai', 'tirmidhi',
                  'ibnmajah', 'ahmed', 'malik', 'darimi',
                  'musannaf_ibnabi_shaybah', 'mishkat_almasabih']

for book_id in books_to_parse:
    book_dir = DATA / 'sunni' / book_id
    if not book_dir.exists():
        print(f'  {book_id}: not found, skipping')
        continue
    idx_path = book_dir / 'index.json'
    if not idx_path.exists():
        continue
    chapters = json.load(open(idx_path, encoding='utf-8'))
    all_hadiths = []
    for ch in chapters:
        ch_file = book_dir / ch['file']
        if ch_file.exists():
            all_hadiths.extend(json.load(open(ch_file, encoding='utf-8')))

    graph = book_isnad_graph(book_id, all_hadiths, grade_lookup)
    if graph:
        graphs[book_id] = graph
        print(f'  {book_id:35s}: {graph["total_parsed"]:5d} chains parsed, '
              f'{len(graph["nodes"]):3d} nodes, {len(graph["links"]):4d} links')
    else:
        print(f'  {book_id:35s}: no chains found')

print(f'\nTotal books with isnad graphs: {len(graphs)}')

# ── Save ─────────────────────────────────────────────────────────────────────
out_path = DATA / 'isnad_graph.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(graphs, f, ensure_ascii=False, separators=(',', ':'))
sz = out_path.stat().st_size // 1024
print(f'Saved isnad_graph.json ({sz} KB)')
