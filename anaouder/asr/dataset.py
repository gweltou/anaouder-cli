from typing import Tuple, List, Dict
import sys
import os.path
import re
from math import floor, ceil

from hashlib import md5
from uuid import uuid4
from colorama import Fore

# For eaf (Elan) file conversion
from xml.dom import minidom
import datetime, pytz

from ..utils import read_file_drop_comments
from ..text import (
    pre_process, normalize_sentence, filter_out_chars,
    split_sentences, tokenize, detokenize, normalize, Token,
    PUNCTUATION,
    VALID_CHARS
)
from ..audio import convert_to_mp3, find_associated_audiofile
from ..version import VERSION


datafile_header = \
"""{source: }
{source-audio: }
{author: }
{licence: }
{tags: }\n\n
"""


# Special tokens, found in transcriptions
special_tokens = {
    "<UNK>": "SPN",
    "<SPOKEN_NOISE>": "SPN",
    "<NTT>": "SPN",
    "<C'HOARZH>": "LAU",
    "<HUM>": "SPN",
    "<PASAAT>": "SPN",
    "<SONEREZH>": "NSN",
    "<FRONAL>": "SPN",
}



Segment = Tuple[int, int]

def load_segments_data(segfile: str) -> List[Segment]:
    """ Load audio segments delimiters from a `.seg` file
        Return a list of segments
    """

    segments = []
    with open(segfile, 'r') as f:
        for l in f.readlines():
            l = l.strip()
            if not l or l.startswith('#'):
                continue
            t = l.split()
            start = int(t[0]) / 1000
            stop = int(t[1]) / 1000
            segments.append((start, stop))
            
    return segments



def load_text_data(filename) -> List[Tuple[str, Dict]]:
    """ 
        Return list of sentences with metadata.
        Metadata dictionaries will always have, at least, the "speaker" and "gender" keys.

        Return
        ------
            list of tuple (text sentences, metadata)
    """
    utterances = []
    current_speaker = 'unknown'
    current_gender = 'unknown'
    no_lm = False
    for l in read_file_drop_comments(filename):
        # Extract speaker id and other metadata
        l, metadata = extract_metadata(l)
        if "speaker" in metadata:
            current_speaker = metadata["speaker"]
        else:
            metadata["speaker"] = current_speaker
        
        if "gender" in metadata:
            current_gender = metadata["gender"]
        else:
            metadata["gender"] = current_gender
        
        if "parser" in metadata:
            if "no-lm" in metadata["parser"]: no_lm = True
            elif "add-lm" in metadata["parser"]: no_lm = False
        else:
            if no_lm:
                metadata["parser"] = ["no-lm"]
        if l:
            utterances.append((l, metadata))
    return utterances



def get_text_header(filename) -> Dict:
    metadata = dict()
    for l in read_file_drop_comments(filename):
        l, md = extract_metadata(l)
        metadata.update(md)
        if l:
            # Stop a first sentence
            break
    return metadata



def format_timecode(timecode):
    if isinstance(timecode, int):
        return str(timecode)
    return "{:.3f}".format(timecode).rstrip('0').rstrip('.')



def create_ali_file(sentences, segments, **kwargs) -> str:
    """
        Common header metadata:
            audio-path
            source
            audio-source
            author
            transcription: name of transcribers
            licence
            tags: list of tags separated by commas
    """
    data = []

    if value := kwargs.pop("audio-path", None):
        data.append(f"{{audio-path: {value}}}")
    if value := kwargs.pop("audio_path", None):
        data.append(f"{{audio-path: {value}}}")
    for key, value in sorted(kwargs.items()):
        key = key.replace('_', '-')
        data.append(f"{{{key}: {value}}}")
    data.append("")

    for sentence, segment in zip(sentences, segments):
        start = format_timecode(segment[0])
        end = format_timecode(segment[1])
        data.append(f"{sentence.strip()} {{start: {start}; end: {end}}}")
    
    return '\n'.join(data)



def load_ali_file(filepath) -> Dict:
    """
        Return a dictionary containing the data from an `ali` file :
            audio_path: str,
            sentences: list,
            raw_sentences: list,
            segments: list,
            metadata: list,

    """

    audio_path = None
    header = dict()
    sentences = []       # Text without metadata
    raw_sentences = []   # Text with metadata
    segments = []        # Segments in milliseconds
    metadatas = []

    with open(filepath, 'r', encoding='utf-8') as f:
        # Find associated audio file in metadata
        current_speaker = 'unknown'
        current_gender = 'unknown'
        no_lm = False

        for line in f.readlines():
            line = line.strip()
            if line.startswith('#'):
                continue

            text, metadata = extract_metadata(line)
            if "speaker" in metadata:
                current_speaker = metadata["speaker"]
            else:
                metadata["speaker"] = current_speaker
            
            if "gender" in metadata:
                current_gender = metadata["gender"]
            else:
                metadata["gender"] = current_gender
            
            if "parser" in metadata:
                if "no-lm" in metadata["parser"]: no_lm = True
                elif "add-lm" in metadata["parser"]: no_lm = False
            else:
                if no_lm:
                    metadata["parser"] = ["no-lm"]

            # match = re.search(r"{\s*start\s*:\s*([0-9\.]+)\s*;\s*end\s*:\s*([0-9\.]+)\s*}", line)
            # if match:
            if "start" in metadata and "end" in metadata:
                segments.append([metadata["start"], metadata["end"]])
                sentences.append(text.strip())
                raw_sentences.append(line)
                metadatas.append(metadata)
            elif metadata:
                metadata.pop("speaker", None)
                metadata.pop("gender", None)
                metadata.pop("accent", None)
                header.update(metadata)

            if not audio_path and "audio-path" in metadata:
                dir = os.path.split(filepath)[0]
                audio_path = os.path.join(dir, metadata["audio-path"])
                audio_path = os.path.normpath(audio_path)
        
        # Try to find an associated audiofile if it was not explicitely set in metadata
        if not audio_path:
            audio_path = find_associated_audiofile(filepath, silent=True)
    
    return {
        "audio_path": audio_path,
        "header": header,
        "sentences": sentences,
        "raw_sentences": raw_sentences,
        "segments": segments,
        "metadata": metadatas,
    }



def parse_dataset(file_or_dir, args):
    if (file_or_dir.endswith(".split")
        or file_or_dir.endswith(".seg")
        or file_or_dir.lower().endswith('.ali')
    ):   # Single data item
        return parse_data_file(file_or_dir, args)

    elif os.path.isdir(file_or_dir):
        data = {
            "path": file_or_dir,
            "wavscp": [],   # Recording id to wave filenames
            "utt2spk": [],      # Utterance id to speakers id
            "segments": [],     # Time segments
            "text": [],         # Utterances it to text
            "speakers": set(),  # Speakers names
            "lexicon": set(),   # Word dictionary
            "corpus": set(),    # Sentences for LM corpus
            "audio_length": {'m': 0, 'f': 0, 'u': 0},    # Audio length for each gender
            "subdir_audiolen": {}   # Size (total audio length) for every sub-folders
            }
        
        for filename in sorted(os.listdir(file_or_dir)):
            if filename.startswith('.'):
                # Skip hidden folders
                continue
            if (os.path.isdir(os.path.join(file_or_dir, filename))
                or filename.endswith(".split")
                or filename.endswith(".seg")
                or filename.lower().endswith(".ali")
            ):
                item_data = parse_dataset(os.path.join(file_or_dir, filename), args)
                data["wavscp"].extend(item_data["wavscp"])
                data["utt2spk"].extend(item_data["utt2spk"])
                data["segments"].extend(item_data["segments"])
                data["text"].extend(item_data["text"])
                data["speakers"].update(item_data["speakers"])
                data["lexicon"].update(item_data["lexicon"])
                data["corpus"].update(item_data["corpus"])
                data["subdir_audiolen"][filename] = \
                    item_data["audio_length"]['f'] + \
                    item_data["audio_length"]['m'] + \
                    item_data["audio_length"]['u']
                for k, dur in item_data["audio_length"].items():
                    if k in data["audio_length"]:
                        data["audio_length"][k] += dur
                    else:
                        data["audio_length"][k] = dur

        return data
    else:
        print("File argument must be a split file or a directory")
        return
    


valid_chars = set(VALID_CHARS)
speakers_gender = {"unknown": 'u'}

def parse_data_file(filepath, args):
    print(Fore.GREEN + f" * {filepath}" + Fore.RESET, end=' ', flush=True)
    
    seg_ext = os.path.splitext(filepath)[1] # Could be '.split' or '.seg'
    audio_path = ""

    if seg_ext == ".ali":
        aligned_data = load_ali_file(filepath)
        segments = aligned_data["segments"]
        sentences_and_metadata = list(zip(aligned_data["sentences"], aligned_data["metadata"]))
        audio_path = aligned_data["audio_path"]
    else: # .seg, .split
        text_filename = filepath.replace(seg_ext, '.txt')
        assert os.path.exists(text_filename), f"ERROR: no text file found for {filepath}"
        segments = load_segments_data(filepath)
        sentences_and_metadata = load_text_data(text_filename)
    assert len(sentences_and_metadata) == len(segments), \
        f"number of utterances in text file ({len(data['text'])}) doesn't match number of segments in split file ({len(segments)})"

    
    # Look for accompanying audio file
    if not audio_path:
        audio_path = os.path.abspath(filepath.replace(seg_ext, '.wav'))
        if not os.path.exists(audio_path):
            audio_path = os.path.abspath(filepath.replace(seg_ext, '.mp3'))
    assert os.path.exists(audio_path), f"ERROR: no audio file found for {filepath}"
    
    recording_id = md5(audio_path.encode("utf8")).hexdigest()

    # Use a single random speaker id per file for unknown speakers
    unk_speaker_id = str(uuid4()).replace('-', '')
    

    data = {
        "wavscp": [],       # Recording id to wave filenames
        "utt2spk": [],      # Utterance id to speakers id
        "segments": [],     # Time segments
        "text": [],         # Utterances id to text
        "speakers": set(),  # Speakers names
        "lexicon": set(),   # Word dictionary
        "corpus": set(),    # Sentences for LM corpus
        "audio_length": {'m': 0, 'f': 0, 'u': 0},    # Audio length for each gender
        }
    

    # if not args.split_audio:
    data["wavscp"].append((recording_id, audio_path))

    for (sentence, metadata), (start, end) in zip(sentences_and_metadata, segments):
        if end - start < args.utt_min_len:
            # Skip short utterances
            print(Fore.YELLOW + "dropped (too short): " + Fore.RESET + sentence, file=sys.stderr)
            continue
            
        speaker_id = metadata["speaker"]

        if speaker_id == "unknown":
            speaker_id = unk_speaker_id
        else:
            if args.hash_id:
                speaker_id = md5(speaker_id.encode('utf-8')).hexdigest()
            data["speakers"].add(speaker_id)
        
        utterance_id = f"{speaker_id}-{recording_id}-{floor(100*start):0>7}_{ceil(100*end):0>7}"
        
        if speaker_id not in speakers_gender:
            # speakers_gender is a global variable
            speakers_gender[speaker_id] = metadata["gender"]
        
        cleaned_sentence = pre_process(sentence)
        tokens = list(tokenize(cleaned_sentence, autocorrect=True, norm_punct=False))
        sent = detokenize(normalize(tokens, norm_case=True), normalize=True, capitalize=False)
        
        sent = sent.replace('\xa0', ' ') # Non-breakable spaces
        sent = sent.replace('-', ' ').replace('/', ' ')
        sent = filter_out_chars(sent, PUNCTUATION + '*')
        if not sent:
            continue
        sent = ' '.join(sent.split())
        
        # Filter out utterances with numbers or foreign chars (not counting acronyms)
        sent_no_acronyms = detokenize(
            normalize(
                filter(lambda t: not t.kind == Token.ACRONYM, tokens),
                norm_case=True
            ), normalize=True
        )
        sent_no_acronyms = sent_no_acronyms.replace('\xa0', ' ').replace('*', '')
        chars = set(sent_no_acronyms)
        if not chars.issubset(valid_chars):
            print('\n' + Fore.YELLOW
                + f"dropped (foreign chars '{chars.difference(valid_chars)}'): "
                + Fore.RESET + sentence, end='', file=sys.stderr)
            continue
        
        data["text"].append((utterance_id, sent))
        data["utt2spk"].append((utterance_id, speaker_id))
        data["segments"].append((utterance_id, recording_id, start, end))


        # Keeping track of gender representation
        if metadata["gender"] == 'm':
            data["audio_length"]['m'] += end - start
        elif metadata["gender"] == 'f':
            data["audio_length"]['f'] += end - start
        else:
            data["audio_length"]['u'] += end - start


        # Add words to lexicon
        for word in sent.split():
            # Remove black-listed words (those beggining with '*')
            if word.startswith('*'):
                pass
            elif word in special_tokens:
                pass
            elif word == "'":
                pass
            else: data["lexicon"].add(word)


        # Add sentence to language model corpus
        add_to_text_corpus = True
        if "parser" in metadata:
            if "no-lm" in metadata["parser"]:
                add_to_text_corpus = False
            elif "add-lm" in metadata["parser"]:
                add_to_text_corpus = True
        
        if add_to_text_corpus and not args.no_lm:
            for sub in split_sentences(cleaned_sentence):
                sent = normalize_sentence(sub, autocorrect=True, norm_case=True)
                sent = sent.replace('-', ' ').replace('/', ' ')
                sent = sent.replace('\xa0', ' ')
                sent = filter_out_chars(sent, PUNCTUATION)
                if not sent.strip():
                    continue

                n_stared = sent.count('*')
                tokens = sent.split()
                # Ignore if to many black-listed words in sentence
                if n_stared / len(tokens) > 0.2:
                    if args.verbose:
                        print(Fore.YELLOW + "LM exclude:" + Fore.RESET, sent, end='')
                    continue
                # Remove starred words
                tokens = [tok for tok in tokens if not tok.startswith('*')]
                # Ignore if sentence is too short
                if len(tokens) < args.lm_min_token:
                    if args.verbose:
                        print(Fore.YELLOW + "LM exclude:" + Fore.RESET, sent, end='')
                    continue
                data["corpus"].add(' '.join(tokens))
     
    # status = Fore.GREEN + f" * {filepath[:-6]}" + Fore.RESET
    if data["audio_length"]['u'] > 0:
        print(' ' + Fore.RED + "unknown speaker(s)" + Fore.RESET, end='')
    print()
    return data



def create_eaf(segments, sentences, audiofile, type="wav"):
    """ Export to eaf (Elan) file """

    record_id = os.path.splitext(os.path.abspath(audiofile))[0]
    if type == "mp3":
        mp3_file = os.path.extsep.join((record_id, 'mp3'))
        if not os.path.exists(mp3_file):
            convert_to_mp3(audiofile, mp3_file)
        audiofile = mp3_file

    doc = minidom.Document()

    root = doc.createElement('ANNOTATION_DOCUMENT')
    root.setAttribute('AUTHOR', f'Anaouder {VERSION}')
    root.setAttribute('DATE', datetime.datetime.now(pytz.timezone('Europe/Paris')).isoformat(timespec='seconds'))
    root.setAttribute('FORMAT', '3.0')
    root.setAttribute('VERSION', '3.0')
    root.setAttribute('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.setAttribute('xsi:noNamespaceSchemaLocation', 'http://www.mpi.nl/tools/elan/EAFv3.0.xsd')
    doc.appendChild(root)

    header = doc.createElement('HEADER')
    header.setAttribute('MEDIA_FILE', '')
    header.setAttribute('TIME_UNITS', 'milliseconds')
    root.appendChild(header)

    media_descriptor = doc.createElement('MEDIA_DESCRIPTOR')
    media_descriptor.setAttribute('MEDIA_URL', 'file://' + os.path.abspath(audiofile))
    if type == "mp3":
        media_descriptor.setAttribute('MIME_TYPE', 'audio/mpeg')
    else:
        media_descriptor.setAttribute('MIME_TYPE', 'audio/x-wav')
    media_descriptor.setAttribute('RELATIVE_MEDIA_URL', './' + os.path.basename(audiofile))
    header.appendChild(media_descriptor)

    time_order = doc.createElement('TIME_ORDER')
    last_t = 0
    for i, (s, e) in enumerate(segments):
        s, e = int(s*1000), int(e*1000)
        if s < last_t:
            s = last_t
        last_t = s
        time_slot = doc.createElement('TIME_SLOT')
        time_slot.setAttribute('TIME_SLOT_ID', f'ts{2*i+1}')
        time_slot.setAttribute('TIME_VALUE', str(s))
        time_order.appendChild(time_slot)
        time_slot = doc.createElement('TIME_SLOT')
        time_slot.setAttribute('TIME_SLOT_ID', f'ts{2*i+2}')
        time_slot.setAttribute('TIME_VALUE', str(e))
        time_order.appendChild(time_slot)
    root.appendChild(time_order)

    tier_trans = doc.createElement('TIER')
    tier_trans.setAttribute('LINGUISTIC_TYPE_REF', 'transcript')
    tier_trans.setAttribute('TIER_ID', 'Transcription')

    for i, sentence in enumerate(sentences):
        annotation = doc.createElement('ANNOTATION')
        alignable_annotation = doc.createElement('ALIGNABLE_ANNOTATION')
        alignable_annotation.setAttribute('ANNOTATION_ID', f'a{i+1}')
        alignable_annotation.setAttribute('TIME_SLOT_REF1', f'ts{2*i+1}')
        alignable_annotation.setAttribute('TIME_SLOT_REF2', f'ts{2*i+2}')
        annotation_value = doc.createElement('ANNOTATION_VALUE')
        #text = doc.createTextNode(get_cleaned_sentence(sentence, rm_bl=True, keep_dash=True, keep_punct=True)[0])
        text = doc.createTextNode(sentence.replace('*', ''))
        annotation_value.appendChild(text)
        alignable_annotation.appendChild(annotation_value)
        annotation.appendChild(alignable_annotation)
        tier_trans.appendChild(annotation)
    root.appendChild(tier_trans)

    linguistic_type = doc.createElement('LINGUISTIC_TYPE')
    linguistic_type.setAttribute('GRAPHIC_REFERENCES', 'false')
    linguistic_type.setAttribute('LINGUISTIC_TYPE_ID', 'transcript')
    linguistic_type.setAttribute('TIME_ALIGNABLE', 'true')
    root.appendChild(linguistic_type)

    language = doc.createElement('LANGUAGE')
    language.setAttribute("LANG_ID", "bre")
    language.setAttribute("LANG_LABEL", "Breton (bre)")
    root.appendChild(language)

    constraint_list = [
        ("Time_Subdivision", "Time subdivision of parent annotation's time interval, no time gaps allowed within this interval"),
        ("Symbolic_Subdivision", "Symbolic subdivision of a parent annotation. Annotations refering to the same parent are ordered"),
        ("Symbolic_Association", "1-1 association with a parent annotation"),
        ("Included_In", "Time alignable annotations within the parent annotation's time interval, gaps are allowed")
    ]
    for stereotype, description in constraint_list:
        constraint = doc.createElement('CONSTRAINT')
        constraint.setAttribute('DESCRIPTION', description)
        constraint.setAttribute('STEREOTYPE', stereotype)
        root.appendChild(constraint)

    xml_str = doc.toprettyxml(indent ="\t", encoding="UTF-8")

    return xml_str.decode("utf-8")



def convert_from_eaf(eaf_filename):
    """ Write a split file and a text file from an eaf file """
    
    abs_path = os.path.abspath(eaf_filename)
    rep, eaf_filename = os.path.split(abs_path)
    
    print(rep, eaf_filename)
    print(abs_path)
    doc = minidom.parse(abs_path)
    root = doc.firstChild

    segments = []

    def getText(nodelist):
        rc = []
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return ''.join(rc)

    header = root.getElementsByTagName("HEADER")[0]
    md = header.getElementsByTagName("MEDIA_DESCRIPTOR")[0]
    wav_rel_path = md.getAttribute("RELATIVE_MEDIA_URL")

    wav_filename = os.path.normpath(os.path.join(rep, wav_rel_path))
    record_id = wav_filename.split(os.path.extsep)[0]
    text_filename = os.path.extsep.join((record_id, 'txt'))
    split_filename = os.path.extsep.join((record_id, 'split'))
    
    if os.path.exists(split_filename):
        print("Split file already exists.")
        while True:
            r = input("Replace (y/n)? ")
            if r.startswith('n'):
                print("Aborting...")
                return
            elif r.startswith('y'):
                break
    if not os.path.exists(wav_filename):
        print(f"Couldn't find '{wav_filename}'. Aborting...")
        return

    print("rep", rep)
    print("path", text_filename)

    time_order = root.getElementsByTagName("TIME_ORDER")[0]
    time_slots = time_order.getElementsByTagName("TIME_SLOT")
    time_slot_dict = {}
    for ts in time_slots:
        time_slot_dict[ts.getAttribute("TIME_SLOT_ID")] = int(ts.getAttribute("TIME_VALUE"))

    tiers = root.getElementsByTagName("TIER")
    for tier in tiers:
        if tier.getAttribute("TIER_ID").lower() in ("transcription", "default") :
            annotations = tier.getElementsByTagName("ANNOTATION")
            for annotation in annotations:
                aa = annotation.getElementsByTagName("ALIGNABLE_ANNOTATION")[0]
                ts1 = aa.getAttribute("TIME_SLOT_REF1")
                ts2 = aa.getAttribute("TIME_SLOT_REF2")
                time_seg = (time_slot_dict[ts1], time_slot_dict[ts2])
                text = getText(aa.getElementsByTagName("ANNOTATION_VALUE")[0].childNodes)
                segments.append((time_seg, text))
                #print(f"SEG: {time_seg} {text}")

    with open(text_filename, 'w', encoding='utf-8') as f:
        f.write('#\n' * 4 + '\n' * 6)
        for _, sentence in segments:
            f.write(sentence + '\n')
    with open(split_filename, 'w', encoding='utf-8') as f:
        for (s, e), _ in segments:
            f.write(f"{s} {e}\n")




##############################  METADATA  ##############################

METADATA_PATTERN = re.compile(r'{\s*(.+?)\s*}') # Capture content
METADATA_UNIT_PATTERN = re.compile(r"([\w\s:,_'’/=\.\-\?\&]+)") # Capture content except ';'
SPEAKER_NAME_PATTERN = re.compile(r"(?:(?:spk|speaker)\s*:\s*)?([\w '_-]+?)")
SPEAKER_ID_PATTERN_DEPR = re.compile(r'([-\'\w]+):*([mf])*')
KEYVAL_PATTERN = re.compile(r"([\w_'-]+)\s*:\s*([\w ,_'’.:/-]+?)\s*")

_VALID_PARAMS = {
    "source",
    "source-audio", "audio-source",
    "audio-path",
    "author", "authors",
    "licence",
    "modifications",
    "transcription",
    "tags",
    "parser",
    "speaker", "spk",
    "gender",
    "lang",
    "accent",
    "start", "end",
#    "phon",
}


def extract_metadata(sentence: str) -> Tuple[str, dict]:
    """ Returns the sentence stripped of its metadata (if any)
        and a dictionary of metadata
        Keeps unknown word markers '{?}'
    """
    metadata = dict()
    remove_ranges = []

    for match in METADATA_PATTERN.finditer(sentence):
        start, end = match.span()
        content = match.group(1).strip()
        if content == '?':       # Unknown words {?}
            if "unknown" not in metadata: metadata["unknown"] = []
            sub = sentence[:end]
            metadata["unknown"].append(len(sub.split())-1) # word number
        else:
            remove_ranges.append((start, end))
            metadata_units = content.split(';')
            for unit in metadata_units:
                unit = unit.strip()
                if ':' in unit:
                    # Key-value pair
                    key, val = unit.split(':', maxsplit=1)
                    key = key.strip()
                    val = val.strip()

                    if key in _VALID_PARAMS:
                        if key in ("speaker", "spk"):
                            key = "speaker"
                            if not val.isupper():
                                val = val.replace(' ', '_').lower()
                        if key in ("tags", "author", "accent"):
                            val = [v.strip().replace(' ', '_') for v in val.split(',') if v.strip()]
                        if key in ("start", "end"):
                            val = float(val)
                        metadata[key] = val
                    else:
                        speaker_name_depr = SPEAKER_ID_PATTERN_DEPR.fullmatch(unit)
                        if speaker_name_depr:
                            print(Fore.RED + f"Deprecated metadata: {unit}" + Fore.RESET)
                            metadata["speaker"] = speaker_name_depr.group(1)
                            if speaker_name_depr.group(2) in 'fm':
                                metadata["gender"] = speaker_name_depr.group(2)
                        else:
                            print(Fore.RED + f"Wrong metadata: {unit}" + Fore.RESET)
                else:
                    # A simplified speaker name
                    if not unit.isupper():
                        # Keep all-caps names (Acronyms)
                        unit = unit.replace(' ', '_').lower()
                    metadata["speaker"] = unit

    nchars_removed = 0
    for start, end in remove_ranges:
        sentence = sentence[:start-nchars_removed] + sentence[end-nchars_removed:]
        nchars_removed += end-start
    
    return sentence.strip(), metadata
