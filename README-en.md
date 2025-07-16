[![pypi version](https://img.shields.io/pypi/v/anaouder)](https://pypi.org/project/anaouder/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

# Anaouder


<img src="assets/gwenn_ha_du_128x85.png" alt="Breton flag" width="16" /> [E brezhoneg](README.md) | 🇫🇷 [ Lire en français](README-fr.md) | 🇬🇧 Read in English


Speech recognition for Breton using Vosk.

This project is developed by volunteers. You can support it with a donation:
[![Liberapay](https://liberapay.com/assets/widgets/donate.svg)](https://liberapay.com/gweltou/donate)

An [online version](https://translate.bzh/), developed by Philippe Argouarch, is also available.

## About

Speech recognition model (*speech-to-text*) trained using the [Kaldi](https://www.kaldi-asr.org/) framework, in [Vosk](https://github.com/alphacep/vosk-api) format.\
It comes with scripts allowing automatic transcription of audio and video files, text/sound alignment for the creation of subtitles, or even realtime transcription of microphone input.

Principal advantages:

* **Lightweight**. Vosk models are smaller than 100MB and run on a large range of devices: computers **without GPUs***, RaspberryPi, Android smartphones...
* **Fast**. Inference is done in **realtime**, even on an old machine.
* **Local**. Works without an internet connection. Your data stays on your device.
* **Free and open source**. The MIT licence allows you to modify the code and integrate it into other applications.

The number of hours of recorded audio used to train the model is relatively small, but is increasing little by little.
Outside of Mozilla's [Common Voice](https://commonvoice.mozilla.org/br) project, [freely licensed](https://creativecommons.org/licenses/) transcribed audio recordings in Breton are rare. Any help in this area would be welcome!

## Installation

The scripts require [Python3](https://www.python.org/downloads/). Install the speech recognition module via the terminal:
```bash
pip3 install anaouder
```

When new versions of the model are available you can update the package with the command:

```bash
pip3 install --upgrade anaouder
```


## Transcribe an audio or video file

Once installed, the  `adskrivan` command allows you to transcribe audio or video files from the terminal. On the first run, you will need to wait for the installation of the `static_ffmpeg` module (used for media file format conversion). This will only happen once.

```bash
adskrivan FILENAME
```

The resulting transcription will appear in the terminal by default. You can also save it to a specified file with the `-o` option:

```bash
adskrivan FILENAME -o OUPUT.txt
```

## Use with a microphone

From the terminal, use the `mikro` command.

If no text appears, you can list available audio interfaces with:

```bash
mikro -l
```

You can then specify the desired interface by number:

```bash
mikro -d INTERFACE_NUMBER
```

## Align text to audio

You can align a text file to an audio or video file using the `linennan` command. This generates an `srt` subtitle file (Subrip format) with timestamps.\
The text file much be plain text (.txt) with one line per subtitle block:

```bash
linennan AUDIO_OR_VIDEO_FILE TEXTFILE -o subtitles.srt
```

(Export to `eaf` for  ELAN, is coming soon...)

## Automatically creat subtitles

You can also automatically generate subtitles by transcibing speech from an audio or video file into `srt` (Subrip) format:

```bash
istitlan AUDIO_OR_VIDEO_FILE
```

## Using the model with other software


*It is possible to use the raw model with other applications, but this is not recommended, as it bypasses post-processing features included in the `anaouder` module, such as hyphen restoration and number normalization.*

The raw model is located in `anaouder/models` or can be downloaded from the [releases page](https://github.com/gweltou/vosk-br/releases).

### Audapolis

The model can be used with [Audapolis](https://github.com/bugbakery/audapolis), which provides a graphical interface (GUI).

### Kdenlive

The video editor [Kdenlive](https://kdenlive.org/) supports Vosk models for automatic subtitle generation.
See the [documentation](https://docs.kdenlive.org/en/effects_and_compositions/speech_to_text.html).

## Acknowledgements

This tool was made possible thanks to the open source software on which it is built: Kaldi, Vosk and the [Hunspell Breton spellchecker](https://github.com/Drouizig/hunspell-br) from An Drouizig.\
The model could not have been trained without the voices and texts of many contributors, including:
Becedia, Brezhoweb, Dastum, Dizale, Kaouen.net, Mozilla Common Voice, RKB et l'Ofice Public de la Langue Bretonne\
Special thanks to Elen Cariou, Jean-Mari Ollivier, Karen Treguier, Mélanie Jouitteau, Pêr Morvan and the association An Drouizig for their help and support.
