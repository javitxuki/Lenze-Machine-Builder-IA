import io
import json
import math
import os
import re
from copy import deepcopy


def _number(text):
    return float(str(text).replace(",", "."))


def _feed(mode, parameter):
    mode = str(mode).upper()
    value = _number(parameter)
    if mode == "ROTARY":
        return 360.0
    if mode == "LEADSCREW":
        return value
    if mode in ("BELT", "RACK_PINION"):
        return math.pi * value
    return value


def _new_axis(index):
    return {
        "enabled": True,
        "name": "Axis_{0:02d}".format(index),
        "drive_type": "i950",
        "safety_variant": "Basic Safety",
        "i950_variant": "Normal",
        "descriptor_label": "",
        "device_id": "",
        "station_alias": 1000 + index,
        "second_station_alias": 2000 + index,
        "motor_code_c86": "",
        "kinematics": "ROTARY",
        "kinematic_parameter": 360.0,
        "z1": 1,
        "z2": 1,
        "z3": 1,
        "z4": 1,
        "traversing_range": "MODULO",
        "feed_constant": 360.0,
        "cycle_length": 360.0,
    }


def local_parse(prompt, current_axes):
    text = str(prompt).lower().strip()
    axes = deepcopy(current_axes)
    notes = []

    count_match = re.search(r"(\d+)\s*ejes?", text)
    if count_match:
        count = max(1, min(32, int(count_match.group(1))))
        while len(axes) < count:
            axes.append(_new_axis(len(axes) + 1))
        axes = axes[:count]
        notes.append("Número de ejes: {0}".format(count))

    # Instrucciones por eje: eje 2 i750 extended safety, polea 120, husillo 10...
    chunks = re.split(r"(?=eje\s*\d+)", text)
    for chunk in chunks:
        match = re.search(r"eje\s*(\d+)", chunk)
        if not match:
            continue
        index = int(match.group(1)) - 1
        while len(axes) <= index:
            axes.append(_new_axis(len(axes) + 1))
        axis = axes[index]

        for drive in ("i550", "i750", "i950"):
            if drive in chunk:
                axis["drive_type"] = drive
        if "extended" in chunk:
            axis["safety_variant"] = "Extended Safety"
        elif "basic" in chunk:
            axis["safety_variant"] = "Basic Safety"
        if "dc-link" in chunk or "dc link" in chunk:
            axis["i950_variant"] = "DC-Link"

        rotary = "rotary" in chunk or "rotativo" in chunk
        lead = re.search(r"(?:husillo|leadscrew).*?(\d+(?:[\.,]\d+)?)", chunk)
        belt = re.search(r"(?:correa|polea|belt).*?(\d+(?:[\.,]\d+)?)", chunk)
        rack = re.search(r"(?:cremallera|piñ[oó]n|rack).*?(\d+(?:[\.,]\d+)?)", chunk)
        if rotary:
            axis.update({"kinematics": "ROTARY", "kinematic_parameter": 360.0, "feed_constant": 360.0, "cycle_length": 360.0})
        elif lead:
            value = _number(lead.group(1))
            axis.update({"kinematics": "LEADSCREW", "kinematic_parameter": value, "feed_constant": _feed("LEADSCREW", value), "traversing_range": "LIMITED", "cycle_length": 0.0})
        elif belt:
            value = _number(belt.group(1))
            axis.update({"kinematics": "BELT", "kinematic_parameter": value, "feed_constant": _feed("BELT", value), "traversing_range": "LIMITED", "cycle_length": 0.0})
        elif rack:
            value = _number(rack.group(1))
            axis.update({"kinematics": "RACK_PINION", "kinematic_parameter": value, "feed_constant": _feed("RACK_PINION", value), "traversing_range": "LIMITED", "cycle_length": 0.0})

        for z in (1, 2, 3, 4):
            zmatch = re.search(r"z{0}\s*(?:=|a)?\s*(\d+)".format(z), chunk)
            if zmatch:
                axis["z{0}".format(z)] = int(zmatch.group(1))

        notes.append("Actualizado {0}".format(axis["name"]))

    # Rango secuencial de aliases.
    alias_match = re.search(r"alias(?:es)?\s*(?:desde|a partir de)?\s*(\d+)", text)
    second_match = re.search(r"second\s+alias(?:es)?\s*(?:desde|a partir de)?\s*(\d+)", text)
    if alias_match:
        start = int(alias_match.group(1))
        for i, axis in enumerate(axes): axis["station_alias"] = start + i
    if second_match:
        start = int(second_match.group(1))
        for i, axis in enumerate(axes): axis["second_station_alias"] = start + i

    if not notes:
        notes.append("No he identificado cambios seguros. Prueba: '3 ejes; eje 1 i950 rotary; eje 2 belt 120; eje 3 leadscrew 10'.")
    return {"axes": axes, "summary": "\n".join(notes), "source": "local"}


def transcribe_audio(audio_bytes, filename="voice.wav"):
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("La voz requiere configurar OPENAI_API_KEY en Railway.")
    from openai import OpenAI
    client = OpenAI(api_key=key)
    stream = io.BytesIO(audio_bytes)
    stream.name = filename
    result = client.audio.transcriptions.create(model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"), file=stream)
    return result.text


def interpret(prompt, current_axes):
    # Primera versión segura: parser local. No aplica cambios hasta confirmación.
    return local_parse(prompt, current_axes)
