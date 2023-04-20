#!/usr/bin/env python3

from vosk import Model, KaldiRecognizer, SetLogLevel
import sys
import os
import wave
import argparse
from ostilhou.asr.post_processing import post_process_text


def format_output(result, normalize=False):
    sentence = eval(result)["text"]
    sentence = post_process_text(sentence, normalize)
    return sentence



if __name__ == "__main__":
    desc = f"Decode an audio file in any format, with the help of ffmpeg"
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('filename')
    parser.add_argument("-m", "--model", default="model/vosk-model-br-0.7", help="Vosk model to use for decoding", metavar='MODEL_PATH')
    parser.add_argument("-n", "--normalize", help="Normalize numbers", action="store_true")
    args = parser.parse_args()

    SAMPLE_RATE = 16000

    SetLogLevel(-1)

    model = Model(args.model)
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)

    wf = wave.open(args.filename, "rb")
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
        print ("Audio file must be WAV format mono PCM.")
        sys.exit(1)

    while True:
        data = wf.readframes(4000)   # skip header
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            print(format_output(rec.Result(), normalize=args.normalize))
    print(format_output(rec.FinalResult(), normalize=args.normalize))