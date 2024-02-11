''' NX Prompt Styler '''

# TO DO:
# [x] List all CSV files in a folder
# [x] Order CSV files by list of keys
# [x] Select separator for each field
# [x] Allow CSV files not listed
# [x] Add weight for each category
# [x] Add presets for save selection
# [ ] Add random choice for each field
# [ ] Add random choice globly
# [X] Let user update the prompt before running
# [ ] Allow multiple choice by category
# [X] Add output to list selection by category
# (eg: Styles: Action Photograph, Effects: [Vignette, Blur'])
# [ ] Let user update the order of categories

import math
import sys
from pathlib import Path
import csv
import json

from server import PromptServer
from aiohttp import web

# decorator used for create routes from/to server
routes = PromptServer.instance.routes

MY_DIR = Path(__file__).parent
CSV_DIR = Path.joinpath(MY_DIR, "CSV")
PRESETS_FILE = Path.joinpath(MY_DIR, "presets.json")

POSITIVE_ORDER = [
    "styles", 
    "prompt_positive", 
    "framing", 
    "cameras", 
    "lighting", 
    "effects", 
    "composition", 
    "films", 
    "artists"
]
NEGATIVE_ORDER = ['negative', 'prompt_negative']
SPECIAL_SEPARATOR = {"styles": " "}
DEFAULT_SEPARATOR = ", "

PRINT = 0
SUCCESS = 1
ERROR = 2

def console_log(text: str, level: int = 0) -> None:
    ''' Print text in console 
    text: text to print
    level: 0 = print, 1 = success, 2 = error
    '''
    COLOR_FG_GREEN =    "\033[32m"
    COLOR_FG_RED =      "\033[31m"
    COLOR_FG_BLUE =     "\033[34m"
    COLOR_FG_WHITE =    "\033[37m"
    TEXT_BOLD =         "\033[1m"
    RST =               "\033[0m"

    if level == 0:
        print(text)
    elif level == 1:
        print(f"{COLOR_FG_GREEN}{text}{RST}")
    elif level == 2:
        print(f"{COLOR_FG_RED}ERROR: {text}{RST}")

def list_csv(path: Path = CSV_DIR) -> list[Path]:
    ''' List all CSV files in CSV_DIR '''
    return list(path.glob("./*.csv"))

def get_csv_path(file: str) -> Path:
    ''' Get path of CSV file 
    file: name of CSV file
    return: path of CSV file
    '''
    return Path.joinpath(CSV_DIR, file)

def read_csv(path_csv: Path) -> list[dict]:
    ''' Read CSV and return list of dictionaries 
    file: name of CSV file
    return: list of dictionaries
    '''
    try:
        with open(path_csv, "r", encoding="utf-8-sig", newline="") as f:
            list_dict = list(csv.DictReader(f, delimiter=",", quotechar='"'))
    except UnicodeDecodeError:
        console_log(f"CSV file '{path_csv.name}' is not encoded in UTF-8.", ERROR)
        sys.exit()
    except PermissionError:
        console_log(f"CSV file '{path_csv.name}' is not readable.", ERROR)
        sys.exit()
    except FileNotFoundError:
        console_log(f"CSV file '{path_csv.name}' not found.", ERROR)
        sys.exit()
    return list_dict

def get_col(list_dict: list[dict], col_name: str = "name") -> list[str] or None:
    ''' Get column list from CSV file 
    list_dict: list of dictionaries
    col_name: name of column
    return: list of values in column or None   
    '''
    if len(list_dict) == 0 or col_name not in list_dict[0]:
        return None
    return [row[col_name] for row in list_dict]

def get_row(list_dict: list, value: str) -> dict or None:
    ''' Get row list from CSV file by value of field "name" 
    list_dict: list of dictionaries
    value: value of field name
    return: list of values in row or None
    '''
    for row in list_dict:
        if row["name"] == value:
            return row
    return None

def order_csv(dict_list: dict, order: list[str]) -> dict:
    ''' Order CSV file 
    dict_list: list of dictionaries
    order: list of keys
    return: list of dictionaries
    '''
    ordered_dict = {}
    keys_positive = dict_list.pop("positive", None)
    keys_negative = dict_list.pop("negative", None)
    # csv_ordered = [key for key in dict_list if key in order and key != "prompt_positive"]
    csv_unordered = [key for key in dict_list if key not in order]
    for key in order:
        if key in dict_list:
            ordered_dict[key] = dict_list[key]
    for key in csv_unordered:
        ordered_dict[key] = dict_list[key]
    if keys_positive:
        ordered_dict["positive"] = keys_positive
    if keys_negative:
        ordered_dict["negative"] = keys_negative
    return ordered_dict

def get_csv_ordered(path_csv: Path = None)  -> list[dict]:
    ''' Get ordered CSV file 
    path_csv: path of CSV file
    return: list of dictionaries
    '''
    if not path_csv:
        csv_list = list_csv()
    else:
        csv_list = list_csv(path_csv)
    dict_csv_unordered = {file.name[:-4].lower(): read_csv(file) for file in csv_list}
    return order_csv(dict_csv_unordered, POSITIVE_ORDER)

def tabs(text: str) -> str:
    ''' Calculate number of tabulations is needed 
    text: text to calculate
    return: tabulations
    '''
    if not text:
        return ""
    number = 2
    if len(text) > 15:
        number = 1
    if len(text) < 8:
        number = 3
    tab = "\t" * number
    return tab

def get_separator(item: str = '') -> str:
    ''' Get separator '''
    return SPECIAL_SEPARATOR.get(item, DEFAULT_SEPARATOR)

def limit_weight(weight: float = 1.0) -> float:
    ''' Limit weight '''
    return max(min(weight, 5.0), 0.1)

def format_weight(weight: float = 1.0) -> str:
    ''' Format weight '''
    return f"{(math.floor(weight * 100) / 100)}"

def set_weight(value: str = '', weight: float = 1.0) -> str:
    ''' Set weights '''
    weight = limit_weight(weight)
    value_weigted = value
    if weight is not None and weight != 1.0:
        value_weigted = f"({value}:{format_weight(weight)})"
    return value_weigted

def set_resume(item: str = '', value: str = '', weight: float = 1.0) -> str:
    ''' Resume '''
    weight = limit_weight(weight)
    label = f"{item}:"
    resume = label
    if not value or value.strip() == "":
        resume += f"{tabs(label)}None\n"
    else:
        if weight is not None and weight != 1.0:
            value = f"{value} ({format_weight(weight)})"
        resume += f"{tabs(label)}{value}\n"
    return resume

def create_positive(
    csv_ordered: list[dict],
    prompt_positive: str,
    arg_positive: str,
    args_ordered: dict,
    args_not_ordered: dict
) -> str:
    ''' Create positive '''
    positive = ""

    for item in POSITIVE_ORDER:
        if item == 'prompt_positive':
            positive += f"{prompt_positive}{get_separator(item)}"
            continue
        arg = args_ordered.get(item, None)
        if not arg:
            continue
        if arg[0] == 'None' or arg[0].strip() == "":
            continue
        row = get_row(csv_ordered[item], arg[0])
        if not row or not row['prompt'] or row['prompt'].strip() == "":
            continue
        positive += f"{set_weight(row['prompt'], arg[1])}{get_separator(item)}"

    for item in args_not_ordered:
        row = get_row(csv_ordered[item], args_not_ordered[item][0])
        if not row or not row['prompt'] or row['prompt'].strip() == "":
            continue
        positive += f"{set_weight(row['prompt'], args_not_ordered[item][1])}{get_separator(item)}"

    if arg_positive:
        row = get_row(csv_ordered['positive'], arg_positive)
        if row and row['prompt'] or row['prompt'].strip() != "":
            positive += f"{row['prompt']}{get_separator('positive')}"

    return positive.strip(', ')

def create_negative(csv_ordered: list[dict], prompt_negative: str, arg_negative: str) -> str:
    ''' Create negative '''
    negative = ""
    for item in NEGATIVE_ORDER:
        if item == 'prompt_negative' and prompt_negative:
            if prompt_negative != '':
                negative += f"{prompt_negative}{get_separator('negative')}"
            continue
        if item == 'negative' and arg_negative:
            row = get_row(csv_ordered['negative'], arg_negative)
            if row and row['prompt'] or row['prompt'].strip() != "":
                negative += f"{row['prompt']}{get_separator('negative')}"

    return negative.strip(', ')

def create_resume(positive: str, negative: str, ordered: dict, not_ordered: dict) -> str:
    ''' Create resume '''
    resume_title = "Styler SDXL resume"
    resume = f"{resume_title}:\n{'-'*(len(resume_title) + 1)}\n"

    for item in POSITIVE_ORDER:
        if item == 'prompt_positive':
            continue
        arg = ordered.get(item, None)
        if not arg:
            continue
        if arg[0] == 'None':
            resume += set_resume(item, '')
            continue
        resume += set_resume(item, arg[0], arg[1])

    for item in not_ordered:
        resume += set_resume(item, not_ordered[item][0], not_ordered[item][1])

    if positive:
        resume += set_resume('positive', positive)

    for item in NEGATIVE_ORDER:
        if item == 'prompt_negative':
            continue
        if item == 'negative' and negative:
            resume += set_resume('negative', negative)

    return resume

def create_response(csv_ordered: list[dict] = None, data: dict = {}) -> tuple[str, str, str]:
    ''' Create response '''
    if not csv_ordered:
        return ("", "", "")

    prompt_positive = data.pop('prompt_positive', None)
    prompt_negative = data.pop('prompt_negative', None)
    arg_positive = data.pop('positive', None)
    arg_negative = data.pop('negative', None)

    args_ordered = {item[0]: (item[1], data.get(f"{item[0]} weight", None))
        for item in data.items()
        if item[0] in POSITIVE_ORDER and not item[0].endswith(" weight")}

    args_not_ordered = {item[0]: (item[1], data.get(f"{item[0]} weight", None))
        for item in data.items()
        if item[0] not in POSITIVE_ORDER and not item[0].endswith(" weight")}

    positive = create_positive(
        csv_ordered,
        prompt_positive,
        arg_positive,
        args_ordered,
        args_not_ordered
    )
    negative = create_negative(csv_ordered, prompt_negative, arg_negative)
    resume = create_resume(arg_positive, arg_negative, args_ordered, args_not_ordered)

    return (positive, negative, resume)

def read_presets() -> list:
    ''' Get presets '''
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8-sig") as f:
            presets = json.load(f)
    except json.JSONDecodeError as e:
        console_log(f"JSON file '{PRESETS_FILE.name}' is not valid JSON. {e}", ERROR)
        return []
    except PermissionError:
        console_log(f"JSON file '{PRESETS_FILE.name}' is not readable.", ERROR)
        return []
    except FileNotFoundError:
        console_log(f"JSON file '{PRESETS_FILE.name}' not found.", ERROR)
        return []

    return presets
def write_presets(name: str, name_old: str, preset_values: dict) -> tuple[bool, str] :
    ''' Write presets '''
    presets = read_presets()

    if name != name_old and name in [item["name"] for item in presets]:
        error = f"Name '{name}' already exists."
        return False, error
    if name_old in [item["name"] for item in presets]:
        presets_items = [item["name"] for item in presets]
        id = presets_items.index(name_old)
        presets[id] = {"name": name, "values": preset_values}
    else:
        presets.append({"name": name, "values": preset_values})
    
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8-sig") as f:
            json.dump(presets, f, indent=4)
    except PermissionError:
        error = f"JSON file '{PRESETS_FILE.name}' is not writable."
        return False, error
    except IOError:
        error = f"JSON file '{PRESETS_FILE.name}' is not writable."
        return False, error
    
    return True, 'SAVED'

def delete_presets(preset_name: str) -> bool:
    ''' Delete presets '''
    presets = read_presets()
    if not presets:
        presets = {}
    if preset_name  not in [item["name"] for item in presets]:
        return True
    
    presets_items = [item["name"] for item in presets]
    id = presets_items.index(preset_name)
    del(presets[id])
    
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8-sig") as f:
            json.dump(presets, f, indent=4)
    except PermissionError:
        console_log(f"JSON file '{PRESETS_FILE.name}' is not writable.", ERROR)
        return False
    except IOError:
        console_log(f"JSON file '{PRESETS_FILE.name}' is not writable.", ERROR)
        return False
    
    return True

@routes.post('/loadpreset')
async def load_preset(request):
    req = await request.json()
    preset_name = req['preset']
    presets = read_presets()
    resp = {}
    if preset_name and preset_name in [item["name"] for item in presets]:
        preset = [item for item in presets if item["name"] == preset_name][0]
        resp = preset.get("values", {})
    return web.Response(body=json.dumps(resp), content_type='application/json')

@routes.post('/savepreset')
async def save_preset(request):
    req = await request.json()    
    resp = {"name": req['name'], "name_old": req['name_old'], "saved": False}
    succes, msg = write_presets(req['name'], req["name_old"], req['values'])
    if succes:
        resp["saved"] = True
    else:
        resp["error"] = msg
    return web.Response(body=json.dumps(resp), content_type='application/json')

@routes.post('/deletepreset')
async def delete_preset(request):
    req = await request.json()
    resp = {"deleted": False}
    if delete_presets(req['preset']):
        resp["deleted"] = True
    return web.Response(body=json.dumps(resp), content_type='application/json')

@routes.post('/loadpositive')
async def load_positive(request):
    req = await request.json()
    positive, _, _ = create_response(csv_ordered=NX_PromptStyler.csv_ordered, data=req['data'])

    resp = {"success": True, "prompt_positive": positive}
    
    return web.Response(body=json.dumps(resp), content_type='application/json')

@routes.post('/loadprompt')
async def load_prompt(request):
    req = await request.json()
    prompt = ""
    if req['prompt'] == "positive":
        prompt, _, _ = create_response(csv_ordered=NX_PromptStyler.csv_ordered, data=req['data'])
    if req['prompt'] == "negative":
        _, prompt, _ = create_response(csv_ordered=NX_PromptStyler.csv_ordered, data=req['data'])
        
    resp = {"prompt": prompt}
    
    return web.Response(body=json.dumps(resp), content_type='application/json')

class NX_PromptStyler:
    ''' NX Prompt Styler '''
    csv_ordered = get_csv_ordered()
    presets = read_presets()

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        ''' Input types '''

        presets_items = [item["name"] for item in s.presets]

        required = {
            "prompt_positive": ("STRING", {"placeholder": "positive", "multiline": True}),
            "prompt_negative": ("STRING", {"placeholder": "negative", "multiline": True}),
        }
        for item in s.csv_ordered.items():
            col = get_col(item[1])
            if col is None:
                continue
            required[item[0]] = (col, {"default": "None"})
            if item[0] not in ("positive", "negative"):
                required[f"{item[0]} weight"] = ("FLOAT", {
                    "default": 1.0, 
                    "min": 0.1, 
                    "max": 5.0, 
                    "step": 0.05,
                    "round": 0.001
                })
        return {
            "required": required,
            "optional": {
                "viewer_positive": ("STRING", {"placeholder": "output positive", "multiline": True}),
                "viewer_negative": ("STRING", {"placeholder": "output negative", "multiline": True}),
                "presets": (presets_items, {"default": "none"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "resume")
    FUNCTION = "run"
    OUTPUT_NODE = True

    CATEGORY = "NX_Nodes"

    def run(self, presets="none", viewer_positive="", viewer_negative="", **kwargs):
        ''' Run function '''  
        positive, negative, resume = create_response(csv_ordered=self.csv_ordered, data=kwargs)
        if viewer_positive.strip() != "":
            positive = viewer_positive.strip()
        if viewer_negative.strip() != "":
            negative = viewer_negative.strip()
        return {"result": (positive, negative, resume)}


WEB_DIRECTORY = "js"

NODE_CLASS_MAPPINGS = {
    "NX_PromptStyler": NX_PromptStyler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NX_PromptStyler": "📄 Prompt Styler",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
# __all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
