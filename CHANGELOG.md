# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.4]

- New english translated README file (thanks to @kassschmitt)
- New `--return-after` parameter (program returns after first utterance)

## [1.0.3] 2025-03-12

- Fix mikro and normalizan command
- Fix missing dependency
- Fix timecodes in eaf

## [1.0.0] 2025-03-02

- Sync with online model database.
- JSON output in `adskrivan` (with `-t json` option).
- New audio segmentation algorithm.
- Inverse-normalize option is set by default.
- Fixed absent hyphens from subtitles.
- Updated dictionaries.
- Removed `--translate` option from `mikro`.

## [0.9.8] - 2024-11-7

- Changed option `--max_words_per_line` to `--max-words-per-line`
- Fixed utf-8 decoding of dictionaries on macOS.

## [0.9.6]

- Improved alignment algorithm in `linennan`.
- `ali` file format compatibility with `adskrivan` and `linennan`.

## [0.9.5] - 2024-06-03

- Fixed model selection when outputing to a txt file.
- Fixed inference with progress bar for MKV files.
- Fixed MacOS compatibility issue when downloading models.

## [0.9.2] - 2024-05-14

- Better segmentation when decoding to a text file with `-o/--output` option.
- Shows a progress bar when decoding to a text file with `-o/--output` option.
- Included Anaouder version in EAF headers.
- Removed optional use of translation dictionaries.

## [0.9.0] - 2024-03-09

- Updated Vosk STT model to v0.9.
- Auto-downloading of models online if not available locally.
- Progress bars with `tqdm`.

## [0.8.4]

- Automatically converts to wave and keep fillers when creating 'split' files.
- Fixed argument propagation error in istitlan.

## [0.8.3]

- Fixed missing module `pytz`

## [0.8.2]

- Export to `EAF` (Elan) files.
- Option `--autosplit` (adaptative splitting of audio file at silences).
- Option `--set-ffmpeg-path` to define the path to ffmpeg explicitely.
- Option `-v/--version` to show the version of the module.

## [0.8.1]

- Fixed dependency in `normalizan` script.

## [0.8.0] - 2023-08-16

- `normalizan` command will normalize a text file or whatever is sent through stdin.
- Updated STT model to v0.8.

## [0.7.12]

- Added option `--keep-fillers` that allows verbal fillers ('euh', 'ebeñ', 'kwa', 'alors'...) in transcriptions.

## [0.7.11]

- Changed option `-d/--translate` to `--translate` because of conflicting '-d' option in `mikro.py`. script.
- Bufixes in script `mikro.py` from @Tornaod

## [0.7.10]

- Fixed setup.py to include non python file, broken by the new folder hierarchy.

## [0.7.9]

- Options `-o/--output` (output file) and `-d/--translate` (translate words using a tsv file) added to `adskrivan`, `istitlan` and `mikro` scripts.
- Simplified folder hierarchy.
- The scripts can now be called with the python interpreter.

## [0.7.8]

- First version uploaded to pypi.org
