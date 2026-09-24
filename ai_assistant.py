# -*- coding: utf-8 -*-
"""Lenze Machine Builder Assistant V3.

Parser local robusto para instrucciones en español o inglés.
La función pública interpret(prompt, current_axes, current_config=None) devuelve:
{
    "axes": [...],
    "cpu_model": "c520" | None,
    "axis_count": int,
    "summary": str,
    "changes": [...],
    "warnings": [...],
    "source": "local-v3"
}

La configuración nunca se aplica automáticamente. app.py debe mostrar la
propuesta y aplicarla únicamente después de la confirmación del usuario.
"""

from __future__ import annotations

import io
import math
import os
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_CPUS = ("c430", "c520", "c550")
SUPPORTED_DRIVES = ("i550", "i750", "i950")
SUPPORTED_KINEMATICS = ("ROTARY", "LEADSCREW", "BELT", "RACK_PINION")


def _normalize(text: Any) -> str:
    value = str(text or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("−", "-").replace("–", "-")
    value = re.sub(r"\s+", " ", value)
    return value


def _number(value: Any) -> float:
    raw = str(value).strip().replace(" ", "").replace(",", ".")
    return float(raw)


def _formatted_number(value: float) -> float:
    return float(("{0:.12f}".format(float(value))).rstrip("0").rstrip("."))


def _feed(mode: str, parameter: Any) -> float:
    mode = str(mode).upper()
    value = _number(parameter)
    if mode == "ROTARY":
        return 360.0
    if mode == "LEADSCREW":
        return _formatted_number(value)
    if mode in ("BELT", "RACK_PINION"):
        return _formatted_number(math.pi * value)
    raise ValueError("Kinematics no reconocida: " + mode)


def _new_axis(index: int) -> Dict[str, Any]:
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


def _ensure_axes(axes: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    count = max(1, min(32, int(count)))
    while len(axes) < count:
        axes.append(_new_axis(len(axes) + 1))
    return axes[:count]


def _detect_cpu(text: str) -> Optional[str]:
    match = re.search(r"\b(?:cpu|controller|controlador)?\s*(c430|c520|c550)\b", text)
    return match.group(1) if match else None


def _detect_axis_count(text: str) -> Optional[int]:
    patterns = (
        r"\b(\d+)\s*(?:ejes|eje|axes|axis)\b",
        r"\b(?:ejes|axes)\s*[:=]?\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, min(32, int(match.group(1))))
    return None


def _axis_clauses(text: str) -> List[Tuple[int, str]]:
    """Devuelve segmentos 'eje N ...' hasta el siguiente eje o fin de texto."""
    matches = list(re.finditer(r"\b(?:eje|axis)\s*0*(\d+)\b", text))
    clauses = []
    for pos, match in enumerate(matches):
        start = match.start()
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
        clauses.append((int(match.group(1)) - 1, text[start:end].strip(" ,;.")))
    return clauses


def _extract_drive(clause: str) -> Optional[str]:
    match = re.search(r"\b(i550|i750|i950)\b", clause)
    return match.group(1) if match else None


def _extract_safety(clause: str) -> Optional[str]:
    if re.search(r"\b(?:extended|extendida|es)\s*(?:safety|seguridad)?\b", clause):
        return "Extended Safety"
    if re.search(r"\b(?:basic|basica|bs)\s*(?:safety|seguridad)?\b", clause):
        return "Basic Safety"
    return None


def _extract_i950_variant(clause: str) -> Optional[str]:
    if re.search(r"\bdc[ -]?link\b", clause):
        return "DC-Link"
    if re.search(r"\b(?:normal|standard)\b", clause) and "i950" in clause:
        return "Normal"
    return None


def _extract_traversing_range(clause: str) -> Optional[str]:
    if re.search(r"\b(?:limited|limitado|limitada)\b", clause):
        return "LIMITED"
    if re.search(r"\b(?:modulo|m[oó]dulo|modular)\b", clause):
        return "MODULO"
    return None


def _extract_kinematics(clause: str) -> Optional[Tuple[str, float]]:
    number = r"(-?\d+(?:[\.,]\d+)?)"
    patterns = (
        ("LEADSCREW", r"\b(?:husillo|leadscrew|lead screw|tornillo)\b[^\d-]*" + number),
        ("BELT", r"\b(?:correa|polea|belt|pulley)\b[^\d-]*" + number),
        ("RACK_PINION", r"\b(?:cremallera|pinon|rack(?:\s*(?:and|&))?\s*pinion)\b[^\d-]*" + number),
    )
    if re.search(r"\b(?:rotary|rotativo|rotativa)\b", clause):
        return "ROTARY", 360.0
    for mode, pattern in patterns:
        match = re.search(pattern, clause)
        if match:
            return mode, _number(match.group(1))
    return None


def _extract_z_values(clause: str) -> Dict[str, int]:
    values = {}
    for index in (1, 2, 3, 4):
        patterns = (
            r"\bz{0}\s*(?:=|:|a)?\s*(-?\d+)\b".format(index),
            r"\bz\s*{0}\s*(?:=|:|a)?\s*(-?\d+)\b".format(index),
        )
        for pattern in patterns:
            match = re.search(pattern, clause)
            if match:
                values["z{0}".format(index)] = int(match.group(1))
                break
    return values


def _extract_alias(clause: str, second: bool = False) -> Optional[int]:
    if second:
        pattern = r"\b(?:second|segundo|2nd)\s*(?:station\s*)?alias\s*(?:=|:)?\s*(\d+)\b"
    else:
        pattern = r"(?<!second )(?<!segundo )(?<!2nd )\b(?:station\s*)?alias\s*(?:=|:)?\s*(\d+)\b"
    match = re.search(pattern, clause)
    return int(match.group(1)) if match else None


def _extract_c86(clause: str) -> Optional[str]:
    match = re.search(r"\bc86\s*(?:=|:)?\s*([a-z0-9._-]+)\b", clause)
    return match.group(1).upper() if match else None


def _describe_axis(axis: Dict[str, Any]) -> str:
    return (
        "{name}: {drive}, {safety}, {kin}, parámetro {parameter}, "
        "Feed {feed}, {traversing}, Z1={z1}, Z2={z2}, Z3={z3}, Z4={z4}"
    ).format(
        name=axis.get("name"),
        drive=axis.get("drive_type"),
        safety=axis.get("safety_variant"),
        kin=axis.get("kinematics"),
        parameter=axis.get("kinematic_parameter"),
        feed=axis.get("feed_constant"),
        traversing=axis.get("traversing_range"),
        z1=axis.get("z1"), z2=axis.get("z2"), z3=axis.get("z3"), z4=axis.get("z4"),
    )


def local_parse(prompt: str, current_axes: List[Dict[str, Any]], current_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    text = _normalize(prompt)
    axes = deepcopy(current_axes or [])
    changes: List[str] = []
    warnings: List[str] = []

    cpu_model = _detect_cpu(text)
    if cpu_model:
        changes.append("CPU: " + cpu_model)

    count = _detect_axis_count(text)
    if count is not None:
        axes = _ensure_axes(axes, count)
        changes.append("Número de ejes: {0}".format(count))
    elif not axes:
        axes = [_new_axis(1)]

    clauses = _axis_clauses(text)
    if not clauses and len(axes) == 1:
        # Permitir una orden de un eje sin repetir 'eje 1'.
        clauses = [(0, text)]

    for axis_index, clause in clauses:
        if axis_index < 0 or axis_index >= 32:
            warnings.append("Número de eje fuera de rango: {0}".format(axis_index + 1))
            continue
        axes = _ensure_axes(axes, max(len(axes), axis_index + 1))
        axis = axes[axis_index]

        drive = _extract_drive(clause)
        safety = _extract_safety(clause)
        variant = _extract_i950_variant(clause)
        traversing = _extract_traversing_range(clause)
        kinematics = _extract_kinematics(clause)
        z_values = _extract_z_values(clause)
        alias = _extract_alias(clause, False)
        second_alias = _extract_alias(clause, True)
        c86 = _extract_c86(clause)

        if drive:
            axis["drive_type"] = drive
            # i550 no ofrece selector de Extended Safety en la aplicación actual.
            if drive == "i550" and safety == "Extended Safety":
                warnings.append("{0}: i550 + Extended Safety requiere revisión manual.".format(axis["name"]))
        if safety:
            axis["safety_variant"] = safety
        if variant:
            axis["i950_variant"] = variant
        elif drive and drive != "i950":
            axis["i950_variant"] = "Normal"
        if traversing:
            axis["traversing_range"] = traversing
        if kinematics:
            mode, parameter = kinematics
            axis["kinematics"] = mode
            axis["kinematic_parameter"] = parameter
            axis["feed_constant"] = _feed(mode, parameter)
            axis["cycle_length"] = 360.0 if mode == "ROTARY" else 0.0
            if not traversing:
                axis["traversing_range"] = "MODULO" if mode == "ROTARY" else "LIMITED"
        axis.update(z_values)
        if alias is not None:
            axis["station_alias"] = alias
        if second_alias is not None:
            axis["second_station_alias"] = second_alias
        if c86:
            axis["motor_code_c86"] = c86

        changes.append(_describe_axis(axis))

    # Alias secuenciales globales.
    station_sequence = re.search(r"\b(?:station\s*)?aliases?\s*(?:desde|from|a partir de)\s*(\d+)\b", text)
    second_sequence = re.search(r"\b(?:second|segundo|2nd)\s*(?:station\s*)?aliases?\s*(?:desde|from|a partir de)\s*(\d+)\b", text)
    if station_sequence:
        start = int(station_sequence.group(1))
        for pos, axis in enumerate(axes):
            axis["station_alias"] = start + pos
        changes.append("Station Alias secuencial desde {0}".format(start))
    if second_sequence:
        start = int(second_sequence.group(1))
        for pos, axis in enumerate(axes):
            axis["second_station_alias"] = start + pos
        changes.append("Second Station Alias secuencial desde {0}".format(start))

    if not changes:
        warnings.append(
            "No se identificaron cambios. Ejemplo: CPU c520, 1 eje, eje 1 i750 Extended Safety, "
            "correa 100, LIMITED, Z1 10, Z2 20, Z3 30, Z4 40."
        )

    return {
        "axes": axes,
        "cpu_model": cpu_model,
        "axis_count": len(axes),
        "summary": "\n\n".join(changes + (["Avisos: " + " ".join(warnings)] if warnings else [])),
        "changes": changes,
        "warnings": warnings,
        "source": "local-v3",
    }


def transcribe_audio(audio_bytes: bytes, filename: str = "voice.wav") -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("La voz requiere configurar OPENAI_API_KEY en Railway.")
    from openai import OpenAI
    client = OpenAI(api_key=key)
    stream = io.BytesIO(audio_bytes)
    stream.name = filename
    result = client.audio.transcriptions.create(
        model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
        file=stream,
    )
    return result.text


def interpret(prompt: str, current_axes: List[Dict[str, Any]], current_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return local_parse(prompt, current_axes, current_config)
