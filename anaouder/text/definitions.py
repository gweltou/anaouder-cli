from typing import List
import re
from ..dicts import proper_nouns, nouns_f, nouns_m


LETTERS = "aâàbcçdeêéèëfghiïjklmnñoôpqrstuüùûvwxyzœ"
PUNCTUATION = '.?!,‚;:«»“”"()[]/…–—•'
OPENING_QUOTES = "«“"
CLOSING_QUOTES = "»”"
# CLOSING_PUNCT = {'»': '«', '”': '“', ')': '('}
# OPENING_PUNCT = CLOSING_PUNCT.values()
PUNCT_PAIRS = {'«': '»', '“': '”', '(': ')', '[': ']'}
OPENING_PUNCT = PUNCT_PAIRS.keys()
CLOSING_PUNCT = PUNCT_PAIRS.values()
VALID_CHARS = LETTERS + LETTERS.upper() + PUNCTUATION + "-'<> "


substitutions = {
    "+"     : ["mui"],
    "="     : ["kevatal da"],
    "&"     : ["ha", "hag"],
    "%"     : ["dre gant"],
    "1/2"   : ["hanter", "unan war daou"],
    "3/4"   : ["tri c'hard"],
    "eurvezh/sizhun" : ["eurvezh dre sizhun"],
    "km/h" : [],
    "c'hm" : ["c'hilometr", "c'hilometrad"],
}


# Regular words
re_word = re.compile(r"['’\-·" + LETTERS + r"]+", re.IGNORECASE)
re_extended_word = re.compile(r"['’\-·" + LETTERS + r"]+[23²³€$%]?", re.IGNORECASE)
common_word = re.compile(r"['’\·" + LETTERS + r"]+(-[" + LETTERS + r"]+)*", re.IGNORECASE)
match_word = lambda s: re_word.fullmatch(s)
is_word = lambda s: bool(match_word(s))

# Inclusive words (ex: arvester·ez)
# will always match as regular words as well
re_word_inclusive = re.compile(r"(['-" + LETTERS + r"]+)·([-" + LETTERS + r"]+)", re.IGNORECASE)
match_word_inclusive = lambda s: re_word_inclusive.fullmatch(s)
is_word_inclusive = lambda s: bool(match_word_inclusive(s))


# Nouns and proper nouns
def is_proper_noun(word: str) -> bool:
    if '-' in word:
        for sub in word.split('-'):
            if sub not in proper_nouns:
                return False
        return True
    else:
        return word in proper_nouns


def is_noun_f(word: str) -> bool:
    if len(word) < 2:
        return False
    
    word = word.lower()
    if word in nouns_f:
        return True
    for candidate in reverse_mutation(word):
        if candidate in nouns_f:
            return True
    return False


def is_noun_m(word: str) -> bool:
    if len(word) < 2:
        return False

    word = word.lower()
    if word in nouns_m:
        return True
    for candidate in reverse_mutation(word):
        if candidate in nouns_m:
            return True
    return False


def is_noun(word: str) -> bool:
    return is_noun_m(word) or is_noun_f(word)


# Acronyms
PATTERN_DOTTED_ACRONYM = re.compile(r"([A-Z]\.)+([A-Z])?")


SI_UNITS = {
    'g'     : ["gramm"],
    'kg'    : ["kilo", "kilogramm"],
    'µg'    : ["mikro gramm"],
    't'     : ["tonenn"],
    'l'     : ["litr", "litrad"],
    'cl'    : ["santilitr", "santilitrad"],
    'ml'    : ["mililitr", "mililitrad"],
    'cm'    : ["santimetr", "kantimetr"],
    'sm'    : ["santimetr"],
    'cm2'   : ["santimetr karrez", "kantimetr karrez"],
    'cm²'   : ["santimetr karrez", "kantimetr karrez"],
    'cm3'   : ["santimetr diñs", "kantimetr diñs"],
    'm'     : ["metr", "metrad"],
    'm2'    : ["metr karrez", "metrad karrez"],
    'm²'    : ["metr karrez", "metrad karrez"],
    'm3'    : ["metr diñs", "metrad diñs"],
    'm³'    : ["metr diñs", "metrad diñs"],
    'km'    : ["kilometr", "kilometrad"],
    "c'hm"  : ["c'hilometr", "c'hilometrad"],
    'km2'   : ["kilometr karrez", "kilometrad karrez"],
    'km²'   : ["kilometr karrez", "kilometrad karrez"],
    'km³'   : ["kilometr diñs", "kilometrad diñs"],
    'mn'    : ["munutenn"],
    '€'     : ['euro'],
    '$'     : ['dollar', 'dollar amerikan'],
    'k€'    : ["mil euro"],
    'M€'    : ["milion euro"],
    '%'     : ["dre gant"],
    '°C'    : ["derez celsius"],
    }

# A percentage or a number followed by a unit
# re_unit_number = re.compile(r"(\d+)([\w%€$']+)", re.IGNORECASE)
re_unit_number = re.compile(r"(\d{1,3}(?:\.\d\d\d)+|\d+)([\w%€$']+)", re.IGNORECASE)
match_unit_number = lambda s: re_unit_number.fullmatch(s)
def is_unit_number(s):
    match = match_unit_number(s)
    if not match: return False
    unit = match.group(2)
    return unit in SI_UNITS


# Time (hours and minutes)
re_time = re.compile(r"(\d+)(?:e|h|eur)(\d+)?")
match_time = lambda s: re_time.fullmatch(s)
def is_time(s):
    match = match_time(s)
    if not match: return False
    _, m = match.groups(default='00')
    return int(m) < 60


# Ordinals
ORDINALS = {
    "1añ"  : "kentañ",
    "2vet" : "eilvet",
    "3de"  : "trede",
    "3e"   : "trede",
    "3vet" : "teirvet",
    "4e"   : "pevare",
    "4re"  : "pevare",
    "4vet" : "pedervet",
    "9vet" : "navet"
}

re_ordinal = re.compile(r"(\d+)vet")
match_ordinal = lambda s: re_ordinal.fullmatch(s)
is_ordinal = lambda s: s in ORDINALS or bool(match_ordinal(s))


ROMAN_ORDINALS = {
    "Iañ"  : "kentañ",
    "IIvet": "eilvet",
    "IIIde": "trede",
    "IIIe" : "trede",
    "IIIvet": "teirvet",
    "IVe"  : "pevare",
    "IVvet": "pedervet",
    "IXvet": "navet"
}

re_roman_ordinal = re.compile(r"([XVI]+)vet")
match_roman_ordinal = lambda s: re_roman_ordinal.fullmatch(s)
is_roman_ordinal = lambda s: s in ROMAN_ORDINALS or bool(match_roman_ordinal(s))

re_roman_number = re.compile(r"([XVI]+)")
match_roman_number = lambda s: re_roman_number.fullmatch(s)
is_roman_number = lambda s: bool(match_roman_number(s))



def reverse_mutation(word: str) -> List[str]:
    """ returns the list of possible reverse-mutated candidates
        from a mutated (or not) word.
        Note that many candidates won't have meaning
    """
    first_letter = word[0].lower()
    is_cap = word[0].isupper()
    candidates = []

    if word.lower().startswith("c'h"):
        candidates.append('k' + word[3:])
        candidates.append('g' + word[3:])
    elif first_letter == 'w':
        candidates.append('g' + word[:])
    elif first_letter == 'z':
        candidates.append('t' + word[1:])
        candidates.append('d' + word[1:])
    elif first_letter == 'f':
        candidates.append('p' + word[1:])
    elif first_letter == 'k':
        candidates.append('g' + word[1:])
    elif first_letter == 't':
        candidates.append('d' + word[1:])
    elif first_letter == 'p':
        candidates.append('b' + word[1:])
    elif first_letter == 'g':
        candidates.append('k' + word[1:])
    elif first_letter == 'd':
        candidates.append('t' + word[1:])
    elif first_letter == 'b':
        candidates.append('p' + word[1:])
    elif first_letter == 'v':
        candidates.append('b' + word[1:])
        candidates.append('m' + word[1:])
    
    if is_cap:
        candidates = [ w[0].upper() + w[1:] for w in candidates]
    return candidates
