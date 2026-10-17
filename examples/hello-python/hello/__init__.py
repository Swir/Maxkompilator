import json
from importlib.resources import files


def main():
    message = json.loads(files(__package__).joinpath("message.json").read_text(encoding="utf-8"))
    print(message["message"])
