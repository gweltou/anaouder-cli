#!/usr/bin/env python3

import sys
import argparse
import queue
import sounddevice as sd

import static_ffmpeg
from vosk import KaldiRecognizer

from anaouder.asr.models import load_model, get_latest_model
from anaouder.asr.post_processing import post_process_text
from anaouder.text import tokenize, detokenize
from anaouder.version import VERSION



def int_or_str(text):
	"""Helper function for argument parsing."""
	try:
		return int(text)
	except ValueError:
		return text


def callback(indata, frames, time, status):
	"""This is called (from a separate thread) for each audio block."""
	if status:
		print(status, file=sys.stderr)
	q.put(bytes(indata))


def format_output(sentence, normalize=False, keep_fillers=False):
	sentence = post_process_text(sentence, normalize, keep_fillers)
	return sentence


def main_mikro() -> None:
	""" mikro cli entry point """

	global q

	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-l', '--list-devices', action='store_true',
		help='show list of audio devices and exit')
	args, remaining = parser.parse_known_args()
	if args.list_devices:
		print(sd.query_devices())
		parser.exit(0)
	parser = argparse.ArgumentParser(
		description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter,
		parents=[parser])
	parser.add_argument("-o", "--output", type=str, metavar='FILENAME',
		help='text file to store transcriptions')
	parser.add_argument('-m', '--model', type=str, metavar='MODEL_PATH', default=get_latest_model("vosk"),
		help='Path to the model')
	parser.add_argument('-d', '--device', type=int_or_str,
		help='input device (numeric ID or substring)')
	parser.add_argument('-r', '--samplerate', type=int,
		help='sampling rate')
	parser.add_argument('-n', '--normalize', action="store_true",
		help="Normalize numbers")
	parser.add_argument("--translate", nargs='+',
		help="Use additional translation dictionaries")
	parser.add_argument("--keep-fillers", action="store_true",
		help="Keep verbal fillers ('euh', 'beñ', 'alors', 'kwa'...)")
	parser.add_argument("--return-after", action="store_true", help="program returns after the first and only utterance")
	parser.add_argument("-v", "--version", action="version", version=f"%(prog)s v{VERSION}")
	args = parser.parse_args(remaining)

	# Use static_ffmpeg instead of ffmpeg
	static_ffmpeg.add_paths()
	
	q = queue.Queue()

	try:
		if args.samplerate is None:
			device_info = sd.query_devices(args.device, 'input')
			# soundfile expects an int, sounddevice provides a float:
			args.samplerate = int(device_info['default_samplerate'])

		model = load_model(args.model)

		if args.output:
			dump_fn = open(args.output, "w")
		else:
			dump_fn = None

		with sd.RawInputStream(samplerate=args.samplerate, blocksize = 1024, device=args.device, dtype='int16',
								channels=1, latency='high', callback=callback):
				print('[Press Ctrl+C to stop the recording]', file=sys.stderr)
				
				rec = KaldiRecognizer(model, args.samplerate)
				
				while True:
					data = q.get()
					if rec.AcceptWaveform(data):
						result = eval(rec.Result())["text"]
						if len(result) > 0:
							formatted = format_output(result, normalize=not args.normalize, keep_fillers=args.keep_fillers)
							print(formatted)
							if dump_fn:
								dump_fn.write(formatted+'\n')
							if args.return_after:
								break

	except KeyboardInterrupt:
		print('\nDone')
		parser.exit(0)
	except Exception as e:
		parser.exit(type(e).__name__ + ': ' + str(e))


if __name__ == "__main__":
	main_mikro()
