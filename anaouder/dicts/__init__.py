"""
Load various dictionaries from local resources

The option should be given to load user dictionaries as well, stored in a system folder
"""

import sys
# import os
# import platform
import importlib.resources


# dict_root = importlib.resources.files("anaouder") / "dicts"

# print(f"loading dicts in {dict_root}", file=sys.stderr)


# Proper nouns dictionary
# with phonemes when name has a foreign or particular pronunciations

def load_proper_nouns():
    proper_nouns = dict()
    proper_nouns_files = [
        "proper_nouns_phon.tsv",
        "places.tsv",
        # "countries.tsv",
        "last_names.tsv",
        "first_names.tsv",
    ]

    # print(f"Loading proper nouns dictionaries", file=sys.stderr)
    
    for file in proper_nouns_files:
        try:
            # Use importlib.resources to access files within the package
            with importlib.resources.files("anaouder.dicts").joinpath(file).open('r', encoding='utf-8') as f:
                for l in f.readlines():
                    l = l.strip()
                    if l.startswith('#') or not l: continue
                    w, *pron = l.split(maxsplit=1)
                    pron = pron or []
                    
                    if w in proper_nouns and pron:
                        if pron[0] not in proper_nouns[w]: # Avoid duplicate entries, which Kaldi hates
                            proper_nouns[w].append(pron[0])
                    else:
                        proper_nouns[w] = pron
        except FileNotFoundError:
            print(f"Missing dictionary file {file}", file=sys.stderr)
            continue
    
    return proper_nouns

proper_nouns = load_proper_nouns()



# Nouns dictionary
# Things that you can count

def load_nouns_f():
    nouns_f = set()
    filepath = "noun_f.tsv"

    try:
        with importlib.resources.files("anaouder.dicts").joinpath(filepath).open('r', encoding='utf-8') as f:
            
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                nouns_f.add(l)
        
        return nouns_f
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)

nouns_f = load_nouns_f()



def load_nouns_m():
    nouns_m = set()
    filepath = "noun_m.tsv"

    try:
        with importlib.resources.files("anaouder.dicts").joinpath("noun_m.tsv").open('r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                nouns_m.add(l)
        
        return nouns_m
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)

nouns_m = load_nouns_m()



# Acronyms dictionary

def load_acronyms():
    """
    Acronyms are stored in UPPERCASE in dictionary
    Values are lists of strings for all possible pronunciation of an acronym
    """
    acronyms = dict()
    filepath = "acronyms.tsv"

    # for l in "BCDFGHIJKLMPQRSTUVWXZ":
    #     acronyms[l] = [acr2f[l]]
    
    try:
        with importlib.resources.files("anaouder.dicts").joinpath(filepath).open('r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                acr, pron = l.split(maxsplit=1)
                if acr in acronyms:
                    acronyms[acr].append(pron)
                else:
                    acronyms[acr] = [pron]
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)
    
    return acronyms

acronyms = load_acronyms()



# Abbreviations

def load_abbreviations():
    abbreviations = dict()
    filepath = "abbreviations.tsv"

    try:
        with importlib.resources.files("anaouder.dicts").joinpath(filepath).open('r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                k, v = l.split('\t')
                # v = v.split()
                abbreviations[k] = v
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)
    
    return abbreviations

abbreviations = load_abbreviations()


# Interjections

def load_interjections():
    """
    Acronyms are stored in UPPERCASE in dictionary
    Values are lists of strings for all possible pronunciation of an acronym
    """
    interjections = dict()
    filepath = "interjections.tsv"
    
    try:
        with importlib.resources.files("anaouder.dicts").joinpath(filepath).open('r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                interj, *pron = l.split(maxsplit=1)
                pron = pron if pron else []

                if interj in interjections and pron:
                    interjections[interj].append(pron)
                else:
                    interjections[interj] = pron
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)

    return interjections

interjections = load_interjections()


# Common word mistakes

def load_corrected_tokens():
    corrected_tokens = dict()
    filepath = "corrected_tokens.tsv"

    try:
        with importlib.resources.files("anaouder.dicts").joinpath(filepath).open('r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                k, v = l.split('\t')
                v = v.split()
                corrected_tokens[k] = v
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)
    
    return corrected_tokens

corrected_tokens = load_corrected_tokens()


# Standardization tokens

def load_standard_tokens():
    standard_tokens = dict()
    filepath = "standard_tokens.tsv"

    try:
        with importlib.resources.files("anaouder.dicts").joinpath(filepath).open('r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if l.startswith('#') or not l: continue
                k, v = l.split('\t')
                v = v.split()
                standard_tokens[k] = v
    except FileNotFoundError:
        print(f"Missing dictionary file {filepath}", file=sys.stderr)
    
    return standard_tokens

standard_tokens = load_standard_tokens()
