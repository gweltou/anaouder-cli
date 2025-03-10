from os import path
from setuptools import setup, find_packages
from anaouder.version import VERSION


NAME = "anaouder"
DESCRIPTION = "Breton language speech-to-text tools"
URL = "https://github.com/gweltou/vosk-br"
AUTHOR = "Gweltaz Duval-Guennoc"
EMAIL = "gweltou@hotmail.com"
REQUIRES_PYTHON = ">=3.6.0"


# The directory containing this file
HERE = path.dirname(__file__)

with open(path.join(HERE, "requirements.txt")) as fd:
    REQUIREMENTS = [line.strip() for line in fd.readlines() if line.strip()]


setup(
    name=NAME,
    url=URL,
    version=VERSION,
    author=AUTHOR,
    license="MIT",
    author_email=EMAIL,
    description=DESCRIPTION,
    long_description=open("README-fr.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=REQUIRES_PYTHON,
    install_requires=REQUIREMENTS,
    classifiers=[
		"Intended Audience :: Developers",
		"License :: OSI Approved :: MIT License",
		"Programming Language :: Python",
		"Programming Language :: Python :: 3",
		"Programming Language :: Python :: 3.6",
		"Programming Language :: Python :: 3.7",
		"Programming Language :: Python :: 3.8",
		"Programming Language :: Python :: 3.9",
		"Operating System :: OS Independent"
	],
    packages=find_packages(),
    # package_dir={"anaouder": "anaouder", "ostilhou": "anaouder/ostilhou"},
    package_data={
        "anaouder": [
            "asr/inorm_units.tsv",
            "asr/postproc_sub.tsv",
            "dicts/acronyms.tsv",
            "dicts/corrected_tokens.tsv",
            "dicts/first_names.tsv",
            "dicts/last_names.tsv",
            "dicts/noun_f.tsv",
            "dicts/noun_m.tsv",
            "dicts/places.tsv",
            "dicts/proper_nouns_phon.tsv",
            "dicts/standard_tokens.tsv",
            "text/moses_br.txt",
        ]
    },
    data_files=[('', ["README.md", "README-fr.md", "CHANGELOG.md"])],
    entry_points={
        "console_scripts": [
            "adskrivan = anaouder.adskrivan:main_adskrivan",
            "linennan = anaouder.linennan:main_linennan",
            "istitlan = anaouder.istitlan:main_istitlan",
            "mikro = anaouder.mikro:main_mikro",
            "normalizan = anaouder.normalizan:main_normalizan",
        ],
    },
)
