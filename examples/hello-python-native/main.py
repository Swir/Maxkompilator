import json
from pathlib import Path

message = json.loads((Path(__file__).parent / "assets/message.json").read_text(encoding="utf-8"))
if message["message"] != "Maxkompilator: build and resource check OK":
    raise RuntimeError("Bundled resource differs from the selected profile")
print(message["message"])
