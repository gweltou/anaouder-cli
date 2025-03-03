#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Align a text file with an audio file, using a vosk model.
Can export to a subtitle file `srt` or `ali`.

Author:  Gweltaz Duval-Guennoc

Usage: ./linennan.py audio_file text_file

"""

from typing import List

import sys
import datetime
import argparse

import re
import srt
import jiwer
import static_ffmpeg
import os.path
from time import perf_counter

from anaouder.asr.models import load_model, get_latest_model
from anaouder.asr.recognizer import transcribe_file_timecoded
from anaouder.asr.post_processing import verbal_fillers
from anaouder.asr.dataset import format_timecode
from anaouder.text import (
    pre_process, filter_out_chars,
    sentence_stats,
    normalize_sentence, split_sentences,
    PUNCTUATION
)
from anaouder.utils import read_file_drop_comments
from anaouder.version import VERSION


autocorrect = False


def align(sentences:list, hyp:List[dict], left_boundary:int, right_boundary:int):
    """
        Try to locate the best match for each sentence in transcription
        Returns a list of match dictionaries {'hyp', 'score', 'span'}
    """
    matches = []
    for sentence in sentences:
        match = []
        for i in range(left_boundary, right_boundary):
            # Try to find a minima for the CER by adding one word at a time
            best_score = 999
            for offset in range(1, right_boundary - i + 1):
                hyp_window = hyp[i: i+offset]
                hyp_sentence = ' '.join( [t["word"].lower().replace('-', ' ') for t in hyp_window] )
                score = jiwer.cer(
                    filter_out_chars(sentence, ' '),
                    filter_out_chars(hyp_sentence, ' ')
                    )
                if score <= best_score:
                    best_score = score
                    best_span = (i, i+offset)
                    best_hyp = hyp_sentence
                else:
                    break
            
            match.append( {"hyp": best_hyp, "score": best_score, "span": best_span} )
        
        match.sort(key=lambda x: x["score"])
        
        # Keep only best match location for each sentence
        try:
            matches.append(match[0])
        except:
            print(f"{match=}")
            print(f"{sentence=}")
            print(f"{left_boundary=} {right_boundary=}")
            return []

    return matches


def get_prev_word_idx(matches, idx):
    if idx <= 0:
        return 0
    return matches[idx-1]["span"][1]

def get_next_word_idx(matches, idx, hyp):
    if idx >= len(matches) - 1:
        return len(hyp)
    return matches[idx+1]["span"][0]


def score_reliability(matches, hyp):
    """ Infer the reliability of each location by checking its adjacent neighbours """
    
    last_reliable_wi = 0
    for i, match in enumerate(matches):
        span = match["span"]
        prev_dist = get_prev_word_idx(matches, i) - span[0]
        next_dist = get_next_word_idx(matches, i, hyp) - span[1]
        # Allow for up to 2 words overlap between neighbours
        is_pdn = abs(prev_dist) <= 2 # is prev a direct-ish neighbour ?
        is_ndn = abs(next_dist) <= 2 # is next a direct-ish neighbour ?
        if is_pdn or is_ndn and (span[1] > last_reliable_wi):
            r = 'o' # Semi-reliable alignment
            if is_pdn and is_ndn and (abs(prev_dist) + abs(next_dist)) <= 2:
                r = 'O' # Reliable alignment
                last_reliable_wi = span[1]
        elif span[1] > last_reliable_wi:
            r = '?' # Not sure...
        else:
            r = 'X' # Obviously wrong alignment
        matches[i]["reliability"] = r
        
        if args.debug:
            print(f"{i} {span}\t{r}")



def get_unaligned_ranges(sentences, matches, rel=['O']):
    # Find ill-aligned sentence ranges
    wrong_ranges = []
    start = 0
    end = 0
    while True:
        while start < len(sentences) and matches[start]["reliability"] in rel:
            start += 1
        end = start
        while end < len(sentences) and matches[end]["reliability"] not in rel:
            end += 1
        if start >= len(sentences):
            break
        wrong_ranges.append((start, end))
        start = end
    return wrong_ranges



def count_aligned_utterances(matches):
    n = 0
    for match in matches:
        if match["reliability"] == 'O':
            n += 1
    return n
    


def calculate_cer(matches: list):
    total_cer = 0
    total_num_char = 0
    for i, match in enumerate(matches):
        num_char = len(match["hyp"]) - match["hyp"].count(' ')
        total_cer += match["score"] * num_char
        total_num_char += num_char

    return total_cer / total_num_char



def main_linennan() -> None:
    """ linennan cli entry point """
    global args

    parser = argparse.ArgumentParser(
        prog = "Linennan",
        description = "Create a timecoded file (`srt`, `seg` or `ali` file) from an audio file and a text file")
    parser.add_argument("audio_file")
    parser.add_argument("text_file")
    parser.add_argument("-m", "--model", default=get_latest_model("vosk"),
        help="Vosk model to use for decoding", metavar='MODEL_PATH')
    parser.add_argument("-t", "--type", choices=["srt", "seg", "ali"],
        help="file output type")
    parser.add_argument("-r", "--reformat", action="store_true",
        help="reformat text file using punctuation, to put one sentence per line")
    parser.add_argument("--keep-fillers", action="store_true",
        help="Keep verbal fillers ('euh', 'beñ', 'alors', 'kwa'...)")
    parser.add_argument("-o", "--output", help="write to a file")
    parser.add_argument("-d", "--debug", action="store_true",
        help="display debug information")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s v{VERSION}")
    args = parser.parse_args()
    
    # Use static_ffmpeg instead of ffmpeg
    static_ffmpeg.add_paths()

    load_model(args.model)

    lines = read_file_drop_comments(args.text_file)
    
    # Remove metadata
    lines = [ re.sub(r"{.+?}", '', l) for l in lines ]
    lines = [ l for l in lines if l ]

    if args.reformat:
        # Use punctuation to reformat text to one sentence per line
        lines = list(split_sentences(' '.join(lines), end=''))
    
    # Remove special labels <C'HOARZH>, <UNK>...
    sentences = [ re.sub(r"<[A-Z\']+?>", '', line) for line in lines ]
    # Remove punctuation
    sentences = [ filter_out_chars(pre_process(line), PUNCTUATION + "><*").strip() for line in lines ]
    
    # Look for numbers in text file, normalize in that case
    normalize = False
    for line in sentences:
        if sentence_stats(line)["decimal"] > 0:
            normalize = True
            break
    if normalize:
        sentences = [ normalize_sentence(line, autocorrect=autocorrect) for line in sentences ]
    
    sentences = [ " ".join(line.lower().replace('-', ' ').split()) for line in sentences ]

    print("Transcribing audio file...", flush=True)
    hyp = transcribe_file_timecoded(args.audio_file)
    if not args.keep_fillers:
        print("Removing verbal fillers", file=sys.stderr)
        hyp = [ tok for tok in hyp if tok["word"] not in verbal_fillers ]


    if args.debug:
        print("Number of words in hypothesis:", len(hyp))
    t_total = 0

    print("Aligning...")

    # Global alignment
    print("First iteration")
    t = perf_counter()
    sentence_matches = align(sentences, hyp, 0, len(hyp))
    score_reliability(sentence_matches, hyp)
    n_aligned = count_aligned_utterances(sentence_matches)

    dt = perf_counter() - t
    t_total += dt
    if args.debug:
        print(f"{n_aligned} aligned utterances", file=sys.stderr)
        print(f"Mean CER: {calculate_cer(sentence_matches):0.3}", file=sys.stderr)
        print("perf counter:", dt, file=sys.stderr)


    print("Second iteration", file=sys.stderr)
    t = perf_counter()
    unaligned_ranges = get_unaligned_ranges(sentences, sentence_matches)
    for start_range, end_range in unaligned_ranges:
        if start_range == 0:
            left_word_idx = 0
        else:
            left_word_idx = sentence_matches[start_range-1]["span"][1]
        if end_range == len(sentences):
            right_word_idx = len(hyp)
        else:
            right_word_idx = sentence_matches[end_range]["span"][0]
        if left_word_idx >= right_word_idx:
            continue
        matches = align(sentences[start_range: end_range], hyp, left_word_idx, right_word_idx)
        for idx in range(start_range, end_range):
            sentence_matches[idx] = matches[idx-start_range]

    score_reliability(sentence_matches, hyp)
    new_n_aligned = count_aligned_utterances(sentence_matches)

    dt = perf_counter() - t
    t_total += dt
    if args.debug:
        print(f"{new_n_aligned} aligned utterances", file=sys.stderr)
        print(f"Mean CER: {calculate_cer(sentence_matches):0.3}", file=sys.stderr)
        print("perf counter:", dt, file=sys.stderr)


    if new_n_aligned != n_aligned:
        print("Third iteration")
        t = perf_counter()
        unaligned_ranges = get_unaligned_ranges(sentences, sentence_matches, rel=['O'])
        for start_range, end_range in unaligned_ranges:
            if start_range == 0:
                left_word_idx = 0
            else:
                left_word_idx = sentence_matches[start_range-1]["span"][1]
            if end_range == len(sentences):
                right_word_idx == len(hyp)
            else:
                right_word_idx = sentence_matches[end_range]["span"][0]
            if left_word_idx >= right_word_idx:
                continue
            matches = align(sentences[start_range: end_range], hyp, left_word_idx, right_word_idx)
            for idx in range(start_range, end_range):
                sentence_matches[idx] = matches[idx-start_range]
        score_reliability(sentence_matches, hyp)
        n_aligned = new_n_aligned
        new_n_aligned = count_aligned_utterances(sentence_matches)

        dt = perf_counter() - t
        t_total += dt
        if args.debug:
            print(f"{new_n_aligned} aligned utterances")
            print(f"Mean CER: {calculate_cer(sentence_matches):0.3}", file=sys.stderr)
            print("perf counter:", dt)


    ni = 3
    for it in range(3):
        if new_n_aligned == n_aligned:
            break
        ni += 1
        print("Iteration", ni)
        t = perf_counter()

        reliable = ['O', 'o'] if it%2 == 0 else ['O']
        unaligned_ranges = get_unaligned_ranges(sentences, sentence_matches, rel=reliable)
        for start_range, end_range in unaligned_ranges:
            if start_range == 0:
                left_word_idx = 0
            else:
                left_word_idx = sentence_matches[start_range-1]["span"][1]
            if end_range == len(sentences):
                right_word_idx == len(hyp)
            else:
                right_word_idx = sentence_matches[end_range]["span"][0]
            if left_word_idx >= right_word_idx:
                continue
            matches = align(sentences[start_range: end_range], hyp, left_word_idx, right_word_idx)
            for idx in range(start_range, end_range):
                sentence_matches[idx] = matches[idx-start_range]
        score_reliability(sentence_matches, hyp)
        n_aligned = new_n_aligned
        new_n_aligned = count_aligned_utterances(sentence_matches)

        dt = perf_counter() - t
        t_total += dt
        if args.debug:
            print(f"{new_n_aligned} aligned utterances", file=sys.stderr)
            print(f"Mean CER: {calculate_cer(sentence_matches):0.3}", file=sys.stderr)
            print("perf counter:", dt, file=sys.stderr)
        

    print("Alignment total time:", t_total)

    # Try to fix remaining bad locations
    # for i in range(1, len(sentence_matches)-1):
    #     if reliability[i] == 'X':
    #         if reliability[i-1] in ('O', 'o') and reliability[i+1] in ('O', 'o'):
    #             if sentence_matches[i-1]["span"][1] >= sentence_matches[i+1]["span"][0]:
    #                 # Neighbours boundaries are wrong
    #                 span = ('?', '?') 
    #             else:
    #                 span = (get_prev_word_idx(i), get_next_word_idx(i))
    #             hyp_window = hyp[span[0]: span[1]]
    #             hyp_sentence = ' '.join( [t["word"].lower().replace('-', ' ') for t in hyp_window] )
    #             score = jiwer.cer(
    #                 filter_out(cleaned_lines[i], ' '),
    #                 filter_out(hyp_sentence, ' ')
    #                 )
    #             sentence_matches[i] = {"hyp": hyp_sentence, "score": score, "span": span}
    #             reliability[i] = '.'
    

    # Naive segmentation of remaining unaligned ranges
    unaligned_ranges = get_unaligned_ranges(sentences, sentence_matches, rel=['O', 'o'])
    
    for start_range, end_range in unaligned_ranges:
        size = end_range - start_range
        span = (
            get_prev_word_idx(sentence_matches, start_range), 
            get_next_word_idx(sentence_matches, end_range-1, hyp)
            )
        n_words = span[1] - span[0]
        step = n_words / size
        prev = span[0]
        for i in range(size):
            new_span = (prev, prev + round(step))
            hyp_window = hyp[new_span[0]: new_span[1]]
            hyp_sentence = ' '.join( [t["word"].lower().replace('-', ' ') for t in hyp_window] )
            score = jiwer.cer(
                filter_out_chars(sentences[start_range+i], ' '),
                filter_out_chars(hyp_sentence, ' ')
                )
            sentence_matches[start_range+i] = {"hyp": hyp_sentence, "score": score, "span": new_span}
            sentence_matches[start_range+i]["reliability"] = '/'
            prev += round(step)
    
    if args.debug:
        for i, match in enumerate(sentence_matches):
            print(f"{i} {match["span"]}\t{match["reliability"]}")


    print(f"Mean CER: {calculate_cer(sentence_matches):0.3}", file=sys.stderr)

    n = 0
    for i, l in enumerate(sentences):
        if sentence_matches[i]["reliability"] in ('X', '/', '?'):
            n += 1
    print(f"{n} ill-aligned segment{'s' if n>1 else ''}", file=sys.stderr)


    # Resolve file output type
    if args.output and not args.type:
        # No type explicitely defined, use output file extension
        split_ext = args.output.rsplit('.', maxsplit=1)
        if len(split_ext) == 2:
            ext = split_ext[1].lower()
            if ext in ("srt", "seg", "ali"):
                args.type = ext
            else:
                print("Unrecognized extension, using default type (`srt`)", file=sys.stderr)
                args.type = "srt"
        else:
            # No file extension found, use default type
            args.type = "srt"

    if not args.type:
        args.type = "srt"
    

    fout = open(args.output, 'w') if args.output else sys.stdout

    if args.type == "srt":
        subs = []
        last = -1
        for i, line in enumerate(lines):
            if sentence_matches[i]["reliability"] == 'X':
                continue

            span = sentence_matches[i]["span"]
            start = hyp[span[0]]["start"]
            if start <= last: # Avoid timecode overlap
                start += 0.05
            end = hyp[span[1]-1]["end"]
            last = end
            s = srt.Subtitle(index=len(subs),
                    content=line,
                    start=datetime.timedelta(seconds=start),
                    end=datetime.timedelta(seconds=end))
            subs.append(s)

        print(srt.compose(subs), file=fout)
    

    elif args.type == "seg":
        # utts = []
        for i, line in enumerate(lines):
            if sentence_matches[i]["reliability"] == 'X':
                continue

            span = sentence_matches[i]["span"]
            start = int(hyp[span[0]]["start"] * 1000)
            end = int(hyp[span[1]-1]["end"] * 1000)
            print(f"{line} {{start: {start}; end: {end}}}", file=fout)
    

    elif args.type == "ali":
        print(f"{{audio-path: {os.path.basename(args.audio_file)}}}\n\n", file=fout)

        for i, line in enumerate(lines):
            if sentence_matches[i]["reliability"] == 'X':
                continue

            span = sentence_matches[i]["span"]
            start = hyp[span[0]]["start"]
            end = hyp[span[1]-1]["end"]
            print(f"{line.strip()} {{start: {format_timecode(start)}; end: {format_timecode(end)}}}",
                  file=fout)
    

    if args.output:
        fout.close()



if __name__ == "__main__":
    main_linennan()
