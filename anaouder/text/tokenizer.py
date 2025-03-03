#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Programming pattern inspired by https://github.com/mideind/Tokenizer
"""


from typing import Iterator, Iterable, List, Any, Union, Set
from enum import Enum
import os.path
import re

from sentence_splitter import SentenceSplitter, split_text_into_sentences

from .definitions import (
    re_word, is_word, is_word_inclusive, re_extended_word,
    is_roman_number, is_ordinal, is_roman_ordinal,
    is_noun, is_noun_f, is_noun_m, is_proper_noun,
    is_time, match_time,
    is_unit_number, match_unit_number,
    PUNCTUATION, LETTERS, SI_UNITS,
    OPENING_QUOTES, CLOSING_QUOTES,
    PUNCT_PAIRS, OPENING_PUNCT, CLOSING_PUNCT,
)
from .utils import capitalize, is_capitalized
from ..dicts import acronyms, abbreviations, corrected_tokens, standard_tokens




class Token:
    # Enum
    RAW = -1
    SPECIAL_TOKEN = 0
    END_OF_SENTENCE = 1
    PUNCTUATION = 2
    WORD = 3
    NUMBER = 4
    ROMAN_NUMBER = 5
    NOUN = 6
    PROPER_NOUN = 7
    VERB = 8
    ACRONYM = 9
    ORDINAL = 10
    ROMAN_ORDINAL = 11
    TIME = 12
    UNIT = 13         # %, m, km2, kg...
    QUANTITY = 14     # a number and a unit (%, m, km2, kg, bloaz, den...)
    ABBREVIATIION = 15
    UNKNOWN = 99

    descr = {
        RAW: "RAW",
        SPECIAL_TOKEN: "SPECIAL_TOKEN",
        END_OF_SENTENCE: "END_OF_SENTENCE",
        WORD: "WORD",
        NUMBER: "NUMBER",
        ROMAN_NUMBER: "ROMAN_NUMBER",
        PUNCTUATION: "PUNCTUATION",
        NOUN: "NOUN",
        PROPER_NOUN: "PROPER_NOUN",
        VERB: "VERB",
        ACRONYM: "ACRONYM",
        ORDINAL: "ORDINAL",
        ROMAN_ORDINAL: "ROMAN_ORDINAL",
        TIME: "TIME",
        UNIT: "UNIT",
        QUANTITY: "QUANTITY",
        # PERCENT: "PERCENT",
        ABBREVIATIION: "ABBREVIATION",
        UNKNOWN: "UNKNOWN",
    }

    def __init__(self, data: str, kind: int=RAW, *flags):
        self.data = data
        self.norm = []
        self.kind = kind
        self.flags: Set[Flag] = set(flags)
        self.next = None # The token following this one, after "generate_tokens_lookahead" is called
    
    def __repr__(self):
        flags_name = [flag.name for flag in self.flags]
        return "Token(" + \
            f"{repr(self.data)}, {self.descr[self.kind]}" + \
            f", {flags_name if flags_name else ''}" + \
            ")"


class Flag(Enum):
    FIRST_WORD = 1
    MASCULINE = 2
    FEMININE = 3
    INCLUSIVE = 4
    CAPITALIZED = 5
    CORRECTED = 6
    OPENING_PUNCT = 7
    CLOSING_PUNCT = 8



_root = os.path.dirname(os.path.abspath(__file__))
_moses_prefix_file = os.path.join(_root, "moses_br.txt")

def split_sentences(text_or_gen: Union[str, Iterable[str]]) -> Iterator[str]:
    """ Split a line (or list of lines) according to its punctuation
        This function can be used independently
    """
   #print(text_or_gen)
    if isinstance(text_or_gen, str):
        text = text_or_gen
    else:
        text = ' '.join([line.strip() for line in text_or_gen])
    
    return split_text_into_sentences(
            text=text,
            language='br',
            non_breaking_prefix_file=_moses_prefix_file
        )


def split_sentences_old(text_or_gen: Union[str, Iterable[str]], **options: Any) -> Iterator[str]:
    """ Split a line (or list of lines) according to its punctuation
        This function can be used independently

        Parameters
        ----------
            end : str
                End the sentences with the given character

    """

    end_char = options.pop("end", '\n')
    # preserve_newline = options.pop("preserve_newline", False)

    if isinstance(text_or_gen, str):
        if not text_or_gen:
            return
        text_or_gen = [text_or_gen]
    
    token_stream = generate_raw_tokens(text_or_gen)
    token_stream = parse_punctuation(token_stream)
    token_stream = generate_tokens_lookahead(token_stream) # Needed to generate subsequent eos tokens
    token_stream = generate_eos_tokens(token_stream)

    current_sentence = []
    for tok in token_stream:
        if tok.kind == Token.END_OF_SENTENCE:
            yield detokenize(current_sentence, **options) + end_char
            current_sentence = []
        else:
            current_sentence.append(tok)
    if current_sentence:
        yield detokenize(current_sentence, **options) + end_char





def tokenize(text_or_gen: Union[str, Iterable[str]], **options: Any) -> Iterator[Token]:
    """
        Parameters
        ----------
            autocorrect: boolean
                Try to correct typos with a substitution dictionary
            
            norm_punct: boolean
                Normalize punctuation
        
        TODO:
            * &
    """

    # Arg options
    autocorrect = options.pop('autocorrect', False)
    #standardize = options.pop('standardize', False)
    
    token_stream = generate_raw_tokens(text_or_gen)
    token_stream = parse_punctuation(token_stream, **options)
    token_stream = generate_tokens_lookahead(token_stream)
    token_stream = generate_eos_tokens(token_stream)
    if autocorrect:
        token_stream = correct_tokens(token_stream)
    token_stream = parse_numerals(token_stream)
    token_stream = parse_regular_words(token_stream, **options)
    # token_stream = parse_acronyms(token_stream)

    return token_stream



def detokenize(token_stream: Iterator[Token], **options: Any) -> str:
    """
        Parameters
        ----------
            capitalize: boolean
                Capitalize sentence
            
            end: str
                String to append at end of each sentence
    """
    
    # Parse options
    end_sentence = options.pop('end', '')
    capitalize_opt = options.pop('capitalize', False)
    normalize = options.pop("normalize", False)
    # colored = options.pop("colored", False)

    parts: List[str] = []
    punct_stack = [] # Used to keep track of coupled punctuation (quotes and brackets)
    capitalize_next_word = capitalize_opt

    for tok in token_stream:
        data = tok.norm[0] if (normalize and tok.norm) else tok.data

        if capitalize_next_word:
            data = data.capitalize()
            capitalize_next_word = False

        prefix = ''
        if tok.kind == Token.PUNCTUATION:
            if data in '!?:;–':
                prefix = '\xa0' # Non-breakable space
            elif data == '"':
                if punct_stack and punct_stack[-1] == '"':
                    punct_stack.pop()
                    prefix = ''
                else:
                    punct_stack.append('"')
                    prefix = ' '
            elif data in OPENING_QUOTES:
                # we use a single '"' char to represent every kind of quotation mark
                # this prevents problems when mixing types of quotation marks
                punct_stack.append('"')
                prefix = ' '
            elif data in CLOSING_QUOTES:
                if punct_stack and punct_stack[-1] == '"':
                    punct_stack.pop()
                prefix = '\xa0' if data == '»' else ''
            elif data in '([':
                punct_stack.append(data)
                prefix = ' '
            elif data in ')':
                if punct_stack and punct_stack[-1] == '(':
                    punct_stack.pop()
                prefix = ''
            elif data in ']':
                if punct_stack and punct_stack[-1] == '[':
                    punct_stack.pop()
                prefix = ''
            elif data == '/…':
                prefix = ''
        
        elif tok.kind == Token.END_OF_SENTENCE:
            prefix = end_sentence
            if capitalize_opt:
                capitalize_next_word = True

        elif parts and parts[-1]:
            last_char = parts[-1][-1]
            if last_char == '«':
                prefix = '\xa0'
            elif punct_stack and last_char == punct_stack[-1]:
                prefix = ''
            elif punct_stack and last_char == '“':
                prefix = ''
            elif last_char not in '-/':
                prefix = ' '

        if parts:
            parts.append(prefix + data)
        else:
            # First word in sentence
            parts.append(data if data else '')
        if parts[-1] == '':
            parts.pop()
    
    if parts:
        ret = ''.join(parts)
        return ret
    return ''





def generate_raw_tokens(text_or_gen: Union[str, Iterable[str]]) -> Iterator[Token]:
    """ 
        Generate raw tokens by splitting strings on whitespaces

        <SPECIAL_TOKENS> will be generated at this stage as well
    """
    
    if isinstance(text_or_gen, str):
        if not text_or_gen:
            return
        text_or_gen = [text_or_gen]
    
    for sentence in text_or_gen:
        for s in sentence.split():
            if re.fullmatch(r"<[A-Z']+>", s):
                yield Token(s, Token.SPECIAL_TOKEN)
            else:
                yield Token(s, Token.RAW)


def generate_tokens_lookahead(token_stream: Iterator[Token]):
    try:
        token = next(token_stream)
    except StopIteration:
        return
    for next_token in token_stream:
        token.next = next_token
        yield token
        token = next_token
    token.next = None
    yield token



def generate_eos_tokens(token_stream: Iterator[Token]) -> Iterator[Token]:
    """
        Adds <END_OF_SENTENCE> tokens to token stream.

        Tokens must have the 'next' parameter defined by calling
        'generate_tokens_lookahead' on the token stream first.
    """

    subsentence_depth = 0
    in_double_quotes = False
    first_in_sentence = True

    for token in token_stream:
        if first_in_sentence and not token.kind == Token.PUNCTUATION:
            token.flags.add(Flag.FIRST_WORD)
            first_in_sentence = False
        
        if token.kind != Token.PUNCTUATION:
            yield token
            continue

        if Flag.OPENING_PUNCT in token.flags:
            subsentence_depth += 1
        elif Flag.CLOSING_PUNCT in token.flags:
            subsentence_depth -= 1
        elif token.data == '"':
            in_double_quotes = not in_double_quotes
            subsentence_depth += 1 if in_double_quotes else -1

        if token.norm:
            punct = token.norm[0]
        else:
            punct = token.data
        
        if punct in ".!?":
            yield token
            first_in_sentence = True
            if subsentence_depth == 0:
                yield Token('', Token.END_OF_SENTENCE)
        elif punct == '…' or re.fullmatch(r"\.\.+", punct):
            yield token
            first_in_sentence = True
            if subsentence_depth == 0 and token.next and is_capitalized(token.next.data):
                yield Token('', Token.END_OF_SENTENCE)
        else:
            yield token



def parse_punctuation(token_stream: Iterator[Token], **options: Any) -> Iterator[Token]:
    """
        Parse a stream of raw tokens to find punctuation marks

        Options:
            * norm_punct: Normalize punctuation marks
    
        TODO:
            * URLS, email addresses (anything with internal punctuation marks)
            * Fix: A... -> A.…
            * Fix: Y. -B. Piriou
    """

    # Normalize punctuation option
    norm_punct = options.pop('norm_punct', False)

    for tok in token_stream:
        if tok.kind == Token.RAW:
            data = tok.data
            subtokens = []
            post_subtokens = []

            while data:
                #print(f"'{data}'")

                # Check at the beggining of the token
                # Check for opening punctuation
                if data[0] in OPENING_PUNCT:
                    # punct_stack.append(data[0])
                    subtokens.append(Token(data[0], Token.PUNCTUATION, Flag.OPENING_PUNCT))
                    data = data[1:]
                    continue

                # Check for closing punctuation
                if data[0] in CLOSING_PUNCT:
                    # if punct_stack and data[0] == PUNCT_PAIRS[punct_stack[-1]]:
                    #     punct_stack.pop()
                    subtokens.append(Token(data[0], Token.PUNCTUATION, Flag.CLOSING_PUNCT))
                    data = data[1:]
                    continue
                
                # Check for ellipsis
                m = re.match(r"\.\.+", data)
                if m:
                    subtokens.append(Token(m.group(), Token.PUNCTUATION))
                    data = data[m.end():]
                    continue
                
                # Check for single punctuation mark
                if data[0] in PUNCTUATION:
                    subtokens.append(Token(data[0], Token.PUNCTUATION))
                    data = data[1:]
                    continue
                

                # Check for common abbreviations
                skip = False
                for abbr in abbreviations:
                    # pattern = abbr.replace('.', '\\.')
                    # m = re.fullmatch(pattern, data, re.IGNORECASE)
                    # if m:
                    if data == abbr:
                        t = Token(data, Token.ABBREVIATIION)
                        t.norm.append(abbreviations[abbr])
                        subtokens.append(t)
                        data = data[len(abbr):]
                        skip = True
                        break
                if skip:
                    continue

                m = re.match(r"h\.a(?=…)", data, re.IGNORECASE)
                if m:
                    t = Token(m.group(), Token.ABBREVIATIION)
                    t.norm.append("hag all")
                    subtokens.append(t)
                    subtokens.append(Token('…', Token.PUNCTUATION))
                    data = data[4:]
                    continue


                # Single initial or group of initials (i.e: I.E. or U.N.…)
                m = re.match(r"([A-Z]\.)+", data)
                if m:
                    subtokens.append(Token(m.group(), Token.ACRONYM))
                    data = data[m.end():]
                    continue
                

                # Check for trailing punctuation
                # Trailing ellipsis
                m = re.search(r"\.\.+$", data)
                if m:
                    post_subtokens.insert(0, Token(m.group(), Token.PUNCTUATION))
                    data = data[:m.start()]
                    continue

                # Other trailing punctuation
                m = re.match(r"\!(\!)*$", data)
                if m:
                    t = Token(m.group(), Token.PUNCTUATION)
                    t.norm.append('!')
                    post_subtokens.insert(0, t)
                    data = data[:m.start()]
                    continue
                
                m = re.match(r"\?(\?)*$", data)
                if m:
                    t = Token(m.group(), Token.PUNCTUATION)
                    t.norm.append('?')
                    post_subtokens.insert(0, t)
                    data = data[:m.start()]
                    continue
                
                if data[-1] in CLOSING_PUNCT:
                    post_subtokens.insert(0, Token(data[-1], Token.PUNCTUATION, Flag.CLOSING_PUNCT))
                    data = data[:-1]
                    continue

                if data[-1] in PUNCTUATION:
                    post_subtokens.insert(0, Token(data[-1], Token.PUNCTUATION))
                    data = data[:-1]
                    continue

                # Check for SI_UNITS here maybe

                # Parse the remainder
                m = re_extended_word.match(data)             # Doesn't match (covid-19)
                #m = re.match(r"[\w\-'’·]+", data)  # Breaks numbers with dots or commas
                # m = common_word.match(data)       # Doesn't match the final hyphen (labour- \ndouar )
                if m:
                    l = m.end() - m.start()
                    subtokens.append(Token(m.group()))
                    data = data[l:]
                    continue

                subtokens.append(Token(data))
                data = ''
            
            for t in subtokens + post_subtokens:
                if norm_punct:
                    if re.fullmatch(r"\.\.+", t.data):
                        t.norm.append('…')
                    elif t.data == '‚':   # dirty comma
                        t.norm.append(',')
                yield t
        
        else:
            yield tok



def parse_regular_words(token_stream: Iterator[Token], **options: Any) -> Iterator[Token]:
    """ It should be called after `parse_punctuation`
    
        TODO:
            * Brezhoneg/Galleg
            * miz Gouere.Laouen e oa
    """

    # Arg options

    for tok in token_stream:
        if tok.kind == Token.RAW:
            if tok.data in acronyms:
                tok.kind = Token.ACRONYM
            elif tok.data.isupper() and Flag.FIRST_WORD not in tok.flags:
                tok.kind = Token.ACRONYM
            elif is_word(tok.data):
                # Token is a simple and well formed word
                if is_proper_noun(tok.data):
                    tok.kind = Token.PROPER_NOUN
                else:
                    tok.kind = Token.WORD
                    if is_word_inclusive(tok.data):
                        tok.flags.add(Flag.INCLUSIVE)
            yield tok
        else:
            yield tok



def parse_numerals(token_stream: Iterator[Token]) -> Iterator[Token]:
    """ Look for various numeral forms: numbers, ordinals, units...
        It should be applied before `parse_regular_words` to accurately parse quantities

        TODO:
            * 1,20
            * €/miz
            * +40 %
            * d'ar Sul 10/10
            * ½
            * 02.98.00.00.00
            * 2003-2004
    """

    # prev_token = None
    num_concat = "" # buffer to contatenate numeral forms such as '12 000' -> '12000'
    for tok in token_stream:
        if tok.kind == Token.RAW:
            # r"[+-]?\d+(?:,\d+)"

            if tok.data.isdecimal():
                if not num_concat and len(tok.data) < 4:
                    num_concat += tok.data
                elif num_concat and len(tok.data) == 3:
                    num_concat += tok.data                    
                else:
                    # A full number
                    tok.kind = Token.NUMBER
            elif re.fullmatch(r"\d{1,3}(\.\d\d\d)+", tok.data):
                # Big number with dotted thousands (i.e: 12.000.000)
                tok.data = tok.data.replace('.', '')
                tok.kind = Token.NUMBER
            else:
                if is_roman_number(tok.data):
                    tok.kind = Token.ROMAN_NUMBER
                elif is_ordinal(tok.data):
                    tok.kind = Token.ORDINAL
                elif is_roman_ordinal(tok.data):
                    tok.kind = Token.ROMAN_ORDINAL
                elif is_time(tok.data):
                    # TODO: Check for token 'gm', 'g.m', 'GM'...
                    tok.kind = Token.TIME
                elif is_unit_number(tok.data):
                    # ex: "10m2"
                    number, unit = match_unit_number(tok.data).groups()
                    number = number.replace('.', '')
                    tok.kind = Token.QUANTITY
                    tok.data = f"{num_concat}{number}{unit}"
                    tok.number = num_concat + number
                    tok.unit = unit
                    if num_concat:
                        num_concat = ""
                elif tok.data in SI_UNITS:
                    if num_concat:
                        # ex: "10 s"
                        tok.kind = Token.QUANTITY
                        tok.number = num_concat
                        tok.unit = tok.data
                        tok.data = num_concat + tok.data
                        num_concat = ""
                    elif tok.data not in ('l', 'm', 't', 'g'):
                        tok.kind = Token.UNIT
                elif num_concat and is_noun(tok.data):
                    # ex: "32 bloaz"
                    tok.kind = Token.QUANTITY
                    tok.number = num_concat
                    tok.unit = tok.data
                    if is_word_inclusive(tok.data):
                        tok.flags.add(Flag.INCLUSIVE)
                    else:
                        if is_noun_f(tok.data):
                            tok.flags.add(Flag.FEMININE)
                        if is_noun_m(tok.data):
                            tok.flags.add(Flag.MASCULINE)
                    tok.data = f"{num_concat} {tok.data}"
                    num_concat = ""
                
                if num_concat:
                    yield Token(num_concat, Token.NUMBER)
                    num_concat = ""
        
        else:
            if num_concat:
                yield Token(num_concat, Token.NUMBER)
                num_concat = ""

        if not num_concat:
            yield tok
    
    if num_concat:
        yield(Token(num_concat, Token.NUMBER))



def correct_tokens(token_stream: Iterator[Token]) -> Iterator[Token]:
    """
        Correct words from `corrected_tokens.tsv` and `standard_tokens.tsv`.
        Should be applied before `parse_regular_words`
    """

    def get_susbitution(word: str) -> List[str]:
        lowered = word.lower()
        
        if lowered in corrected_tokens:
            substitutes = corrected_tokens[lowered]
        elif lowered in standard_tokens:
            substitutes = standard_tokens[lowered]
        else:
            return []
        
        # Keep capitalization
        i = 0
        while lowered[i] not in LETTERS: i += 1
        if word[i].isupper():
            first = capitalize(substitutes[0])
            return [first] + substitutes[1:]
        else:
            return substitutes

        


    for tok in token_stream:
        if tok.kind == Token.RAW:
            lowered = tok.data.lower()
            substitutes = get_susbitution(tok.data)
            if substitutes:
                # We must keep the prepended apostrophe (there could be a substitution rule for it)
                yield from [ Token(s, Token.RAW, Flag.CORRECTED) for s in substitutes ]
            elif lowered.startswith("'") and lowered[1:] not in ('n', 'm', 'z'):
                # Remove prepended apostrophies
                # Check if there is a susbstitution rule for the remaining word
                substitutes = get_susbitution(tok.data[1:])
                if substitutes:
                    yield from [ Token(s, Token.RAW, Flag.CORRECTED) for s in substitutes ]
                else:
                    # Pass the word without the apostrophe
                    tok.data = tok.data[1:]
                    yield tok
            else:
                yield tok
        else:
            yield tok