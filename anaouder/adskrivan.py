#! /usr/bin/env python3

import sys
import os.path
import datetime
import argparse
import subprocess

import static_ffmpeg
import json
import srt
from vosk import KaldiRecognizer
from pydub import AudioSegment
from tqdm import tqdm

from anaouder.asr.models import load_model, get_latest_model
from anaouder.asr.recognizer import transcribe_file_timecoded, transcribe_segment_timecoded
from anaouder.asr.post_processing import post_process_text, post_process_timecoded
from anaouder.asr.dataset import create_eaf, create_ali_file
from anaouder.audio import split_to_segments
from anaouder.version import VERSION



def _split_vosk_tokens(tokens, min_silence=0.5):
    subsegments = []
    current_segment = [tokens[0]]
    for tok in tokens[1:]:
        if tok['start'] - current_segment[-1]['end'] > min_silence:
            # We shall split here
            subsegments.append(current_segment)
            current_segment = []
        current_segment.append(tok)
    subsegments.append(current_segment)
    return subsegments


def split_vosk_tokens(tokens, max_length=15):
    """ Split sequences of Vosk tokens on silences """
    token_segments = [tokens]
    silence_length = 1.0

    while True:
        n_long_segments = 0
        parsed = []
        for segment in token_segments:
            dur = segment[-1]['end'] - segment[0]['start']
            if dur > max_length:
                # Split this segment deeper
                sub = _split_vosk_tokens(segment, silence_length)
                parsed.extend(sub)
                n_long_segments += 1
            else:
                parsed.append(segment)
        token_segments = parsed
        silence_length -= 0.1
        if n_long_segments == 0 or silence_length < 0.3:
            break
    
    return token_segments


def main_adskrivan(*args, **kwargs) -> None:
    """ adskrivan cli entry point """

    desc = f"Decode an audio file in any format, with the help of ffmpeg"
    parser = argparse.ArgumentParser(description=desc, prog="adskrivan")
    parser.add_argument('filename')
    parser.add_argument("-m", "--model", default=get_latest_model("vosk"),
        help="Vosk model to use for decoding", metavar='MODEL_PATH')
    parser.add_argument("-n", "--normalize", action="store_true",
        help="Normalize numbers")
    parser.add_argument("--keep-fillers", action="store_true",
        help="Keep verbal fillers ('euh', 'beñ', 'alors', 'kwa'...)")
    parser.add_argument("-t", "--type", choices=["txt", "srt", "eaf", "ali", "json"],
        help="file output type")
    parser.add_argument("-o", "--output", help="write to a file")
    parser.add_argument("--autosplit", action="store_true",
        help="Pre-split audio at silences (used for 'srt', 'eaf' or 'ali' types only)")
    parser.add_argument("--segment-max-length",
        help="Will try not to go above this length when segmenting audio files (seconds)",
        type=float, default=10)
    parser.add_argument("--max-words-per-line", type=int, default=7,
        help="Number of words per line for subtitle files")
    parser.add_argument("--set-ffmpeg-path", type=str,
        help="Set ffmpeg path (will not use static_ffmpeg in that case)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s v{VERSION}")

    if args:
        args = parser.parse_args(args)
    else:
        args = parser.parse_args()
    
    if not os.path.exists(args.filename):
        print("Couldn't find file '{}'".format(args.filename))
        sys.exit(1)
        
    
    # Use static_ffmpeg instead of ffmpeg
    ffmpeg_path = "ffmpeg"
    if args.set_ffmpeg_path:
        ffmpeg_path = args.set_ffmpeg_path
    else:
        static_ffmpeg.add_paths()
    
    if args.type:
        args.type = args.type.lower()
    else:
        if args.output:
            # No explicit type was given to we'll try to infer it from output file extension
            ext = os.path.splitext(args.output)[1][1:].lower()
            if ext in ("srt", "json", "eaf", "ali"):
                args.type = ext
            else:
                args.type = "txt"	# Default type
        else:
            args.type = "txt"

    # Special default behaviour for ALI type
    if args.type in ("ali",):
        args.keep_fillers = True

    model = load_model(args.model)

    fout = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout

    if args.type == "txt":
        # No need for timecodes

        if args.output:
            # Whole file decoding
            # Different segmentation algorithm than online decoding
            # Shows a progress bar
            print("Transcribing audio file...", flush=True)
            tokens = transcribe_file_timecoded(args.filename)
            token_segments = split_vosk_tokens(tokens, max_length=args.segment_max_length)
            token_segments = [
                post_process_timecoded(seg, not args.normalize, args.keep_fillers)
                for seg in token_segments
            ]
            token_sentences = [ ' '.join([token['word'] for token in seg]) for seg in token_segments ]
            
            fout.write('\n'.join(token_sentences))
        else:
            # Online decoding
            # Print decoded sentences one-by-one
            rec = KaldiRecognizer(model, 16000)
            rec.SetWords(True)
        
            with subprocess.Popen([ffmpeg_path, "-loglevel", "quiet", "-i",
                                    args.filename,
                                    "-ar", "16000" , "-ac", "1", "-f", "s16le", "-"],
                                    stdout=subprocess.PIPE).stdout as stream:
                while True:
                    data = stream.read(4000)
                    if len(data) == 0:
                        break
                    if rec.AcceptWaveform(data):
                        sentence = json.loads(rec.Result())["text"]
                        sentence = post_process_text(sentence, not args.normalize, args.keep_fillers)
                        if sentence: print(sentence, file=fout)

                sentence = json.loads(rec.FinalResult())["text"]
                sentence = post_process_text(sentence, not args.normalize, args.keep_fillers)
                if sentence: print(sentence, file=fout)


    elif args.type in ("srt", "ali", "eaf", "json"):
        # Transcribe with timecodes

        if args.autosplit:
            song = AudioSegment.from_file(args.filename)
            song = song.set_channels(1)
            if song.frame_rate != 16000:
                song = song.set_frame_rate(16000)
            if song.sample_width != 2:
                song = song.set_sample_width(2)
            
            # Audio need to be segmented first
            print("Segmenting audio file...", end=' ', flush=True)
            segments = split_to_segments(
                song,
                max_length=args.segment_max_length
                )
            print(f"{len(segments)} segment{'s' if len(segments)>1 else ''} found")

            t_min, t_max = 0, segments[-1][1]
            token_sentences = []
            for seg in tqdm(segments):
                tr = transcribe_segment_timecoded(song[max(t_min, seg[0]-200):min(t_max, seg[1]+200)])
                token_sentences.append(tr)
            
        else:
            print("Transcribing audio file...", flush=True)
            tokens = transcribe_file_timecoded(args.filename)
            token_sentences = split_vosk_tokens(tokens, max_length=args.segment_max_length)
            segments = [ [sent[0]['start'], sent[-1]['end']] for sent in token_sentences ]

        # Post-process and remove empty sentences
        utterances = []
        for sentence, segment in zip(token_sentences, segments):
            if sentence:
                utterances.append(
                    (post_process_timecoded(sentence, not args.normalize, args.keep_fillers),
                    segment)
                )


        if args.type == "json":
            token_sentences, _ = zip(*utterances)
            tokens = sum(token_sentences, list())
            json.dump(tokens, fout, indent=2)


        if args.type == "srt":
            # Re-split sentences to fit subtitles
            words_per_line = args.max_words_per_line
            if words_per_line == 0: words_per_line = 999
            subs = []
            for sentence, segment in utterances:
                for j in range(0, len(sentence), words_per_line):
                    line = sentence[j : j + words_per_line]
                    text = ' '.join([ w["word"] for w in line ])

                    if args.autosplit:
                        offset = segment[0]/1000
                        s = srt.Subtitle(index=len(subs),
                                content=text,
                                start=datetime.timedelta(seconds=line[0]["start"]+offset),
                                end=datetime.timedelta(seconds=line[-1]["end"]+offset))
                    else:
                        s = srt.Subtitle(index=len(subs),
                                content=text,
                                start=datetime.timedelta(seconds=line[0]["start"]),
                                end=datetime.timedelta(seconds=line[-1]["end"]))
                    subs.append(s)
            
            # Write to a srt file with the same name as input file by default
            # if not args.output:
            #     srt_path = os.path.splitext(args.filename)[0] + ".srt"
            #     fout = open(srt_path, 'w', encoding='utf-8')

            print(srt.compose(subs), file=fout)
        

        elif args.type == "eaf":
            token_sentences, segments = zip(*utterances)
            text_sentences = []
            for sentence in token_sentences:
                sentence = ' '.join([ t['word'] for t in sentence ])
                text_sentences.append(sentence)
            ext = os.path.splitext(args.filename)[1][1:].lower()
            if ext not in ('mp3', 'wav'):
                data = create_eaf(segments, text_sentences, args.filename, type="mp3")
            else:
                data = create_eaf(segments, text_sentences, args.filename)

            print(data, file=fout)
            if args.output:
                print("EAF file written to", os.path.abspath(args.output))
        

        elif args.type == "ali":
            token_sentences, segments = zip(*utterances)
            sentences = [' '.join([ t['word'] for t in s ]) for s in token_sentences]
            data = create_ali_file(
                sentences,
                segments,
                audio_path=os.path.basename(args.filename)
                )
            print(data, file=fout)


    if args.output:
        fout.close()
    

if __name__ == "__main__":
    main_adskrivan()
