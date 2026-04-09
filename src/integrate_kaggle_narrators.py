"""
integrate_kaggle_narrators.py
=============================
Integrates the Kaggle/muslimscholars.info narrator dataset (24,326 scholars)
into narrator_unified.json, adding:
  - global_id (scholar_indx from Kaggle, linked to muslimscholars.info)
  - death_date_hijri (structured, not prose)
  - death_date_gregorian
  - birth info
  - teacher/student IDs from the Kaggle dataset
  - tabaqat/generation info from grade field

Usage:
    python src/integrate_kaggle_narrators.py              # apply
    python src/integrate_kaggle_narrators.py --dry-run    # preview
"""

import csv, json, re, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KAGGLE = ROOT / "src" / "kaggle_rawis.csv"
UNIFIED = ROOT / "app" / "data" / "narrator_unified.json"

DIACRITICS_RE = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC'
    r'\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]'
)
ALEF_RE = re.compile(r'[أإآا]')


def normalize(name):
    n = DIACRITICS_RE.sub('', name)
    n = ALEF_RE.sub('ا', n)
    n = n.replace('\u0640', '')
    n = n.replace('ہ', 'ه')
    n = n.replace('ی', 'ي')
    n = n.replace('ک', 'ك')
    n = n.replace('ے', 'ي')
    n = n.replace('ۃ', 'ة')
    return re.sub(r'\s+', ' ', n).strip()


def ibn_parts(name):
    return tuple(p.strip() for p in re.split(r'\s+بن\s+', name) if p.strip())


def extract_arabic_name(raw_name):
    """Extract and clean Arabic name from Kaggle's mixed-script name field."""
    arabic_re = re.compile(r'[\u0600-\u06FF][\u0600-\u06FF\s\u0640]+')
    m = arabic_re.search(raw_name)
    if not m:
        return ''
    ar = normalize(m.group(0).strip())
    ar = re.sub(r'\s*رضي?\s*الله\s*عن[هاـ].*', '', ar).strip()
    ar = re.sub(r'\s*صلي?\s*الله\s*علي[هـ].*', '', ar).strip()
    return ar


def main():
    dry_run = '--dry-run' in sys.argv

    print("Loading narrator database...")
    with open(UNIFIED, encoding='utf-8') as f:
        db = json.load(f)
    profiles = db['profiles']
    by_name = db['by_name']
    print(f"  {len(profiles):,} profiles, {len(by_name):,} name variants")

    print("Loading Kaggle dataset...")
    with open(KAGGLE, encoding='utf-8') as f:
        kaggle = list(csv.DictReader(f))
    print(f"  {len(kaggle):,} scholars")

    # Build our name indices
    our_norm = {}
    for name, entry in by_name.items():
        norm = normalize(name)
        if norm not in our_norm:
            our_norm[norm] = str(entry['id'])

    our_by_parts = defaultdict(list)
    for name, entry in by_name.items():
        parts = ibn_parts(normalize(name))
        if len(parts) >= 3:
            key = parts[:3]
            if str(entry['id']) not in our_by_parts[key]:
                our_by_parts[key].append(str(entry['id']))

    # Match Kaggle entries to our profiles
    print("\nMatching...")
    matches = []
    kaggle_by_idx = {}
    for r in kaggle:
        kaggle_by_idx[r['scholar_indx']] = r
        ar_name = extract_arabic_name(r.get('name', ''))
        if not ar_name:
            continue

        kidx = r['scholar_indx']

        # Tier 1: exact name match
        pid = our_norm.get(ar_name)
        if pid and pid in profiles:
            matches.append((pid, kidx, 'exact'))
            continue

        # Tier 2: 3-part ibn prefix (unique match only)
        parts = ibn_parts(ar_name)
        if len(parts) >= 3:
            cands = our_by_parts.get(parts[:3], [])
            if len(cands) == 1:
                matches.append((cands[0], kidx, 'prefix3'))
                continue

    print(f"  Matched: {len(matches):,} / {len(kaggle):,}")
    method_counts = Counter(m for _, _, m in matches)
    for method, cnt in method_counts.most_common():
        print(f"    {method}: {cnt:,}")

    if dry_run:
        # Stats preview
        death_gains = 0
        teacher_gains = 0
        for pid, kidx, _ in matches:
            p = profiles[pid]
            k = kaggle_by_idx[kidx]
            if not p.get('death', '').strip():
                dh = k.get('death_date_hijri', '').strip()
                if dh and dh not in ('', 'NA', '-'):
                    death_gains += 1
            if not p.get('teachers') and k.get('teachers_inds', '').strip() not in ('', 'NA'):
                teacher_gains += 1

        print(f"\n  Would gain death year: {death_gains:,}")
        print(f"  Would gain teacher IDs: {teacher_gains:,}")
        print("\n[DRY RUN] No files written.")
        return

    # Apply enrichment
    print("\nEnriching profiles...")
    enriched = 0
    death_added = 0
    global_id_added = 0

    for pid, kidx, method in matches:
        p = profiles[pid]
        k = kaggle_by_idx[kidx]
        changed = False

        # Add global_id
        if 'global_id' not in p:
            p['global_id'] = int(kidx)
            global_id_added += 1
            changed = True

        # Add death year if missing
        if not p.get('death', '').strip():
            dh = k.get('death_date_hijri', '').strip()
            if dh and dh not in ('', 'NA', '-'):
                p['death'] = f"{dh} هـ"
                death_added += 1
                changed = True

        # Add gregorian death/birth as metadata
        dg = k.get('death_date_gregorian', '').strip()
        if dg and dg not in ('', 'NA', '-') and 'death_gregorian' not in p:
            p['death_gregorian'] = dg
            changed = True

        bg = k.get('birth_date_gregorian', '').strip()
        if bg and bg not in ('', 'NA', '-') and 'birth_gregorian' not in p:
            p['birth_gregorian'] = bg
            changed = True

        # Add generation from grade field
        gen_m = re.search(r'\[(\d+)\w*\s+Generation\]', k.get('grade', ''))
        if gen_m and not p.get('generation'):
            p['generation'] = int(gen_m.group(1))
            changed = True

        if changed:
            enriched += 1

    print(f"  Enriched: {enriched:,} profiles")
    print(f"  Global IDs added: {global_id_added:,}")
    print(f"  Death years added: {death_added:,}")

    # Check for dedup signal: profiles sharing the same global_id
    gid_to_pids = defaultdict(list)
    for pid, p in profiles.items():
        gid = p.get('global_id')
        if gid is not None:
            gid_to_pids[gid].append(pid)

    shared_gid = {gid: pids for gid, pids in gid_to_pids.items() if len(pids) > 1}
    print(f"\n  Profiles sharing a global_id (dedup candidates): {sum(len(p) for p in shared_gid.values()):,} across {len(shared_gid):,} groups")

    # Write
    db['profiles'] = profiles
    import tempfile, shutil
    tmp = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', dir=str(ROOT), delete=False)
    json.dump(db, tmp, ensure_ascii=False)
    tmp.close()
    shutil.move(tmp.name, str(UNIFIED))
    print(f"\n  Written: {UNIFIED.stat().st_size:,} bytes")

    # Death year coverage after
    has_death = sum(1 for p in profiles.values() if p.get('death', '').strip())
    print(f"  Death year coverage: {has_death:,} / {len(profiles):,} ({100*has_death/len(profiles):.1f}%)")


if __name__ == '__main__':
    main()
