
from math import inf, ceil
from pydub import AudioSegment
from pydub.utils import get_player_name
from pydub.silence import detect_nonsilent

    

# def get_min_max_energy(segment: AudioSegment, chunk_size=100, overlap=50):
#     """ Return the minimum dBFS of the segment, wich is above -inf.
#         chunk_size and overlap in milliseconds
#     """
#     min_energy = 0
#     max_energy = -999

#     for i in range(0, len(segment), chunk_size-overlap):
#         chunk = segment[i: i+chunk_size]  # Pydub will take care of overflow
#         energy = chunk.dBFS
#         if energy > -inf:
#             min_energy = min(min_energy, energy)
#         max_energy = max(max_energy, energy)

#     return min_energy, max_energy

def get_min_max_energy(segment: AudioSegment, chunk_size=100, overlap=50):
    """ Return the minimum dBFS of the segment, wich is above -inf.
        chunk_size and overlap in milliseconds
    """
    max_energy = -999
    energy_bins = dict()

    for i in range(0, len(segment), chunk_size-overlap):
        chunk = segment[i: i+chunk_size]  # Pydub will take care of overflow
        if chunk.dBFS == -inf:
            continue
        energy = round(chunk.dBFS)
        if energy in energy_bins:
            energy_bins[energy] += 1
        else:
            energy_bins[energy] = 1
        max_energy = max(max_energy, energy)
    
    bins_list = sorted(energy_bins.items())
    n_thresh = ceil(sum(energy_bins.values()) / 1000)

    for e, n in bins_list:
        if e <= -80: continue
        if n < n_thresh: continue
        min_energy = e
        break

    return min_energy, max_energy



def _recursive_split(song: AudioSegment, segment: list, max_length=15, min_silence_len=300):
    start, end = segment
    if (end-start) / 1000 < max_length:
        # Segment's length is short enough
        return [segment]

    min_e, max_e = get_min_max_energy(song[start:end])
    delta_e = max_e - min_e
    thresh = min_e + delta_e / 6.5
    sub_segments = detect_nonsilent(song[start:end], min_silence_len=min_silence_len, silence_thresh=thresh)

    # Filter out segments too short (< 0.8s)
    sub_segments = [ sub for sub in sub_segments if sub[1]-sub[0] > 800 ]

    if len(sub_segments) == 1:
        s, e = sub_segments[0]
        if e-s > max_length:
            # Sub divide a second time, if necessary
            min_e, max_e = get_min_max_energy(song[s:e])
            delta_e = max_e - min_e
            thresh = min_e + delta_e / 5
            sub2 = detect_nonsilent(song[s:e], min_silence_len=150, silence_thresh=thresh)
            return [ [start+s, start+e] for s, e in sub2 ]
        else:
            return [[start+s, start+e]]

    result = []
    for seg in sub_segments:
        result.extend(_recursive_split(song, [start + seg[0], start + seg[1]]))
    sub_segments = result

    return result



def split_to_segments(song: AudioSegment, max_length=15, min_length=5):
    """
        Return a list of sub-segments from a pydub AudioSegment
        Sub-segments are represented as 2-elements lists:
            [start, end]
        Where 'start' and 'end' are in milliseconds
    """
    segments: list = _recursive_split(song, [0, len(song)], max_length=max_length)

    # Extend segments length
    for i, seg in enumerate(segments[1:]):
        prev = segments[i]
        gap = seg[0] - prev[1]
        if 100 < gap < 1000:
            prev[1] += gap // 2 - 50
            seg[0] -= gap // 2 - 50

    # Concatenate short segments
    result = [segments[0]]
    for i, seg in enumerate(segments[1:]):
        prev = segments[i]
        prev_length = prev[1]-prev[0]
        seg_length = seg[1]-seg[0]
        gap = seg[0] - prev[1]
        
        if gap < 500 and prev_length + seg_length < min_length*1000:
            # Extend previous segment with this segment
            result[-1][1] = seg[1]
        else:
            result.append(seg)

    return result
