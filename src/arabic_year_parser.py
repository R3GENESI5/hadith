"""
arabic_year_parser.py
=====================
Parses Arabic word-form death years from classical biographical prose.

Converts phrases like:
  مات سنة ست وعشرين ومائة  -> 126
  توفي سنة تسع وأربعين ومئتين -> 249
  مات سنة خمس عشرة  -> 15
  توفي سنة ثلاثمائة -> 300

Usage:
    from arabic_year_parser import extract_death_year_word
    year = extract_death_year_word("مات سنة ست وثلاثين ومائة")
    # Returns: 136
"""

import re

# ── Arabic number words ──────────────────────────────────────────────

# Units (1-9) — masculine and feminine forms
UNITS = {
    'واحد': 1, 'واحدة': 1,
    'إحدى': 1, 'احدى': 1,
    'اثنين': 2, 'إثنين': 2, 'اثنتين': 2, 'إثنتين': 2,
    'اثنى': 2, 'إثنى': 2, 'اثنتى': 2,
    'ثلاث': 3, 'ثلاثة': 3,
    'أربع': 4, 'اربع': 4, 'أربعة': 4, 'اربعة': 4,
    'خمس': 5, 'خمسة': 5,
    'ست': 6, 'ستة': 6,
    'سبع': 7, 'سبعة': 7,
    'ثمان': 8, 'ثماني': 8, 'ثمانية': 8,
    'تسع': 9, 'تسعة': 9,
}

# Tens standalone (10, 20, ..., 90)
TENS = {
    'عشر': 10, 'عشرة': 10, 'عشرين': 20,
    'ثلاثين': 30, 'أربعين': 40, 'اربعين': 40,
    'خمسين': 50, 'ستين': 60, 'سبعين': 70,
    'ثمانين': 80, 'تسعين': 90,
}

# Hundreds
HUNDREDS = {
    'مائة': 100, 'مئة': 100,
    'مائتين': 200, 'مئتين': 200,
}

# Diacritics removal for matching
DIACRITICS_RE = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC'
    r'\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]'
)


def strip_diacritics(t):
    return DIACRITICS_RE.sub('', t)


def parse_arabic_number(phrase):
    """Parse an Arabic word-form number phrase into an integer.

    Handles:
      - Units: ست -> 6
      - Teens: خمس عشرة -> 15, ثماني عشرة -> 18
      - Compound: ست وعشرين -> 26
      - With hundreds: ست وعشرين ومائة -> 126
      - Compound hundreds: ثلاثمائة -> 300, ثلاثمئة -> 300
    """
    if not phrase:
        return None

    phrase = strip_diacritics(phrase.strip())
    # Remove leading/trailing non-number words
    # Stop at common non-number words
    stop_words = {
        'في', 'من', 'أو', 'او', 'بمكة', 'بالمدينة', 'بمصر', 'بالبصرة',
        'بالكوفة', 'بدمشق', 'ببغداد', 'وهو', 'وله', 'وقد', 'وكان',
        'وقيل', 'رحمه', 'خلافة', 'بين', 'على', 'قال',
    }

    words = phrase.split()
    number_words = []
    skip_next = False
    for w in words:
        if skip_next:
            skip_next = False
            continue

        # Strip leading و (conjunction)
        clean = w
        if clean.startswith('و') and len(clean) > 2 and clean[1:] not in ('هو', 'له', 'قد', 'كان', 'قيل'):
            clean = clean[1:]

        # Check if this is a number word or hundred compound
        is_number = (
            clean in UNITS or clean in TENS or clean in HUNDREDS
            or 'مائة' in clean or 'مئة' in clean
        )

        if is_number:
            number_words.append(clean)
        elif w in ('و',):
            continue  # skip standalone و
        elif clean in ('أو', 'او'):
            # "خمس أو ست وأربعين" — skip أو AND the next word (the alternative)
            skip_next = True
            continue
        elif clean in stop_words or w in stop_words:
            break
        elif number_words:
            # We had numbers and hit a non-number -- stop
            break
        # else: skip leading non-number words

    if not number_words:
        return None

    total = 0
    i = 0
    while i < len(number_words):
        w = number_words[i]

        # Check compound hundreds: ثلاثمائة, خمسمئة, etc.
        if 'مائة' in w or 'مئة' in w:
            prefix = w.replace('مائة', '').replace('مئة', '')
            if prefix in UNITS:
                total += UNITS[prefix] * 100
            elif prefix == '':
                total += 100
            else:
                total += 100  # fallback
            i += 1
            continue

        # Check if this is a unit followed by عشر/عشرة (teen)
        if w in UNITS and i + 1 < len(number_words) and number_words[i + 1] in ('عشر', 'عشرة'):
            total += UNITS[w] + 10  # e.g., خمس عشرة = 15
            i += 2
            continue

        # Standalone unit
        if w in UNITS:
            total += UNITS[w]
            i += 1
            continue

        # Tens
        if w in TENS:
            total += TENS[w]
            i += 1
            continue

        # Hundreds
        if w in HUNDREDS:
            total += HUNDREDS[w]
            i += 1
            continue

        i += 1

    return total if total > 0 else None


def extract_death_year_word(text):
    """Extract death year from Arabic prose, handling both numeric and word forms.

    Returns integer year or None.
    """
    clean = strip_diacritics(text)

    # Try numeric first: مات سنة 197
    m = re.search(r'(?:مات|توفي|توفى|قتل)\s+(?:في\s+)?سنة\s+(\d+)', clean)
    if m:
        return int(m.group(1))

    # Word form: مات سنة ست وعشرين ومائة
    m = re.search(
        r'(?:مات|توفي|توفى|قتل|وفاته)\s+(?:في\s+)?سنة\s+'
        r'([\u0600-\u06FF\s]+?)(?:\s*[.،]|\s+(?:وهو|وله|وقد|وكان|وقيل|رحمه|في خلافة|بين|على|قال|ودفن|وصلى|وغسل)|$)',
        clean
    )
    if m:
        phrase = m.group(1).strip()
        year = parse_arabic_number(phrase)
        if year and 1 <= year <= 1500:
            return year

    return None


# ── Tests ────────────────────────────────────────────────────────────

def test():
    cases = [
        ('مات سنة ست وثلاثين', 36),
        ('مات سنة اثنتين وثلاثين', 32),
        ('توفي سنة تسع عشرة', 19),
        ('مات سنة خمس عشرة', 15),
        ('مات سنة ثلاثين', 30),
        ('توفي سنة سبع وخمسين', 57),
        ('مات سنة خمس وأربعين', 45),
        ('مات سنة إحدى وستين', 61),
        ('مات سنة تسع ومئة', 109),
        ('توفي سنة خمس ومئة', 105),
        ('مات سنة أربع ومئة', 104),
        ('مات سنة سبع عشرة ومئة', 117),
        ('توفي سنة ثماني عشرة ومئة', 118),
        ('مات سنة أربع وأربعين ومئة', 144),
        ('توفي سنة تسع وثلاثين ومئة بالمدينة', 139),
        ('مات سنة ثلاثين ومئة', 130),
        ('مات سنة اثنتين وخمسين ومئة', 152),
        ('مات سنة ثلاث وخمسين ومئة', 153),
        ('مات سنة ثلاثمائة', 300),
        ('مات سنة 197', 197),
        ('مات سنة خمس أو ست وأربعين ومئة', 145),  # takes first number
    ]

    passed = 0
    failed = 0
    for text, expected in cases:
        result = extract_death_year_word(text)
        ok = result == expected
        if ok:
            passed += 1
        else:
            failed += 1
            print(f'  FAIL: "{text}" -> {result} (expected {expected})')

    print(f'\n  {passed}/{len(cases)} passed, {failed} failed')
    return failed == 0


if __name__ == '__main__':
    test()
