# -*- coding: utf-8 -*-
# Ejecutar dentro de PLC Designer 4.2.
# Exporta las versiones instaladas para Lenze Machine Builder.

import os
import json

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "device_repository.json"
)

SEARCH_TERMS = ["c430", "c520", "c550", "i550", "i750", "i950"]


def version_text(device):
    try:
        return str(device.device_id.version)
    except:
        text = str(device.device_id)
        marker = "Version='"
        try:
            start = text.index(marker) + len(marker)
            end = text.index("'", start)
            return text[start:end]
        except:
            return ""


def device_name(device):
    try:
        return str(device.device_info.name)
    except:
        try:
            return str(device.name)
        except:
            return ""


def main():
    result = []
    known = set()

    for term in SEARCH_TERMS:
        devices = device_repository.get_all_devices(term)
        if devices is None:
            continue
        for device in devices:
            key = str(device.device_id)
            if key in known:
                continue
            known.add(key)
            result.append({
                "name": device_name(device),
                "version": version_text(device),
                "device_id": key
            })

    with open(OUTPUT_FILE, "w") as output:
        output.write(json.dumps({"devices": result}, indent=2))

    print("Exportado: " + OUTPUT_FILE)
    print("Descriptores: " + str(len(result)))


main()
