#! /usr/bin/env python3
# -*- coding: utf-8 -*-


# import random
import re
from typing import Iterator, List, Any

from .tokenizer import match_time
from .definitions import (
    SI_UNITS,
    ORDINALS, match_ordinal,
    ROMAN_ORDINALS, match_roman_ordinal,
    )
from .tokenizer import tokenize, detokenize, Token
from ..dicts import nouns_f, nouns_m



# MUTATIONS

def solve_mutation_number(number: int, noun: str) -> str:
    # Special rule for "bloaz"
    if noun in ("bloaz", "vloaz"):
        if number in (1, 3, 4, 5, 9, 1000, 1_000_000, 1_000_000_000):
            return "bloaz"
        elif number%10 in (1, 3, 4, 5, 9):
            return "bloaz"
        else:
            return "vloaz"
    else:
        return noun



def solve_mutation_article(article: str, noun: str) -> List[str]:
    """ ar, an, al, un, ur, ul
        Correct the article and change the noun's first letter
        according to mutation rules.

        Some homonyme nouns can be both male an female
        hence the returned list or results
        Ex: taol
    """

    results = []
    noun_first_letter = noun[0].lower()
    is_cap = noun[0].isupper()

    if noun_first_letter == 'l':
        article = article[:-1] + 'l'
    elif noun_first_letter in "adehinot":
        article = article[:-1] + 'n'
    else:
        article = article[:-1] + 'r'

    if noun == 'dor':
        # Special rule
        noun = 'n' + noun[1:]
        results.append(f"{article} {noun}")
    elif noun in nouns_m:
        if noun_first_letter == 'k':
            noun = "c'h" + noun[1:]

        if is_cap:
            noun = noun.capitalize()
        
        results.append(f"{article} {noun}")
    
    if noun in nouns_f:
        if noun_first_letter == 'k':
            noun = 'g' + noun[1:]
        elif noun_first_letter == 'p':
            noun = 'b' + noun[1:]
        elif noun_first_letter == 't':
            noun = 'd' + noun[1:]
        elif noun.lower().startswith('gw'):
            noun = 'w' + noun[2:]
        elif noun_first_letter == 'g':
            noun = "c'h" + noun[1:]
        elif noun_first_letter == 'b':
            noun = 'v' + noun[1:]
        elif noun_first_letter == 'm':
            noun = 'v' + noun[1:]
        
        if is_cap:
            noun = noun.capitalize()
        
        results.append(f"{article} {noun}")

    return results



def norm_number_noun(number: int, noun: str) -> str:
    """ (75, bloaz) -> "pemp bloaz ha tri-ugent"
        TODO:
            * diwall d'ar c'hemadurioù
    """

    noun = solve_mutation_number(number, noun)

    if number > 1000:
        thousands = (number//1000)*1000
        below_thousands = number - thousands
        if below_thousands == 0:
            return f"{num2txt(thousands)} {noun}"
        else:
            return f"{num2txt(thousands)} {norm_number_noun(below_thousands, noun)}"
    
    feminine = noun.lower() in nouns_f
    num_txt = num2txt(number, feminine)
    noun_first_letter = noun[0].lower()
    # is_cap = noun[0].isupper()
    if str(number).endswith('1'):
        if noun_first_letter == 'l':
            num_txt = num_txt.replace('unan', 'ul')
        elif noun_first_letter in "adehinot":
            num_txt = num_txt.replace('unan', 'un')
        else:
            num_txt = num_txt.replace('unan', 'ur')

    split_index = max( [num_txt.rfind(tok) for tok in (" ha ", " hag ", " warn-")] )
    if split_index == -1:
        return f"{num_txt} {noun}"
    else:
        return f"{num_txt[:split_index]} {noun}{num_txt[split_index:]}"



num_units = ["", "unan", "daou", "tri", "pevar", "pemp", "c'hwec'h", "seizh", "eizh", "nav",
             "dek", "unnek", "daouzek", "trizek", "pevarzek", "pemzek", "c'hwezek", "seitek", "triwec'h", "naontek", "ugent"]
num_units_f = ["", "unan", "div", "teir", "peder"]
num_tens = ["", "", "ugent", "tregont", "daou-ugent", "hanter-kant", "tri-ugent", "dek ha tri-ugent", "pevar-ugent", "dek ha pevar-ugent"]


def num2txt(num: int, feminine=False) -> str:
    if num == 0:
        return "mann"
        
    if feminine and num < 5:
        return num_units_f[num]

    if num <= 20:
        return num_units[num]

    if num < 100:
        t, u = divmod(num, 10)
        unit = num_units_f[u] if feminine and u in (2, 3, 4) else num_units[u]
        if u == 0:
            return num_tens[t]
        if t == 2:
            return unit + " warn-" + num_tens[t]
        if t == 5:
            return unit + " hag " + num_tens[t]
        if t in (7, 9):
            t -= 1; u += 10
            unit = num_units_f[u] if feminine and u in (2, 3, 4) else num_units[u]
        return unit + " ha " + num_tens[t]

    if num < 1000:
        h, u = divmod(num, 100)
        if u == 0: unit_str = ""
        else: unit_str = " " + num2txt(u, feminine=feminine)

        if h == 1:
            return "kant" + unit_str
        if h in (2, 3, 4, 9):
            return num_units[h] + " c'hant" + unit_str
        return num_units[h] + " kant" + unit_str

    if num < 1_000_000:
        m, u = divmod(num, 1_000)
        if u == 0: unit_str = ""
        else: unit_str = " " + num2txt(u)
        
        if m == 1:
            return "mil" + unit_str
        if m == 2:
            return num2txt(m) + " vil" + unit_str
        return num2txt(m) + " mil" + unit_str
    
    if num < 1_000_000_000:
        # Millions
        m, u = divmod(num, 1_000_000)
        if u == 0: unit_str = ""
        else: unit_str = " " + num2txt(u)

        if m == 1:
            return "ur milion" + unit_str
        if m == 2:
            return num2txt(m) + " vilion" + unit_str
        return num2txt(m) + " milion" + unit_str
    
    else:
        # Billions
        mrd, u = divmod(num, 1_000_000_000)
        if u == 0: unit_str = ""
        else: unit_str = " " + num2txt(u)

        if mrd == 1:
            return "ur miliard" + unit_str
        if mrd == 2:
            return num2txt(mrd) + " viliard" + unit_str
        return num2txt(mrd) + " miliard" + unit_str 


# Time (hours and minutes)

minutes = {
    15 : "ha kard",
    30 : "hanter",
}

def norm_time(s: str) -> List[str]:
    h, mn = map(int, match_time(s).groups(default=0))
    h_hyp = []
    if h == 0: h_hyp.extend(["hanternoz", "kreiznoz"])
    elif h == 12: h_hyp.append("kreisteiz")
    elif h > 12: h_hyp.append(num2txt(h-12, feminine=True) + " eur")
    else: h_hyp.append(num2txt(h, feminine=True) + " eur")
    
    mn_hyp = []
    if mn != 0:
        if mn in minutes: mn_hyp.append(minutes[mn])
        # if mn >= 50: mn_hyp.append(f"nemet {num2txt(60-mn)}")
        mn_hyp.append(num2txt(mn))

    results = []

    if mn > 30:
        next_hour = norm_time(str((h+1)%12) + 'e')
        if mn == 40 or mn > 50:
            for nh in next_hour:
                results.append(nh + f" nemet {num2txt(60-mn)}")
        elif mn == 45:
            for nh in next_hour:
                results.append(nh + f" nemet kard")

    for h in h_hyp:
        if mn_hyp:
            for mn in mn_hyp:
                results.append(f"{h} {mn}")
        else:
            results.append(h)
    
    # return sorted(results, key=len)
    return results


# Percentage
# norm_percent = lambda s: norm_number_noun(int(match_percent(s).group(1)), "dregant")


# Ordinals

norm_ordinal = lambda s: ORDINALS[s] if s in ORDINALS else num2txt(int(match_ordinal(s).group(1))) + "vet"


roman2br = {
    'I'    : "unan",
    "II"   : "daou",
    "III"  : "tri",
    "IIII" : "pevar",
    "IV"   : "pevar",
    "V"    : "pemp",
    "VI"   : "c'hwec'h",
    "VII"  : "seizh",
    "VIII" : "eizh",
    "IX"   : "nav",
    "X"    : "dek",
    "XI"   : "unnek",
    "XII"  : "daouzek",
    "XIII" : "trizek",
    "XIV"  : "pevarzek",
    "XV"   : "pempzek",
    "XVI"  : "c'hwezek",
    "XVII" : "seitek",
    "XVIII": "triwec'h",
    "XIX"  : "naontek",
    "IXX"  : "naontek",
    "XX"   : "ugent",
    "XXI"  : "un warn-ugent",
    "XXII" : "daou warn-ugent",
    "XXIII": "tri warn-ugent",
    "XXIV" : "pevar warn-ugent",
    "XXV"  : "pemp warn-ugent",
    "XXVI" : "c'hwec'h warn-ugent",
    "XXVII": "seizh warn-ugent",
    "XXVIII": "eizh warn-ugent",
    "XXIX" : "nav warn-ugent",
    "XXX"  : "tregont",
    "XXXI" : "un ha tregont",
    "XXXII": "daou ha tregont",
    "XXXIII": "tri ha tregont",
    "XXXIV": "pevar ha tregont",
    "XXXV" : "pemp ha tregont"
}

norm_roman_ordinal = lambda s: ROMAN_ORDINALS[s] if s in ROMAN_ORDINALS else roman2br[match_roman_ordinal(s).group(1)] + "vet"



def normalize_sentence(sentence: str,
                       autocorrect=False,
                       norm_punct=False,
                       norm_case=False,
                       capitalize=False) -> str:
    """ 
        Normalize a single sentence.
        return: list of all possible normalization for the sentence

        Parameters
        ----------
            autocorrect: bool
                Substitutes words according to `corrected_tokens.tsv` dictionary
            
            norm_punct: bool
                Normalize punctuation
            
            norm_case: bool
                Lowerize any word that shouldn't be capitalized
            
            capitalize: bool
                Capitalize the first word of each grammatical sentence
    """

    propositions = []
    result = ""
    return detokenize(
            normalize(
                tokenize(sentence,
                         autocorrect=autocorrect,
                         norm_punct=norm_punct),
                norm_case=norm_case),
            normalize=True,
            capitalize=capitalize)



def normalize(token_stream: Iterator[Token], **options: Any) -> Iterator[Token]:
    """ 
        Apply different kind of normalization to a stream of tokens

        Options:
            * norm_case: lowerize any word that shouldn't be capitalized
        

        Bugs: the ordinal '3e' will be interpreted as a TIME token
    """

    norm_case = options.pop('norm_case', False)


    for tok in token_stream:
        if tok.kind == Token.PROPER_NOUN: tok.norm.append(tok.data)
        elif tok.kind == Token.WORD and norm_case:
            tok.norm.append(tok.data.lower())
        elif tok.kind == Token.NUMBER:
            tok.norm.append(num2txt(int(tok.data)))
        elif tok.kind == Token.ROMAN_NUMBER: tok.norm.append(roman2br[tok.data])
        elif tok.kind == Token.TIME: tok.norm.extend(norm_time(tok.data))
        elif tok.kind == Token.ORDINAL:
            tok.norm.append(norm_ordinal(tok.data))
        elif tok.kind == Token.ROMAN_ORDINAL: tok.norm.append(norm_roman_ordinal(tok.data))
        elif tok.kind == Token.QUANTITY:
            if tok.unit == '%':
                tok.norm.append(num2txt(int(tok.number)) + " dre gant")
            else:
                noun = tok.unit if tok.unit not in SI_UNITS else SI_UNITS[tok.unit][0]
                tok.norm.append(norm_number_noun(int(tok.number), noun))
        elif tok.kind == Token.UNIT:
            tok.norm.append(SI_UNITS[tok.data][0])

        yield tok