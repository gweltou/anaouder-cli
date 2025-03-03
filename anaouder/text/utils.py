from typing import List, Iterator, Any, Tuple
import re
from .definitions import LETTERS, PUNCTUATION



def strip_punct(word: str) -> str:
    """ Strip punctuation left and right of a word """

    while word and word[0] in PUNCTUATION:
        word = word[1:]
    while word and word[-1] in PUNCTUATION:
        word = word[:-1]
    return word



def filter_out_chars(text: str, chars: str) -> str:
    """ Remove given characters from a string """

    filtered_text = ""
    for l in text:
        if not l in chars: filtered_text += l
    return filtered_text



def filter_in_chars(text: str, allowed_chars: str) -> str:
    """ Remove all characters that are not in allowed list """

    filtered_text = []
    for c in text:
        if c in allowed_chars: filtered_text.append(c)
    return ''.join(filtered_text)



def is_capitalized(word: str) -> bool:
    return word.istitle()



def capitalize(word: str) -> str:
    """
        Capitalize a single word or the first word of a given sentence
    
        TODO:
            * Capitalize compound names, i.e "marie-thérèse" -> "Marie-Thérèse"
        
        Should we capitalize the whole "C'H" character ? For now we don't.
    """

    # Find first letter
    lowered = word.lower()
    i = 0
    while i < len(lowered) and lowered[i] not in LETTERS: i += 1
    if i >= len(word):
        return word
    
    capitalized = word[:i] + word[i].upper() + word[i+1:]
    return capitalized



_PATTERN_BETWEEN_PARENTHESIS = re.compile(r"\((.+?)\)")

def extract_parenthesis_content(txt: str) -> Tuple[str, str]:
    extracted = []
    remaining = txt
    match = re.search(_PATTERN_BETWEEN_PARENTHESIS, remaining)
    while match:
        extracted.append(match.group(1))
        start, end = match.span()
        remaining = remaining[:start] + remaining[end:]
        match = re.search(_PATTERN_BETWEEN_PARENTHESIS, remaining)
    return remaining, extracted



def pre_process(text: str) -> str:
    """ Correct ambiguous quote characters, tilde and such """

    skrab = '\''
    # text = text.replace("c'h", f"c{skrab}h")
    # text = text.replace("C'h", f"C{skrab}h")
    # text = text.replace("C'H", f"C{skrab}H")
    text = text.replace('‘', skrab)
    text = text.replace('’', "'")
    text = text.replace('ʼ', skrab)
    text = text.replace(',', ',')
    text = text.replace('˜', '') # Found instead of non-breakable spaces when parsing Ya! pdfs
    text = text.replace('Š', '') # Found instead of long dashes when parsing Ya! pdfs
    text = text.replace('ñ', 'ñ') # A sneaky n-tilde (found in Ya! webpages)
    text = text.replace('ň', 'ñ')
    text = text.replace('ñ̃', 'ñ') # Found in brezhoweb subtitles
    text = text.replace('ù', 'ù') # Another sneaky one (found in Ya! webpages)
    text = text.replace('ê', 'ê') # Found in brezhoweb subtitles
    text = text.replace('û', 'û') # Found in brezhoweb subtitles
    text = text.replace('ı', 'i') # Found in #Brezhoneg newspaper
    text = text.replace('ã', 'a')
    text = text.replace('ö', 'o')
    text = text.replace('á', 'a')
    return text


def sentence_stats(sentence: str) -> dict:
    """ Get statistics about a text """
    
    letter = 0
    decimal = 0
    upper = 0
    punct = 0
    blank = 0
    other = 0
    
    for c in sentence:
        if c.lower() in LETTERS or c in "'-":
            letter += 1
            if c.isupper():
                upper += 1
        elif c.isdecimal():
            decimal += 1
        elif c.isspace():
            blank += 1
        elif c in PUNCTUATION:
            punct += 1
        else:
            other += 1
        
        sentence = filter_out_chars(sentence, PUNCTUATION)
    
    return {"letter": letter, "decimal": decimal, "upper": upper, "punct": punct,
            "blank": blank, "other": other, "words": len(sentence.split())}
