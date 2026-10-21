"""Never overwrite a first-seen research HTTP response."""
import json
from pathlib import Path

def save(folder,record,raw):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    payload={"manifest.json":(json.dumps(record,indent=2,sort_keys=True)+"\n").encode()}
    if raw is not None:
        payload["official_response_raw.json"]=raw
    for name,body in payload.items():
        path=folder/name
        if path.exists():
            if path.read_bytes()!=body:
                raise ValueError("immutable first-seen conflict")
        else:
            with path.open("xb") as file:
                file.write(body)
    return folder
