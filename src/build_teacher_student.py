"""
build_teacher_student.py
========================
Enriches narrator_unified.json with teacher-student links from AR-Sanad.

For each profile, adds:
  - teachers: [list of profile IDs this narrator learned from]
  - students: [list of profile IDs this narrator taught]

AR-Sanad uses internal IDs (0-18297). These map 1:1 to profile IDs in
narrator_unified.json, with dedup redirects for the 96 absorbed profiles.

Usage:
    python src/build_teacher_student.py              # apply
    python src/build_teacher_student.py --dry-run    # preview stats only
"""

import ast
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARSANAD = ROOT / "src" / "arsanad_narrators.csv"
UNIFIED = ROOT / "app" / "data" / "narrator_unified.json"
DEDUP_LOG = ROOT / "src" / "dedup_logs" / "dedup_layer2.json"


def build_redirect():
    """Build absorbed_id -> primary_id redirect map from dedup log."""
    if not DEDUP_LOG.exists():
        return {}
    log = json.load(open(DEDUP_LOG, encoding='utf-8'))
    redirect = {}
    for entry in log:
        primary = int(entry['primary'])
        for absorbed in entry['absorbed']:
            redirect[int(absorbed['id'])] = primary
    return redirect


def resolve(arsanad_id, redirect, valid_ids):
    """Resolve an AR-Sanad ID to a valid profile ID."""
    pid = int(arsanad_id)
    if pid in redirect:
        pid = redirect[pid]
    return pid if pid in valid_ids else None


def main():
    dry_run = '--dry-run' in sys.argv

    print("Loading narrator database...")
    with open(UNIFIED, encoding='utf-8') as f:
        db = json.load(f)
    profiles = db['profiles']
    valid_ids = set(int(k) for k in profiles.keys())
    print(f"  {len(profiles):,} profiles")

    print("Loading AR-Sanad...")
    with open(ARSANAD, encoding='utf-8') as f:
        arsanad = list(csv.DictReader(f))
    print(f"  {len(arsanad):,} narrators")

    redirect = build_redirect()
    print(f"  {len(redirect)} dedup redirects loaded")

    # Parse all teacher-student links
    print("\nBuilding teacher-student network...")
    teachers_map = {}  # profile_id -> set of teacher profile_ids
    students_map = {}  # profile_id -> set of student profile_ids
    links_resolved = 0
    links_broken = 0

    for row in arsanad:
        narrator_id = resolve(int(row['id']), redirect, valid_ids)
        if narrator_id is None:
            continue

        # Parse narrated_from (teachers)
        try:
            from_ids = ast.literal_eval(row.get('narrated_from', '[]') or '[]')
        except (ValueError, SyntaxError):
            from_ids = []

        # Parse narrated_to (students)
        try:
            to_ids = ast.literal_eval(row.get('narrated_to', '[]') or '[]')
        except (ValueError, SyntaxError):
            to_ids = []

        teachers = set()
        for tid in from_ids:
            resolved = resolve(tid, redirect, valid_ids)
            if resolved is not None and resolved != narrator_id:
                teachers.add(resolved)
                links_resolved += 1
            else:
                links_broken += 1

        students = set()
        for sid in to_ids:
            resolved = resolve(sid, redirect, valid_ids)
            if resolved is not None and resolved != narrator_id:
                students.add(resolved)
                links_resolved += 1
            else:
                links_broken += 1

        if teachers:
            teachers_map[narrator_id] = teachers
        if students:
            students_map[narrator_id] = students

    # Stats
    with_teachers = len(teachers_map)
    with_students = len(students_map)
    total_teacher_links = sum(len(t) for t in teachers_map.values())
    total_student_links = sum(len(s) for s in students_map.values())

    print(f"\n  Narrators with teachers: {with_teachers:,}")
    print(f"  Narrators with students: {with_students:,}")
    print(f"  Teacher links: {total_teacher_links:,}")
    print(f"  Student links: {total_student_links:,}")
    print(f"  Links resolved: {links_resolved:,}")
    print(f"  Links broken (ID not found): {links_broken:,}")

    # Distribution
    teacher_counts = Counter(len(t) for t in teachers_map.values())
    student_counts = Counter(len(s) for s in students_map.values())
    print(f"\n  Teacher count distribution (top):")
    for n, c in sorted(teacher_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"    {n} teachers: {c} narrators")
    print(f"\n  Student count distribution (top):")
    for n, c in sorted(student_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"    {n} students: {c} narrators")

    # Most connected narrators
    print(f"\n  Most teachers (top 5):")
    for pid in sorted(teachers_map, key=lambda p: -len(teachers_map[p]))[:5]:
        p = profiles[str(pid)]
        print(f"    {p['full_name'][:45]}: {len(teachers_map[pid])} teachers")

    print(f"\n  Most students (top 5):")
    for pid in sorted(students_map, key=lambda p: -len(students_map[p]))[:5]:
        p = profiles[str(pid)]
        print(f"    {p['full_name'][:45]}: {len(students_map[pid])} students")

    if dry_run:
        print("\n[DRY RUN] No files written.")
        return

    # Enrich profiles
    print("\nEnriching profiles...")
    enriched = 0
    for pid_str, profile in profiles.items():
        pid = int(pid_str)
        t = teachers_map.get(pid, set())
        s = students_map.get(pid, set())
        if t or s:
            if t:
                profile['teachers'] = sorted(t)
            if s:
                profile['students'] = sorted(s)
            enriched += 1

    print(f"  Enriched {enriched:,} profiles with teacher/student links")

    # Write
    db['profiles'] = profiles
    print(f"  Writing {UNIFIED.name}...")
    with open(UNIFIED, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False)
    print(f"  -> {UNIFIED.stat().st_size:,} bytes")


if __name__ == '__main__':
    main()
