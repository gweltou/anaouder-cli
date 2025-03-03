from typing import List, Optional

import sys
import subprocess
import json
import os.path
from os import listdir
from random import choice
from tempfile import NamedTemporaryFile

from colorama import Fore

from pydub import AudioSegment
from pydub.utils import get_player_name
from pydub.generators import WhiteNoise


AUDIO_FORMATS = ('wav', 'mp3', 'm4a', 'ogg', 'mp4', 'mkv')


def find_associated_audiofile(path: str, silent=False) -> Optional[str]:
    basename, _ = os.path.splitext(path)

    for ext in AUDIO_FORMATS:
        audio_path = os.path.extsep.join((basename, ext))
        if os.path.exists(audio_path):
            if not silent:
                print("Found audio file:", audio_path)
            return audio_path
    print(Fore.RED + f"Could not find {audio_path}" + Fore.RESET, file=sys.stderr)
    return None



def load_audiofile(path: str, sr=16000) -> AudioSegment:
    data = AudioSegment.from_file(path)
    data = prepare_segment_for_decoding(data)
    return data



def get_audio_segment(i, audio: AudioSegment, segments):
    """
    Args:
        i (int) : an index
        audio (AudioSegment)
        segments: list of tuple of floats (seconds)
    """
    start = int(segments[i][0] * 1000)
    stop = int(segments[i][1] * 1000)
    seg = audio[start: stop]
    return seg



def audio_segments(audio, segments):
    for start, stop in segments:
        yield audio[start, stop]



def prepare_segment_for_decoding(segment: AudioSegment) -> AudioSegment:
    """ Ensure that the segment is the right sampling rate and depth """

    if segment.channels > 1:
        segment = segment.set_channels(1)
    if segment.frame_rate != 16000:
        segment = segment.set_frame_rate(16000)
    if segment.sample_width != 2:
        segment = segment.set_sample_width(2)
    return segment



def play_audio_segment(i, song, segments, speed):
    play_with_ffplay(get_audio_segment(i, song, segments), speed)



def get_audiofile_info(filename) -> dict:
    r = subprocess.check_output(['ffprobe', '-hide_banner', '-v', 'panic', '-show_streams', '-of', 'json', filename])
    r = json.loads(r)
    return r['streams'][0]



def get_audiofile_length(filename) -> float:
    """ Get audio file length in seconds """
    info = get_audiofile_info(filename)
    if "duration" in info:
        return float(info["duration"])
    elif "tags" in info:
        # For MKV files
        h, m, s = info["tags"]["DURATION"].split(':')
        return float(h) * 3600 + float(m) * 60 + float(s)



def is_audiofile_valid_format(filename) -> bool:
    """ Returns True if audio file is 16KHz s16le PCM """
    info = get_audiofile_info(filename)
    if info["codec_name"] != "pcm_s16le":
        return False
    if info["sample_rate"] != "16000":
        return False
    if info["channels"] != 1:
        return False
    return True


    
def play_with_ffplay(seg, speed=1.0):
    with NamedTemporaryFile("w+b", suffix=".wav") as f:
        seg.export(f.name, "wav")
        player = get_player_name()
        p = subprocess.Popen(
            [player, "-nodisp", "-autoexit", "-loglevel", "quiet", "-af", f"atempo={speed}", f.name],
        )
        p.wait()



def convert_to_wav(src, dst, verbose=True, keep_orig=True):
    """
        Convert to 16kHz s16le mono PCM

        Parameters
        ----------
            verbose (bool):
                Info text to stdout
            keep_orig (bool):
                keep  original file (or rename if src and dst are the same)
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if src == dst:
        # Rename original audio file (to keep it)
        rep, filename = os.path.split(src)
        basename, ext = os.path.splitext(filename)
        new_name = basename + "_orig" + ext
        new_src = os.path.join(rep, new_name)
        if verbose: print(Fore.YELLOW + f"AUDIO_CONV: renaming {filename} to {new_name}" + Fore.RESET)
        os.rename(src, new_src)
        src = new_src

    if verbose:
        print(Fore.YELLOW + f"AUDIO_CONV: converting '{src}' to '{dst}'..." + Fore.RESET)
    rep, filename = os.path.split(dst)
    dst = os.path.join(rep, filename)
    subprocess.call([
            'ffmpeg', '-v',
            'panic',
            '-i', src,
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            dst
        ])

    if not keep_orig:
        if verbose:
            print(Fore.YELLOW + f"AUDIO_CONV: Removing {src}" + Fore.RESET)
        os.remove(src)



def convert_to_mp3(src, dst, verbose=True, keep_orig=True):
    """ Convert to MP3 """
    if verbose:
        print(Fore.YELLOW + f"AUDIO_CONV: converting '{src}' to '{dst}'..." + Fore.RESET)
        
    if os.path.abspath(src) == os.path.abspath(dst):
        print(Fore.RED + "ERROR: source and destination are the same, skipping" + Fore.RESET)
        return -1
    rep, filename = os.path.split(dst)
    dst = os.path.join(rep, filename)
    subprocess.call(['ffmpeg', '-v', 'panic',
                     '-i', src,
                     '-ac', '1', dst])
    
    if not keep_orig:
        if verbose:
            print(Fore.YELLOW + f"AUDIO_CONV: Removing {src}")
        os.remove(src)



def concatenate_audiofiles(file_list, out_filename, remove=False):
    """ Concatenate a list of audio files to a single audio file

        Parameters
        ----------
            remove (bool):
                remove original files
    """

    if len(file_list) <= 1:
        return
    
    file_list_filename = "audiofiles.txt"
    with open(file_list_filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join([f"file '{wav}'" for wav in file_list]))
    
    subprocess.call(['ffmpeg', '-v', 'panic',
                     '-f', 'concat',
                     '-safe', '0',
                     '-i', file_list_filename,
                     '-c', 'copy', out_filename])
    os.remove(file_list_filename)
    
    if remove:
        for fname in file_list:
            os.remove(fname)



def export_segment(audio_path: str, start: float, end: float, new_path: str):
    """ Split an audiofile in many segments

        Arguments:
            audio_path (str): the path of the original audiofile
            start (float) : time offset of beginning of segment
            end (float) : time offset of end of segment
            new_path (str): path of output file
    """
    # Cut the audio into segments using FFmpeg and suppress output
    subprocess.run([
        "ffmpeg",
        "-i", audio_path,
        "-ss", str(start),
        "-to", str(end),
        "-c", "copy", # Write using the same codec
        new_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)



def get_min_max_energy(segment: AudioSegment, chunk_size=100, overlap=50):
    """Return the min and max RMS energy value for this audio segment"""
    min_energy = segment.max_possible_amplitude
    max_energy = 0
    for i in range(0, len(segment), chunk_size-overlap):
        chunk = segment[i: i+chunk_size]  # Pydub will take care of overflow
        mean = chunk.rms
        if mean < min_energy:
            min_energy = mean
        if mean > max_energy:
            max_energy = mean
    return (min_energy, max_energy)



def binary_split(audio: AudioSegment, treshold_ratio=0.1):
    min_e, max_e = get_min_max_energy(audio)
    delta_e = max_e - min_e
    thresh = min_e + delta_e * treshold_ratio

    # Find segments above the energy threshold
    chunk_size = 100 # millisec
    overlap = 50 # millisec
    segments = []
    seg_start = 0 # millisec
    in_noisy_chunk = False
    for i in range(0, len(audio), chunk_size-overlap):
        chunk = audio[i: i+chunk_size]  # Pydub will take care of overflow
        if chunk.rms >= thresh:
            if not in_noisy_chunk:
                seg_start = i
                in_noisy_chunk = True
        else:
            if in_noisy_chunk:
                segments.append((seg_start, i+chunk_size))
                in_noisy_chunk = False
    if in_noisy_chunk:
        segments.append((seg_start, len(audio)))

    if not segments:
        return segments
    # Find longest silence between segments
    max_sil_length = 0
    max_sil_length_idx = -1
    for i in range(1, len(segments)):
        sil_length = segments[i][0] - segments[i-1][1]
        if sil_length > max_sil_length:
            max_sil_length = sil_length
            max_sil_length_idx = i

    if max_sil_length_idx > 0:
        left_seg = (segments[0][0], segments[max_sil_length_idx-1][1])
        right_seg = (segments[max_sil_length_idx][0], segments[-1][1])
        return [left_seg, right_seg]
    return []



def split_to_segments(audio: AudioSegment, max_length=10, threshold_ratio=0.1) -> List:
    """
    Return a list of shorter sub-segments from a pydub AudioSegment.

    Sub-segments are represented as 2-elements lists [start, end]
    where 'start' and 'end' are in milliseconds.

    Parameters
    ----------
        max_length (float):
            sub-segments maximum length (in seconds)
        threshold_ratio (0.0 < float < 1.0):
            the silence threshold (depending on min/max energy of the audio segment)
    """
    segments_stack = [(0, len(audio))]
    short_segments = []

    while segments_stack:
        segment = segments_stack.pop()
        start, end = segment
        seg_len = end - start
        if seg_len <= max_length * 1000:
            short_segments.append(segment)
            continue
        sub_segments = binary_split(audio[start:end], threshold_ratio)
        segments_stack.extend([ (start + s, start + e) for s, e in sub_segments ])
    
    return sorted(short_segments)