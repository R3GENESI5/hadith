"""
dedup_narrators.py
==================
Two-layer cross-text narrator deduplication for narrator_unified.json.

Layer 1 (Conservative): high-confidence merges
  - Exact normalized full_name + death within 2 years (names with 3+ بن parts)
  - Exact normalized full_name + same kunya (names with 3+ بن parts)
  - بن-prefix match (all shared parts match) + death within 2 years

Layer 2 (Aggressive): probable merges
  - بن-prefix match with 4+ shared parts + no death conflict
  - Exact full_name for 3+ part names + no death conflict (even without kunya)
  - بن-prefix match (3 parts) + rare kunya match + no death conflict

Usage:
    python src/dedup_narrators.py --dry-run          # preview both layers
    python src/dedup_narrators.py --layer 1          # apply conservative only
    python src/dedup_narrators.py --layer 2          # apply both layers
    python src/dedup_narrators.py --layer 1 --log    # write merge log
"""

import json, re, sys
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
UNIFIED = ROOT / "app" / "data" / "narrator_unified.json"
LOG_DIR = ROOT / "src" / "dedup_logs"

# ── Normalization ────────────────────────────────────────────────────

DIACRITICS_RE = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC'
    r'\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]'
)
ALEF_RE = re.compile(r'[أإآا]')


def normalize(name):
    n = DIACRITICS_RE.sub('', name)
    n = ALEF_RE.sub('ا', n)
    n = n.replace('\u0640', '')
    return re.sub(r'\s+', ' ', n).strip()


def ibn_parts(name):
    """Split by بن into full nasab parts: ['محمد', 'عبد الله', 'احمد', ...]"""
    return [p.strip() for p in re.split(r'\s+بن\s+', normalize(name)) if p.strip()]


def death_year(profile):
    m = re.search(r'(\d+)', profile.get('death', ''))
    return int(m.group(1)) if m else None


def primary_kunya(profile):
    """First kunya, normalized."""
    raw = profile.get('kunya', '')
    first = raw.split('،')[0].strip()
    return normalize(first) if first else ''


def primary_city(profile):
    """First city, normalized."""
    raw = profile.get('city', '')
    first = raw.split('،')[0].strip()
    return normalize(first) if first else ''


def is_prefix_match(parts_a, parts_b):
    """True if all shared positions match (shorter is prefix of longer)."""
    min_len = min(len(parts_a), len(parts_b))
    return min_len >= 3 and all(parts_a[i] == parts_b[i] for i in range(min_len))


# Kunyas shared by 100+ profiles are too common to be a dedup signal alone
COMMON_KUNYAS = {
    'ابو عبد الله', 'ابو محمد', 'ابو بكر', 'ابو الحسن',
    'ابو علي', 'ابو الفضل', 'ابو العباس', 'ابو الحسين',
    'ابو عمر', 'ابو القاسم', 'ابو سعيد', 'ابو عمرو',
    'ابو جعفر', 'ابو الخير', 'ابو ابراهيم', 'ابو يوسف',
    'ابو عبد الرحمن', 'ابو حفص', 'ابو اسحاق', 'ابو موسى',
    'ابو هريرة', 'ابو سلمة', 'ابو زرعة', 'ابو حاتم',
    'ابو نصر', 'ابو طالب', 'ابو الطيب', 'ابو منصور',
}

GRADE_STRENGTH = {
    'companion': 6, 'reliable': 5, 'mostly_reliable': 4,
    'weak': 3, 'abandoned': 2, 'fabricator': 1, 'unknown': 0,
}

GRADE_COLORS = {
    'companion': '#9b59b6', 'reliable': '#2ecc71',
    'mostly_reliable': '#f39c12', 'weak': '#e74c3c',
    'abandoned': '#c0392b', 'fabricator': '#8b0000', 'unknown': '#95a5a6',
}


def find_merge_pairs(profiles):
    """Find all merge candidates, separated by layer."""

    # ── Index building ────────────────────────────────────────────────
    by_norm_name = defaultdict(list)
    by_first3 = defaultdict(list)

    for pid, p in profiles.items():
        name = p.get('full_name', '')
        norm = normalize(name)
        parts = ibn_parts(name)
        dy = death_year(p)
        kunya = primary_kunya(p)

        city = primary_city(p)

        if norm:
            by_norm_name[norm].append((pid, parts, dy, kunya, city))
        if len(parts) >= 3:
            by_first3[tuple(parts[:3])].append((pid, parts, dy, kunya, city))

    layer1 = []  # conservative
    layer2 = []  # aggressive
    seen = set()

    def add_pair(pid1, pid2, reason, layer):
        pair = (min(pid1, pid2, key=int), max(pid1, pid2, key=int))
        if pair not in seen:
            seen.add(pair)
            target = layer1 if layer == 1 else layer2
            target.append((*pair, reason))

    # ── Layer 1: Exact name matches ───────────────────────────────────
    for norm, entries in by_norm_name.items():
        if len(entries) < 2:
            continue
        for i, (pid1, parts1, dy1, k1, c1) in enumerate(entries):
            for pid2, parts2, dy2, k2, c2 in entries[i+1:]:
                n_parts = max(len(parts1), len(parts2))
                death_ok = dy1 and dy2 and abs(dy1 - dy2) <= 2
                kunya_ok = k1 and k2 and k1 == k2
                city_ok = c1 and c2 and c1 == c2

                # Death CONFLICT = skip (different people)
                death_conflict = dy1 and dy2 and abs(dy1 - dy2) > 5

                if n_parts < 3:
                    # Short names: require death match AND (kunya or city)
                    if death_ok and (kunya_ok or city_ok):
                        add_pair(pid1, pid2, f'exact_short+death+signal', 1)
                else:
                    # 3+ parts: death within 2 OR same kunya OR same city
                    if death_conflict:
                        continue
                    if death_ok:
                        add_pair(pid1, pid2, f'exact+death', 1)
                    elif kunya_ok and not death_conflict:
                        # Kunya match only safe when no death conflict
                        add_pair(pid1, pid2, f'exact+kunya', 1)
                    elif city_ok and (dy1 is None or dy2 is None):
                        add_pair(pid1, pid2, f'exact+city', 1)
                    elif not dy1 or not dy2:
                        # One has no death: aggressive
                        if n_parts >= 4:
                            add_pair(pid1, pid2, f'exact_long_no_death', 2)
                        elif city_ok:
                            add_pair(pid1, pid2, f'exact+city_no_death', 2)

    # ── Layer 1: Prefix match + death ─────────────────────────────────
    for key, entries in by_first3.items():
        if len(entries) < 2:
            continue
        for i, (pid1, parts1, dy1, k1, c1) in enumerate(entries):
            for pid2, parts2, dy2, k2, c2 in entries[i+1:]:
                if not is_prefix_match(parts1, parts2):
                    continue
                # Death conflict = skip entirely
                if dy1 and dy2 and abs(dy1 - dy2) > 5:
                    continue

                shared = min(len(parts1), len(parts2))
                death_ok = dy1 and dy2 and abs(dy1 - dy2) <= 2
                city_ok = c1 and c2 and c1 == c2

                if death_ok:
                    add_pair(pid1, pid2, f'prefix({shared})+death', 1)
                elif death_ok is False and city_ok and shared >= 3:
                    # Same city + prefix match, death within 5
                    if dy1 and dy2 and abs(dy1 - dy2) <= 5:
                        add_pair(pid1, pid2, f'prefix({shared})+city+death5', 1)
                elif shared >= 4 and (not dy1 or not dy2):
                    # 4+ matching parts, no death conflict
                    if city_ok:
                        add_pair(pid1, pid2, f'prefix({shared})+city_no_death', 1)
                    else:
                        add_pair(pid1, pid2, f'prefix({shared})_no_death', 2)
                elif shared >= 3 and k1 and k2 and k1 == k2:
                    # Kunya match: still check death conflict
                    dy_conflict = dy1 and dy2 and abs(dy1 - dy2) > 5
                    if dy_conflict:
                        pass  # different people
                    elif k1 not in COMMON_KUNYAS:
                        add_pair(pid1, pid2, f'prefix(3)+rare_kunya({k1})', 2)
                    elif shared >= 4:
                        add_pair(pid1, pid2, f'prefix({shared})+common_kunya', 2)
                    elif city_ok:
                        add_pair(pid1, pid2, f'prefix(3)+common_kunya+city', 2)

    return layer1, layer2


def build_merge_groups(pairs, profiles):
    """Union-Find to build connected components, then split groups with
    internal death-year conflicts (transitive merge safety net)."""
    import re as _re

    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            sa = len(profiles[ra].get('classical_sources', {}))
            sb = len(profiles[rb].get('classical_sources', {}))
            if sb > sa:
                ra, rb = rb, ra
            parent[rb] = ra

    for pid1, pid2, reason in pairs:
        union(pid1, pid2)

    groups = defaultdict(list)
    for pid1, pid2, reason in pairs:
        groups[find(pid1)].append((pid1, pid2, reason))

    # Collect members per group
    raw_groups = {}
    for root, pair_list in groups.items():
        members = set()
        reasons = []
        for pid1, pid2, reason in pair_list:
            members.add(pid1)
            members.add(pid2)
            reasons.append(reason)
        raw_groups[find(root)] = {
            'members': sorted(members, key=int),
            'reasons': list(set(reasons)),
        }

    # ── Split groups with internal death conflicts ────────────────────
    def _dy(pid):
        m = _re.search(r'(\d+)', profiles[pid].get('death', ''))
        return int(m.group(1)) if m else None

    result = {}
    for root, group in raw_groups.items():
        members = group['members']
        dated = [(pid, _dy(pid)) for pid in members if _dy(pid) is not None]

        # Check if any pair of dated members conflicts (>5 year gap)
        has_conflict = False
        for i, (p1, d1) in enumerate(dated):
            for p2, d2 in dated[i+1:]:
                if abs(d1 - d2) > 5:
                    has_conflict = True
                    break
            if has_conflict:
                break

        if not has_conflict:
            result[root] = group
        else:
            # Split: cluster dated members by compatible death years,
            # assign undated to the largest compatible cluster
            clusters = []  # list of sets
            for pid, dy in dated:
                placed = False
                for cluster in clusters:
                    # Check compatibility with all dated members in cluster
                    if all(abs(dy - _dy(m)) <= 5
                           for m in cluster if _dy(m) is not None):
                        cluster.add(pid)
                        placed = True
                        break
                if not placed:
                    clusters.append({pid})

            # Assign undated members to the cluster they have direct pairs with
            pair_index = defaultdict(set)
            for pid1, pid2, _ in groups.get(find(root), []):
                pair_index[pid1].add(pid2)
                pair_index[pid2].add(pid1)

            undated = [pid for pid in members if _dy(pid) is None]
            for pid in undated:
                partners = pair_index.get(pid, set())
                best_cluster = None
                best_overlap = 0
                for cluster in clusters:
                    overlap = len(partners & cluster)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_cluster = cluster
                if best_cluster is not None:
                    best_cluster.add(pid)
                else:
                    clusters.append({pid})

            # Only keep clusters with 2+ members
            for cluster in clusters:
                if len(cluster) >= 2:
                    croot = min(cluster, key=int)
                    result[croot] = {
                        'members': sorted(cluster, key=int),
                        'reasons': group['reasons'],
                    }

    return result


def merge_profiles(profiles, by_name, groups):
    """Merge profiles within each group. Returns (new_profiles, new_by_name, merge_log)."""
    merge_log = []
    merged_away = set()

    for root_id, group in groups.items():
        members = group['members']
        if len(members) < 2:
            continue

        # Pick the best profile as primary (most sources, then best grade)
        def score(pid):
            p = profiles[pid]
            n_sources = len(p.get('classical_sources', {}))
            grade_s = GRADE_STRENGTH.get(p.get('grade_en', 'unknown'), 0)
            has_death = 1 if p.get('death', '').strip() else 0
            name_len = len(p.get('full_name', ''))
            return (n_sources, grade_s, has_death, name_len)

        primary_id = max(members, key=score)
        primary = profiles[primary_id]
        absorbed = [m for m in members if m != primary_id]

        log_entry = {
            'primary': primary_id,
            'primary_name': primary.get('full_name', ''),
            'absorbed': [],
            'reasons': group['reasons'],
        }

        for aid in absorbed:
            a = profiles[aid]
            log_entry['absorbed'].append({
                'id': aid,
                'name': a.get('full_name', ''),
                'grade': a.get('grade_en', 'unknown'),
                'sources': list(a.get('classical_sources', {}).keys()),
            })

            # Merge classical sources
            for src, ref in a.get('classical_sources', {}).items():
                if 'classical_sources' not in primary:
                    primary['classical_sources'] = {}
                if src not in primary['classical_sources']:
                    primary['classical_sources'][src] = ref

            # Merge namings
            existing = set(primary.get('namings', []))
            for n in a.get('namings', []):
                if n not in existing:
                    primary.setdefault('namings', []).append(n)
                    existing.add(n)

            # Fill empty fields from absorbed
            if not primary.get('death') and a.get('death'):
                primary['death'] = a['death']
            if not primary.get('kunya') and a.get('kunya'):
                primary['kunya'] = a['kunya']
            if not primary.get('tabaqat') and a.get('tabaqat'):
                primary['tabaqat'] = a['tabaqat']
            if not primary.get('city') and a.get('city'):
                primary['city'] = a['city']
            if not primary.get('laqab') and a.get('laqab'):
                primary['laqab'] = a['laqab']
            if not primary.get('nasab') and a.get('nasab'):
                primary['nasab'] = a['nasab']

            # Upgrade grade if absorbed has better info
            curr = GRADE_STRENGTH.get(primary.get('grade_en', 'unknown'), 0)
            abso = GRADE_STRENGTH.get(a.get('grade_en', 'unknown'), 0)
            if abso > curr:
                primary['grade_en'] = a['grade_en']
                primary['grade_ar'] = a.get('grade_ar', '')
                primary['color'] = GRADE_COLORS.get(a['grade_en'], '#95a5a6')

            merged_away.add(aid)

        merge_log.append(log_entry)

    # Rebuild profiles dict
    new_profiles = {pid: p for pid, p in profiles.items() if pid not in merged_away}

    # Rebuild by_name: redirect absorbed IDs to primary
    redirect = {}
    for root_id, group in groups.items():
        members = group['members']
        primary_id = max(members, key=lambda pid: (
            len(profiles[pid].get('classical_sources', {})),
            GRADE_STRENGTH.get(profiles[pid].get('grade_en', 'unknown'), 0),
        ))
        for m in members:
            if m != primary_id:
                redirect[int(m)] = int(primary_id)

    new_by_name = {}
    for name, entry in by_name.items():
        old_id = entry.get('id')
        if old_id in redirect:
            new_id = redirect[old_id]
            new_entry = dict(entry)
            new_entry['id'] = new_id
            # Update grade/color from primary profile
            if str(new_id) in new_profiles:
                p = new_profiles[str(new_id)]
                new_entry['grade_en'] = p.get('grade_en', 'unknown')
                new_entry['grade_ar'] = p.get('grade_ar', '')
                new_entry['color'] = p.get('color', '#95a5a6')
            new_by_name[name] = new_entry
        else:
            new_by_name[name] = entry

    return new_profiles, new_by_name, merge_log


def main():
    dry_run = '--dry-run' in sys.argv
    write_log = '--log' in sys.argv
    layer_arg = 2  # default: both layers
    if '--layer' in sys.argv:
        idx = sys.argv.index('--layer')
        layer_arg = int(sys.argv[idx + 1])

    print("Loading narrator database...")
    with open(UNIFIED, encoding='utf-8') as f:
        db = json.load(f)

    profiles = db['profiles']
    by_name = db['by_name']
    print(f"  {len(profiles):,} profiles, {len(by_name):,} name variants")

    print("\nFinding merge candidates...")
    layer1_pairs, layer2_pairs = find_merge_pairs(profiles)
    print(f"  Layer 1 (conservative): {len(layer1_pairs)} pairs")
    print(f"  Layer 2 (aggressive):   {len(layer2_pairs)} pairs")

    # Show reason breakdown
    for name, pairs in [('Layer 1', layer1_pairs), ('Layer 2', layer2_pairs)]:
        reasons = Counter(r for _, _, r in pairs)
        print(f"\n  {name} breakdown:")
        for reason, cnt in reasons.most_common():
            print(f"    {reason}: {cnt}")

    # Build groups
    if layer_arg >= 2:
        all_pairs = layer1_pairs + layer2_pairs
    else:
        all_pairs = layer1_pairs

    groups = build_merge_groups(all_pairs, profiles)
    total_absorbed = sum(len(g['members']) - 1 for g in groups.values())
    print(f"\n  Merge groups: {len(groups)}")
    print(f"  Profiles to absorb: {total_absorbed}")
    print(f"  Resulting profiles: {len(profiles) - total_absorbed:,}")

    if dry_run:
        print("\n[DRY RUN] Showing sample merges:\n")
        for i, (root_id, group) in enumerate(sorted(
            groups.items(),
            key=lambda x: -len(x[1]['members'])
        )[:20]):
            members = group['members']
            print(f"  Group {i+1} ({len(members)} profiles, {group['reasons']}):")
            for m in members:
                p = profiles[m]
                dy = death_year(p)
                srcs = list(p.get('classical_sources', {}).keys())
                mark = ' <-- PRIMARY' if m == max(members, key=lambda pid: (
                    len(profiles[pid].get('classical_sources', {})),
                    GRADE_STRENGTH.get(profiles[pid].get('grade_en', 'unknown'), 0),
                )) else ''
                print(f"    {m}: {p.get('full_name','')[:60]} | d.{dy} | {p.get('grade_en')} | {srcs}{mark}")
            print()
        return

    # Apply merges
    print(f"\nApplying layer {layer_arg} merges...")
    new_profiles, new_by_name, merge_log = merge_profiles(profiles, by_name, groups)

    # Write log
    if write_log:
        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"dedup_layer{layer_arg}.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(merge_log, f, ensure_ascii=False, indent=2)
        print(f"  Merge log: {log_path} ({len(merge_log)} entries)")

    # Write output
    db['profiles'] = new_profiles
    db['by_name'] = new_by_name
    print(f"\n  Writing {UNIFIED.name}...")
    with open(UNIFIED, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False)

    print(f"  Profiles: {len(profiles):,} -> {len(new_profiles):,} ({total_absorbed:,} merged)")
    print(f"  Name variants: {len(by_name):,} -> {len(new_by_name):,}")
    print(f"  -> {UNIFIED.stat().st_size:,} bytes")

    # Grade distribution after
    grades = Counter(p.get('grade_en', 'unknown') for p in new_profiles.values())
    print(f"\n  Grade distribution after dedup:")
    for g, c in grades.most_common():
        pct = 100 * c / len(new_profiles)
        print(f"    {g}: {c:,} ({pct:.1f}%)")


if __name__ == '__main__':
    main()
