from typing import List

import os
import sys
import platform
import json

import ssl
import certifi
import urllib
import zipfile
from tqdm import tqdm

from vosk import Model, SetLogLevel



MODEL_LIST_URL = "https://raw.githubusercontent.com/gweltou/patromou/refs/heads/main/model_list.json"
_certifi_context = ssl.create_default_context(cafile=certifi.where())

_model_list = None
_loaded_model = None
_loaded_model_name = ""



def _get_model_directory() -> str:
    if platform.system() in ("Linux", "Darwin"):
        default = os.path.join(os.path.expanduser("~"), ".cache")
    elif platform.system() == "Windows":
        default = os.getenv("LOCALAPPDATA")
    else:
        raise OSError("Unsupported operating system")
    model_dir = os.path.join(os.getenv("XDG_CACHE_HOME", default), "anaouder", "models")
    
    if not os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)
    
    return model_dir

_model_root = _get_model_directory()



def _get_model_list():
    global _model_list
    if _model_list:
        return _model_list

    cached_path = os.path.join(_model_root, "model_list.json")

    try:
        _model_list = json.load(urllib.request.urlopen(MODEL_LIST_URL, timeout=4, context=_certifi_context))
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        print(f"Cannot access online model list: {error}", file=sys.stderr)
        print(f"Reverting to cached model list", file=sys.stderr)
        _model_list = json.load(open(cached_path, 'r'))
    else:
        # Save a cached copy of `model_list.json`
        cached_model_list = []
        if os.path.exists(cached_path):
            try:
                cached_model_list = json.load(open(cached_path, 'r'))
            except json.JSONDecodeError:
                pass
        if _model_list != cached_model_list:
            json.dump(_model_list, open(cached_path, 'w'))
    return _model_list



def get_all_models() -> List[str]:
    """
    Returns the names of available models online
    """
    models = _get_model_list()
    return [ model['name'] for model in models ]



def get_local_models() -> List[str]:
    """
    Returns the names of locally available models
    """
    valid_models = []
    for f in os.listdir(_model_root):
        path = os.path.join(_model_root, f)
        if _is_valid_vosk_model(path):
            valid_models.append(f)
    return valid_models



def get_latest_model(type=None) -> str:
    models = sorted(_get_model_list(), key=lambda m: m["version"], reverse=True)
    if type:
        models = list(filter(lambda m: m["type"]==type, models))
    return models[0]["name"]



_MODEL_ALIASES = {
    "vosk-br-0.6": "vosk-model-br-0.6",
    "vosk6": "vosk-model-br-0.6",
    "vosk-br-0.7": "vosk-model-br-0.7",
    "vosk7": "vosk-model-br-0.7",
    "vosk-br-0.8": "vosk-model-br-0.8",
    "vosk8": "vosk-model-br-0.8",
    "vosk-br-0.9": "vosk-model-br-0.9",
    "vosk9": "vosk-model-br-0.9",
    "vosk": get_latest_model(type="vosk"),
}



def is_model_loaded(model_name=None) -> bool:
    model_name = model_name or get_latest_model()
    if model_name in _MODEL_ALIASES:
        model_name = _MODEL_ALIASES[model_name]
    return _loaded_model_name == model_name



def load_model(model_name: str = None) -> Model:
    global _loaded_model_name
    global _loaded_model
    
    if model_name == None:
        if _loaded_model:
            return _loaded_model
        model_name = get_latest_model()
    elif model_name in _MODEL_ALIASES:
        model_name = _MODEL_ALIASES[model_name]
    
    if model_name == _loaded_model_name:
        return _loaded_model

    if _is_valid_vosk_model(model_name):
        # Given path to a model on local storage
        model_path = model_name
    elif model_name in get_local_models():
        # Model is already downloaded
        model_path = os.path.join(_get_model_directory(), model_name)
    elif model_name in get_all_models():
        # Model needs to be downloaded
        model_path = _download(model_name, _get_model_directory())
    else:
        raise RuntimeError(
            f"Model {model_name} is not a valid model; available models = {get_all_models()}"
        )

    print(f"Loading {os.path.basename(model_path.rstrip(os.path.sep))}", file=sys.stderr)
    SetLogLevel(-1)
    _loaded_model = Model(model_path)
    _loaded_model_name = model_name

    return _loaded_model



def _download(model_name: str, root: str) -> str:
    """ Code modified from https://github.com/openai/whisper
        Get the requested model path on disk or download it if not present
    """
    os.makedirs(root, exist_ok=True)
    
    model_path = os.path.join(root, model_name)

    for model in _model_list:
        if model["name"] == model_name:
            url = model["url"]
            break
    else:
        raise RuntimeError("Couldn't find requested model url")
    
    download_target = os.path.join(root, os.path.basename(url))

    print(f"Downloading model from {url}", file=sys.stderr)
    with urllib.request.urlopen(url, context=_certifi_context) as source, open(download_target, "wb") as output:
        with tqdm(
            total=int(source.info().get("Content-Length")),
            ncols=80,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as loop:
            while True:
                buffer = source.read(8192)
                if not buffer:
                    break

                output.write(buffer)
                loop.update(len(buffer))
    
    with zipfile.ZipFile(download_target, 'r') as zip_ref:
        zip_ref.extractall(root)

    os.remove(download_target)

    return model_path



def _is_valid_vosk_model(dir) -> bool:
    if not os.path.isdir(dir):
        return False
    
    vosk_model_files = {
        "final.dubm",
        "final.ie",
        "final.mat",
        "final.mdl",
        "global_cmvn.stats",
        "mfcc.conf",
        "online_cmvn.conf",
        "splice.conf",
        "word_boundary.int"
    }

    files = set()
    for item in os.walk(dir):
        files.update(item[2])
    return vosk_model_files.issubset(files)
