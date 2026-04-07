"""Add 4 new thematic families to families.json then rebuild bridge."""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QURAN_DATA = ROOT / 'quran' / 'data'

with open(QURAN_DATA / 'families.json', encoding='utf-8') as f:
    fam = json.load(f)

# 1. END OF TIMES
fam['end_of_times'] = {
    'name_ar': 'أشراط الساعة والأخروية',
    'meaning': 'Signs of the Hour, eschatology, resurrection, grave, trials before the Day of Judgment',
    'roots': [
        'فتن',  # fitnah — trials/tribulations (Kitab al-Fitan)
        'قوم',  # qiyama — rising/Yawm al-Qiyamah
        'بعث',  # ba'th — resurrection
        'حشر',  # hashr — grand gathering of mankind
        'نشر',  # nashr — resurrection/spreading of the dead
        'نفخ',  # nafkh — blowing the Trumpet (Israfil)
        'صور',  # sur — the Trumpet itself
        'قبر',  # qabr — grave (punishment/bliss of the grave)
        'موت',  # mawt — death
        'روح',  # ruh — soul (after death, souls in barzakh)
        'خسف',  # khasf — sinking into earth (major sign: army swallowed)
        'دخن',  # dukhan — smoke (one of 10 major signs)
        'زلزل', # zilzal — earthquakes (signs of the Hour)
        'خرج',  # khuruj — emergence (Dajjal, Mahdi, Yajuj/Majuj)
        'ظهر',  # zuhur — appearance (of Islam, of Dajjal, of Isa)
        'نذر',  # indhar — warnings before punishment
        'وقت',  # waqt — appointed times (the Hour has a fixed time)
        'برزخ', # barzakh — intermediate realm between death and resurrection
        'ضنك',  # dhank — straitened existence (punishment after death)
        'رقد',  # ruqad — sleep/slumber (death as sleep, Companions of Cave)
        'جمع',  # jam' — gathering (the Grand Assembly)
        'هدد',  # haddada — threats of destruction/ruin
        'فني',  # fana — perishing of all things
        'دخل',  # dukhul — entering (Paradise or Hellfire)
    ]
}

# 2. JIHAD
fam['jihad'] = {
    'name_ar': 'الجهاد والشهادة في سبيل الله',
    'meaning': 'Striving in the way of Allah, military expeditions, martyrdom, conquest, spoils of war, frontier guarding',
    'roots': [
        'جهد',  # jahd — striving/exerting oneself (the defining root)
        'شهد',  # shahid — martyr/witness (dying fi sabil Allah)
        'غزو',  # ghazwa — military expedition
        'غنم',  # ghanimah — spoils of war (rules of booty)
        'فتح',  # fath — conquest (Fath Makkah, futuhat)
        'حرب',  # harb — war/battle
        'نصر',  # nasr — divine victory
        'ربط',  # ribat — frontier guarding (ribat fi sabil Allah)
        'سلح',  # silah — weapons
        'فدي',  # fida — ransom/sacrifice (ransoming captives)
        'أسر',  # asr — captivity (prisoners of war rules)
        'قتل',  # qatl — fighting/killing in battle
        'رمي',  # ramy — archery (teach your children archery)
        'خيل',  # khayl — horses (cavalry, keeping horses for jihad)
        'سهم',  # sahm — arrow/share (in booty)
        'حصر',  # hisar — siege warfare
        'جند',  # jund — army/troops
        'عتد',  # i'dad — preparation/equipment (i'dad al-quwwa)
        'هزم',  # hazm — routing the enemy
        'غلب',  # ghalab — overcoming/prevailing
        'بأس',  # ba's — might/strength in battle
        'سبل',  # sabil — way (fi sabil Allah)
        'دفع',  # daf' — repelling/defending (dafi'u al-fasad)
    ]
}

# 3. STATECRAFT
fam['statecraft'] = {
    'name_ar': 'السياسة والحكم والخلافة',
    'meaning': 'Islamic governance, caliphate, shura, bay\'a, obedience to authority, justice of rulers, judiciary',
    'roots': [
        'ملك',  # mulk — sovereignty/kingship
        'حكم',  # hukm — governance/ruling/judgment
        'خلف',  # khilafa — succession, caliphate
        'أمر',  # amr — command/authority (uli al-amr)
        'ولي',  # wilaya — guardianship/authority (wali al-amr)
        'شور',  # shura — consultation (wa amruhum shura baynahum)
        'بيع',  # bay'a — pledge of allegiance
        'طوع',  # ta'a — obedience (to Allah, Messenger, and rulers)
        'عهد',  # ahd — covenant/treaty
        'سلط',  # sultan — authority/power
        'قضي',  # qada — judiciary (the qadi, judicial decisions)
        'عزل',  # azl — dismissal/removal from office
        'نصح',  # nasiha — sincere counsel to rulers
        'دبر',  # tadabur — administration/management
        'عدل',  # adl — justice (supreme duty of rulers)
        'ظلم',  # zulm — injustice/tyranny (ruling unjustly)
        'فسد',  # fasad — corruption in the land (rulers' accountability)
        'أمن',  # amn — security/safety (state's duty)
        'حدد',  # hadd — legal limits/punishments administered by state
        'وزر',  # wizr — burden of governance (vizier, wazir)
        'دول',  # dawla — rotation of power among peoples
        'نظم',  # nizam — order/system
        'سير',  # siyar — conduct of state (siyar = Islamic international law)
    ]
}

# 4. FAMILY LAW
fam['family_law'] = {
    'name_ar': 'الأحوال الشخصية والأسرة',
    'meaning': 'Marriage, divorce, inheritance, children, breastfeeding, mahr, maintenance — personal status law',
    'roots': [
        'نكح',  # nikah — marriage contract
        'طلق',  # talaq — divorce (talaq, khul', ila', zihar)
        'ورث',  # miras — inheritance
        'زوج',  # zawj — spouse/pair
        'ولد',  # walad — children/parenthood
        'رضع',  # rida'a — breastfeeding (creates mahram bonds)
        'نفق',  # nafaqa — financial maintenance
        'عشر',  # ishra — conjugal life/cohabitation
        'عقد',  # aqd — contract (marriage as binding contract)
        'صدق',  # sadaq — mahr/dowry
        'أهل',  # ahl — household/family
        'يتم',  # yatim — orphan (children's rights)
        'أيم',  # ayyim — widow/unmarried woman
        'ثيب',  # thayyib — previously married woman
        'بكر',  # bikr — virgin (consent in marriage)
        'خطب',  # khitba — proposal/betrothal
        'نسب',  # nasab — lineage/parentage
        'شرط',  # shart — conditions in marriage contract
        'فرق',  # firaq — separation/judicial dissolution
        'عضل',  # adl — wrongful prevention of marriage by guardian
        'حمل',  # haml — pregnancy (idda of pregnant woman)
        'عدد',  # idda — waiting period (after divorce/widowhood)
        'بعل',  # ba'l — husband (marital authority)
    ]
}

with open(QURAN_DATA / 'families.json', 'w', encoding='utf-8') as f:
    json.dump(fam, f, ensure_ascii=False, indent=1)

print(f'families.json updated: {len(fam)} total families')
new = ['end_of_times', 'jihad', 'statecraft', 'family_law']
for k in new:
    print(f'  {k}: {len(fam[k]["roots"])} roots — {fam[k]["name_ar"]}')
