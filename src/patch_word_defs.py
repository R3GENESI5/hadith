"""
patch_word_defs.py — Fix critical root assignment gaps in word_defs_v2.json
============================================================================

Issues addressed:
  1. WRONG ROOT:  فتن forms (فتنه, فتن, افتتن, تفتن) mapped to فوت instead of فتن
  2. MISSING:     يوم (day) forms — all absent from word_defs_v2 (6935 occurrences)
  3. MISSING:     أمر (command) forms — all absent (2925 hadiths affected)
  4. MISSING:     ولي (guardian) forms — all absent (1755+ occurrences)
  5. MISSING:     أرض (earth) forms — all absent (1777 occurrences)
  6. MISSING:     وقي/تقوى (piety) forms — all absent
  7. ALIAS MAP:   Add أمن → ومن (CAMeL uses ومن for belief/faith root)

Run: python src/patch_word_defs.py
Then rebuild: python src/enrich_data.py --step concordance
Then rebuild: python src/build_bridge.py
"""

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
DATA = ROOT / 'app' / 'data'
SRC  = ROOT / 'src'

def load(p): return json.load(open(p, encoding='utf-8'))
def save(p, d, indent=None):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=indent,
                  separators=None if indent else (',', ':'))
    print(f'  Saved {Path(p).name} ({Path(p).stat().st_size // 1024} KB)')

print('Loading...')
wd    = load(DATA / 'word_defs_v2.json')
alias = load(SRC  / 'root_alias_map.json')
conc  = load(DATA / 'concordance.json')

patched = dict(wd)
stats = defaultdict(int)

# ─── 1. FIX WRONG ROOT: فتن forms assigned to فوت ────────────────────────────
# These words are from root فتن (trial/temptation/fitnah), not فوت (to miss/lose)
FITNAH_WRONG = {
    'فتنه':   'فتن',   # fitna-hu (he tempted him / fitnah)
    'فتن':    'فتن',   # fitan (plural of fitnah) / root form
    'افتتن':  'فتن',   # iftatan (was tempted/tried) — Form VIII
    'تفتن':   'فتن',   # taftinu (you tempt/try) — Form II/V
    'يفتن':   'فتن',   # yaftinu (he tempts)
    'فتنتم':  'فتن',   # fatantum (you caused fitnah)
    'فتنتني': 'فتن',   # you tempted me
}

print('\n── Fix 1: Correct wrong root فوت → فتن ──')
for word, correct_root in FITNAH_WRONG.items():
    if word in patched and isinstance(patched[word], dict):
        old_root = patched[word].get('r', '?')
        if old_root == 'فوت':
            patched[word]['r'] = correct_root
            patched[word]['g'] = 'The root فتن (fitnah) means trial, temptation, civil strife, or persecution.'[:120]
            stats['fitnah_fixed'] += 1
            print(f'  Fixed: {word:15s}  {old_root} → {correct_root}')

# ─── 2. ADD MISSING يوم (day) FORMS ─────────────────────────────────────────
# Root يوم (yawm) — fundamental eschatological root (Yawm al-Qiyamah)
YAWM_FORMS = {
    'يوم':      'The word يوم (yawm) means a day. Yawm al-Qiyama = Day of Resurrection.',
    'يوما':     'يوماً — accusative/adverbial form of day; "one day" or "a (certain) day".',
    'يومئذ':    'يومئذٍ — on that day (Yawm al-Qiyama context or historical event).',
    'يومين':    'يومين — two days (dual form of يوم).',
    'يومه':     'يومه — his day; often refers to the Day of Judgment for a person.',
    'يومها':    'يومها — her day.',
    'يومهم':    'يومهم — their day; the Day of Resurrection for them.',
    'يومكم':    'يومكم — your day (plural); "this day of yours" (Last Sermon context).',
    'يومي':     'يومي — my day; or daily.',
    'يومك':     'يومك — your day.',
    'يومنا':    'يومنا — our day.',
    'يومان':    'يومان — two days (dual nominative).',
    'اليوم':    'اليوم (al-yawm) — today; or specifically the Day of Resurrection.',
    'يومئ':     'يومئ — abbreviated form of يومئذ used in some hadith transmissions.',
}

ROOT_YAWM = 'يوم'
GLOSS_YAWM = 'The root يوم (yawm) means day. Central to Islamic eschatology: Yawm al-Qiyama (Day of Resurrection), Yawm al-Din (Day of Judgment).'

print('\n── Fix 2: Add missing يوم (day) forms ──')
added_yawm = 0
for word, specific_gloss in YAWM_FORMS.items():
    if word not in patched:
        freq = len(conc.get(word, []))  # existing conc count if any
        patched[word] = {
            'r':   ROOT_YAWM,
            'g':   specific_gloss[:120],
            'd':   GLOSS_YAWM[:300],
            'n':   freq,
            'lem': 'يوم',
            'pos': 'noun',
            '_patched': True,
        }
        added_yawm += 1
print(f'  Added {added_yawm} يوم forms')

# ─── 3. ADD MISSING أمر (command/authority) FORMS ────────────────────────────
# Root أمر (amr) — command, authority, matter; basis of ولي الأمر, أمير
# Note: امرأة (woman) is root مرأ — do NOT include امراه/امراته/امراتي here
AMR_FORMS = {
    'امر':       'أمر — command, matter, affair; the verb "to command" or noun "the command".',
    'يامر':      'يأمر — he commands; from root أمر (amara: to command).',
    'فامر':      'فأمر — so he commanded; narrative form in hadith isnads and matn.',
    'الامر':     'الأمر — the command/matter/authority; core concept in Quranic governance.',
    'امره':      'أمره — his command/matter; or "he commanded him".',
    'وامر':      'وأمر — and he commanded.',
    'امرنا':     'أمرنا — he commanded us; or "our matter/affair".',
    'امركم':     'أمركم — he commanded you (pl.); or "your matter".',
    'امرهم':     'أمرهم — he commanded them; or "their matter/affair".',
    'امرها':     'أمرها — he commanded her; or "her matter".',
    'امري':      'أمري — my matter/command; or "he commanded me".',
    'امرك':      'أمرك — your (sg.) command/matter.',
    'يامرنا':    'يأمرنا — he commands us.',
    'يامرهم':    'يأمرهم — he commands them.',
    'يامرون':    'يأمرون — they command.',
    'فامره':     'فأمره — so he commanded him.',
    'فامرهم':    'فأمرهم — so he commanded them.',
    'بامر':      'بأمر — by the command of; "bi-amr Allah" = by Allah\'s command.',
    'لامر':      'لأمر — for a command/matter; "la-amrin" = for a (great) matter.',
    'والامر':    'والأمر — and the command/matter.',
    'امرا':      'أمراً — a matter/command (accusative); "amran min al-amr" = a matter.',
    'الامور':    'الأمور — matters/affairs (plural of أمر); "akhaff al-umur" = easiest matters.',
    'امور':      'أمور — matters/affairs (plural of أمر).',
    'امرائه':    'أمرائه — his commanders (plural of أمير).',
    'امراء':     'أمراء — commanders, emirs (plural of أمير); rulers appointed over peoples.',
    'امير':      'أمير — commander, emir; ruler appointed by the caliph over a region or army.',
    'الامير':    'الأمير — the commander/emir (definite form).',
    'اميرا':     'أميراً — a commander/emir (accusative).',
    'اوامر':     'أوامر — commands, orders (plural of أمر); divine commandments.',
    'مامور':     'مأمور — the one commanded; an official/functionary.',
    'يستامر':    'يستأمر — he consults (asks for command from); Form X of أمر.',
}

ROOT_AMR = 'أمر'
GLOSS_AMR = 'The root أمر (amr) means to command, order, or be in authority. Foundation of Islamic governance: uli al-amr (those in authority), amir (commander), amr (divine command).'

print('\n── Fix 3: Add missing أمر (command) forms ──')
added_amr = 0
for word, specific_gloss in AMR_FORMS.items():
    if word not in patched:
        patched[word] = {
            'r':   ROOT_AMR,
            'g':   specific_gloss[:120],
            'd':   GLOSS_AMR[:300],
            'n':   0,
            'lem': 'امر',
            'pos': 'noun/verb',
            '_patched': True,
        }
        added_amr += 1
print(f'  Added {added_amr} أمر command forms')

# ─── 4. ADD MISSING ولي (guardian/authority) FORMS ──────────────────────────
# Root ولي (wly) — guardian, master, governor; wilaya (authority/proximity)
WALI_FORMS = {
    'ولي':       'وَلِيّ — guardian, master, helper; Allah is al-Wali (the Protecting Friend).',
    'الولي':     'الوَلِيّ — the guardian/protector; one of Allah\'s names.',
    'وليه':      'وَليُّه — his guardian/master; the wali of the orphan or bride.',
    'وليها':     'وَليُّها — her guardian; the wali of the bride in marriage contract.',
    'والي':      'وَالِي — governor/ruler; one appointed over a province (ولاة الأمور).',
    'الوالي':    'الوَالِي — the governor; the appointed ruler of a province.',
    'ولاه':      'وَلَّاه — he appointed him (as governor); he entrusted him with authority.',
    'اولياء':    'أولياء — guardians, allies, protectors (plural of وَلِيّ).',
    'الاولياء':  'الأولياء — the guardians/allies/saints.',
    'مولي':      'مَوْلَى — master, freed slave, ally; term of deep loyalty in Arab tribal context.',
    'المولي':    'المَوْلَى — the master/guardian; refers to Allah as Mawla.',
    'مولاي':     'مَوْلَايَ — my master/guardian.',
    'مولاه':     'مَوْلَاه — his master/guardian.',
    'مولاهم':    'مَوْلَاهم — their master.',
    'موالي':     'مَوَالِي — freed slaves/clients; those bound by wala\' bond.',
    'المولاه':   'المَوْلَاة — the female freedwoman/ally.',
    'تولي':      'تَوَلَّى — he took charge of; he turned away; Form V.',
    'يتولي':     'يَتَوَلَّى — he governs/takes charge of; Form V.',
    'تولاه':     'تَوَلَّاه — he took charge of him/it.',
    'الولاه':    'الوُلَاة — the governors (plural of وَالٍ); those entrusted with authority.',
    'الولايه':   'الوِلَايَة — guardianship, authority, jurisdiction.',
    'ولايه':     'وِلَايَة — guardianship, authority, governorship.',
    'اولي':      'أُولِي — those who possess (followed by noun: أولي الأمر = those in authority).',
    'اولو':      'أُولُو — those who have; أولو الأمر = those in authority (Quran 4:59).',
}

ROOT_WALI = 'ولي'
GLOSS_WALI = 'The root ولي (wly) means to be near, to take charge of, to govern. It underlies wali (guardian/friend), mawla (master/freed slave), wilaya (authority), and wali al-amr (ruler).'

print('\n── Fix 4: Add missing ولي (guardian) forms ──')
added_wali = 0
for word, specific_gloss in WALI_FORMS.items():
    if word not in patched:
        patched[word] = {
            'r':   ROOT_WALI,
            'g':   specific_gloss[:120],
            'd':   GLOSS_WALI[:300],
            'n':   0,
            'lem': 'ولي',
            'pos': 'noun/verb',
            '_patched': True,
        }
        added_wali += 1
print(f'  Added {added_wali} ولي forms')

# ─── 5. ADD MISSING أرض (earth) FORMS ───────────────────────────────────────
# Root أرض (ard) — earth, land, ground; "وارث الأرض" and eschatological contexts
ARTH_FORMS = {
    'ارض':       'أَرْض — earth, land, ground; "al-ard" is a core Quranic concept.',
    'الارض':     'الأَرْض — the Earth; "وَوَرِثَ الأَرْض" = Allah shall inherit the earth.',
    'والارض':    'وَالأَرْض — and the Earth; as in "السَّمَاوَات وَالأَرْض".',
    'بالارض':    'بِالأَرْض — on/in the earth.',
    'بارض':      'بِأَرْض — in a land/earth.',
    'ارضا':      'أَرْضاً — a land (accusative/indefinite); "some land" or "an earth".',
    'ارضه':      'أَرْضُه — his land/earth; his territory.',
    'ارضي':      'أَرْضِي — my land; or أَرْضِيَّة (earthly/terrestrial).',
    'ارضين':     'أَرَضِين — lands/earths; the seven earths in Islamic cosmology.',
    'والارضين':  'وَالأَرَضِين — and the (seven) earths.',
    'ارضنا':     'أَرْضُنَا — our land.',
    'للارض':     'لِلأَرْض — for/to the earth.',
    'وارض':      'وَأَرْض — and (a) land.',
}

ROOT_ARTH = 'أرض'
GLOSS_ARTH = 'The root أرض (ard) means earth, ground, or land. Essential in eschatological hadiths (earth swallowing armies as a sign of the Hour) and in zakah/property law.'

print('\n── Fix 5: Add missing أرض (earth) forms ──')
added_arth = 0
for word, specific_gloss in ARTH_FORMS.items():
    if word not in patched:
        patched[word] = {
            'r':   ROOT_ARTH,
            'g':   specific_gloss[:120],
            'd':   GLOSS_ARTH[:300],
            'n':   0,
            'lem': 'ارض',
            'pos': 'noun',
            '_patched': True,
        }
        added_arth += 1
print(f'  Added {added_arth} أرض forms')

# ─── 6. ADD MISSING وقي/تقوى (piety) FORMS ─────────────────────────────────
# Root وقي (wqy) — to protect, guard; taqwa = God-consciousness (most common Islamic virtue)
WAQY_FORMS = {
    'تقوي':      'تَقْوَى — God-consciousness, piety; the highest virtue in Islamic ethics.',
    'التقوي':    'التَّقْوَى — piety/God-consciousness (definite form); إِنَّ أَكْرَمَكُمْ عند الله أَتْقَاكُمْ.',
    'بتقوي':     'بِتَقْوَى — with piety/God-consciousness.',
    'والتقوي':   'وَالتَّقْوَى — and piety/God-consciousness.',
    'اتقوا':     'اتَّقُوا — fear/be conscious of Allah! (imperative plural); Form VIII.',
    'واتقوا':    'وَاتَّقُوا — and fear/be conscious of Allah!',
    'فاتقوا':    'فَاتَّقُوا — so fear/be conscious of Allah!',
    'اتق':       'اتَّقِ — fear/be conscious of (Allah)! (imperative sg.)',
    'يتقي':      'يَتَّقِي — he is conscious of Allah; he fears (Form VIII).',
    'يتق':       'يَتَّقِ — he fears/is conscious of (short form of يَتَّقِي).',
    'فليتق':     'فَلْيَتَّقِ — let him fear/be conscious of Allah.',
    'يتقون':     'يَتَّقُون — they are God-conscious.',
    'المتقين':   'الْمُتَّقِين — the God-conscious, the pious (accusative/genitive plural).',
    'متقين':     'مُتَّقِين — the God-conscious/pious (without article).',
    'للمتقين':   'لِلْمُتَّقِين — for the God-conscious/pious.',
    'متقبله':    'مُتَقَبِّلَة — accepted (Form V: تَقَبَّلَ = to accept).',
    'اتقاكم':    'أَتْقَاكُم — the most God-conscious among you (elative).',
    'اتقيتم':    'اتَّقَيْتُم — you feared/were conscious of Allah.',
    'اتقي':      'اتَّقِي — fear Allah! (imperative fem.sg.); or يَتَّقِي abbreviated.',
}

ROOT_WAQY = 'وقي'
GLOSS_WAQY = 'The root وقي (wqy) means to protect/guard. From it comes taqwa (God-consciousness/piety), the supreme virtue in Islam. "Innama al-amalu bi-l-niyyat" — deeds by intentions; taqwa by sincerity.'

print('\n── Fix 6: Add missing وقي/تقوى (piety) forms ──')
added_waqy = 0
for word, specific_gloss in WAQY_FORMS.items():
    if word not in patched:
        patched[word] = {
            'r':   ROOT_WAQY,
            'g':   specific_gloss[:120],
            'd':   GLOSS_WAQY[:300],
            'n':   0,
            'lem': 'تقوي',
            'pos': 'noun/verb',
            '_patched': True,
        }
        added_waqy += 1
print(f'  Added {added_waqy} وقي/تقوى forms')

# ─── 7. UPDATE ALIAS MAP: أمن → ومن ─────────────────────────────────────────
# CAMeL Tools uses root ومن for faith/belief words (iman, aman, amine)
# Quran roots_index uses أمن → we add أمن: ومن so bridge finds these words
print('\n── Fix 7: Update alias map ──')
new_aliases = {
    'أمن': 'ومن',   # iman/amana — CAMeL canonical form is ومن
    'أمر': 'أمر',   # we added أمر entries directly, no alias needed
}
alias_updated = 0
for qr_root, wd_root in new_aliases.items():
    if qr_root not in alias:
        alias[qr_root] = wd_root
        alias_updated += 1
        print(f'  Added alias: {qr_root} → {wd_root}')
    elif alias[qr_root] != wd_root:
        print(f'  Skipped {qr_root}: already maps to {alias[qr_root]}')

# ─── Summary ─────────────────────────────────────────────────────────────────
total_added = added_yawm + added_amr + added_wali + added_arth + added_waqy
print(f'\n=== PATCH SUMMARY ===')
print(f'  فتن root fixes:   {stats["fitnah_fixed"]}')
print(f'  يوم forms added:  {added_yawm}')
print(f'  أمر forms added:  {added_amr}')
print(f'  ولي forms added:  {added_wali}')
print(f'  أرض forms added:  {added_arth}')
print(f'  وقي forms added:  {added_waqy}')
print(f'  Total new entries: {total_added}')
print(f'  Alias map updated: {alias_updated} new entries')
print(f'  word_defs_v2: {len(wd):,} → {len(patched):,} entries')

print('\nSaving...')
save(DATA / 'word_defs_v2.json', patched)
save(SRC  / 'root_alias_map.json', alias, indent=2)

# ─── Verification ────────────────────────────────────────────────────────────
print('\n── Verification: roots now covered ──')
new_wd = patched
root_to_count = {}
for w, info in new_wd.items():
    if isinstance(info, dict) and 'r' in info:
        r = info['r']
        root_to_count[r] = root_to_count.get(r, 0) + 1

for root in ['يوم', 'أمر', 'ولي', 'أرض', 'وقي', 'فتن', 'ومن']:
    cnt = root_to_count.get(root, 0)
    print(f'  Root {root}: {cnt} words in word_defs_v2')

print('\n✓ Done. Next steps:')
print('  1. python src/enrich_data.py --step concordance   (rebuild with cap=2000)')
print('  2. python src/build_bridge.py                     (rebuild bridge)')
