# -*- coding: utf-8 -*-
"""Lenze Machine Builder Assistant.
Asistente híbrido:
1. OpenAI interpreta instrucciones en lenguaje natural.
2. El parser local queda como respaldo si OpenAI no está disponible.
3. La configuración nunca se aplica automáticamente.
   app.py muestra la propuesta y el usuario decide si aplicarla.
"""
from __future__ import annotations
import io
import json
import math
import os
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
SUPPORTED_CPUS = ("c430", "c520", "c550")
SUPPORTED_DRIVES = ("i550", "i750", "i950")
SUPPORTED_KINEMATICS = (
    "ROTARY",
    "LEADSCREW",
    "BELT",
    "RACK_PINION",
)
# ============================================================
# UTILIDADES
# ============================================================
def _normalize(text: Any) -> str:
    value = str(text or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        ch for ch in value
        if not unicodedata.combining(ch)
    )
    value = value.replace("−", "-").replace("–", "-")
    value = re.sub(r"\s+", " ", value)
    return value
def _number(value: Any) -> float:
    raw = str(value).strip().replace(" ", "").replace(",", ".")
    return float(raw)
def _formatted_number(value: float) -> float:
    text = "{0:.12f}".format(float(value))
    text = text.rstrip("0").rstrip(".")
    return float(text)
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
# ============================================================
# CONFIGURACIÓN DE EJES
# ============================================================
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
def _ensure_axes(
    axes: List[Dict[str, Any]],
    count: int
) -> List[Dict[str, Any]]:
    count = max(1, min(32, int(count)))
    while len(axes) < count:
        axes.append(_new_axis(len(axes) + 1))
    return axes[:count]
def _sanitize_axis(axis: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Completa un eje devuelto por OpenAI con valores seguros."""
    base = _new_axis(index)
    if not isinstance(axis, dict):
        return base
    base.update(axis)
    # Valores válidos
    if base["drive_type"] not in SUPPORTED_DRIVES:
        base["drive_type"] = "i950"
    if base["kinematics"] not in SUPPORTED_KINEMATICS:
        base["kinematics"] = "ROTARY"
    if base["safety_variant"] not in (
        "Basic Safety",
        "Extended Safety",
    ):
        base["safety_variant"] = "Basic Safety"
    if base["i950_variant"] not in (
        "Normal",
        "DC-Link",
    ):
        base["i950_variant"] = "Normal"
    if base["traversing_range"] not in (
        "MODULO",
        "LIMITED",
    ):
        base["traversing_range"] = (
            "MODULO"
            if base["kinematics"] == "ROTARY"
            else "LIMITED"
        )
    # Números
    integer_fields = (
        "station_alias",
        "second_station_alias",
        "z1",
        "z2",
        "z3",
        "z4",
    )
    for field in integer_fields:
        try:
            base[field] = int(base[field])
        except Exception:
            base[field] = _new_axis(index)[field]
    try:
        base["kinematic_parameter"] = float(
            base["kinematic_parameter"]
        )
    except Exception:
        base["kinematic_parameter"] = 360.0
    # Recalcular siempre el Feed Constant.
    try:
        base["feed_constant"] = _feed(
            base["kinematics"],
            base["kinematic_parameter"],
        )
    except Exception:
        base["feed_constant"] = 360.0
    base["cycle_length"] = (
        360.0
        if base["kinematics"] == "ROTARY"
        else 0.0
    )
    return base
# ============================================================
# PARSER LOCAL
# ============================================================
def _detect_cpu(text: str) -> Optional[str]:
    match = re.search(
        r"\b(?:cpu|controller|controlador)?\s*"
        r"(c430|c520|c550)\b",
        text,
    )
    return match.group(1) if match else None
def _detect_axis_count(text: str) -> Optional[int]:
    patterns = (
        r"\b(\d+)\s*(?:ejes|eje|axes|axis)\b",
        r"\b(?:ejes|axes)\s*[:=]?\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(
                1,
                min(32, int(match.group(1)))
            )
    return None
def _axis_clauses(text: str) -> List[Tuple[int, str]]:
    matches = list(
        re.finditer(
            r"\b(?:eje|axis)\s*0*(\d+)\b",
            text,
        )
    )
    clauses = []
    for pos, match in enumerate(matches):
        start = match.start()
        end = (
            matches[pos + 1].start()
            if pos + 1 < len(matches)
            else len(text)
        )
        clauses.append(
            (
                int(match.group(1)) - 1,
                text[start:end].strip(" ,;."),
            )
        )
    return clauses
def _extract_drive(clause: str) -> Optional[str]:
    match = re.search(
        r"\b(i550|i750|i950)\b",
        clause,
    )
    return match.group(1) if match else None
def _extract_safety(clause: str) -> Optional[str]:
    if re.search(
        r"\b(?:extended|extendida|es)\s*"
        r"(?:safety|seguridad)?\b",
        clause,
    ):
        return "Extended Safety"
    if re.search(
        r"\b(?:basic|basica|básica|bs)\s*"
        r"(?:safety|seguridad)?\b",
        clause,
    ):
        return "Basic Safety"
    return None
def _extract_i950_variant(clause: str) -> Optional[str]:
    if re.search(r"\bdc[ -]?link\b", clause):
        return "DC-Link"
    if re.search(
        r"\b(?:normal|standard)\b",
        clause,
    ) and "i950" in clause:
        return "Normal"
    return None
def _extract_traversing_range(clause: str) -> Optional[str]:
    if re.search(
        r"\b(?:limited|limitado|limitada)\b",
        clause,
    ):
        return "LIMITED"
    if re.search(
        r"\b(?:modulo|m[oó]dulo|modular)\b",
        clause,
    ):
        return "MODULO"
    return None
def _extract_kinematics(
    clause: str
) -> Optional[Tuple[str, float]]:
    number = r"(-?\d+(?:[\.,]\d+)?)"
    patterns = (
        (
            "LEADSCREW",
            r"\b(?:husillo|leadscrew|lead screw|tornillo)\b"
            r"[^\d-]*"
            + number,
        ),
        (
            "BELT",
            r"\b(?:correa|polea|belt|pulley)\b"
            r"[^\d-]*"
            + number,
        ),
        (
            "RACK_PINION",
            r"\b(?:cremallera|pinon|piñon|"
            r"rack(?:\s*(?:and|&))?\s*pinion)\b"
            r"[^\d-]*"
            + number,
        ),
    )
    if re.search(
        r"\b(?:rotary|rotativo|rotativa)\b",
        clause,
    ):
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
            r"\bz{0}\s*(?:=|:|a)?\s*(-?\d+)\b"
            .format(index),
            r"\bz\s*{0}\s*(?:=|:|a)?\s*(-?\d+)\b"
            .format(index),
        )
        for pattern in patterns:
            match = re.search(pattern, clause)
            if match:
                values[
                    "z{0}".format(index)
                ] = int(match.group(1))
                break
    return values
def _extract_alias(
    clause: str,
    second: bool = False
) -> Optional[int]:
    if second:
        pattern = (
            r"\b(?:second|segundo|2nd)"
            r"\s*(?:station\s*)?alias"
            r"\s*(?:=|:)?\s*(\d+)\b"
        )
    else:
        pattern = (
            r"(?<!second )"
            r"(?<!segundo )"
            r"(?<!2nd )"
            r"\b(?:station\s*)?alias"
            r"\s*(?:=|:)?\s*(\d+)\b"
        )
    match = re.search(pattern, clause)
    return (
        int(match.group(1))
        if match
        else None
    )
def _extract_c86(clause: str) -> Optional[str]:
    match = re.search(
        r"\bc86\s*(?:=|:)?\s*"
        r"([a-z0-9._-]+)\b",
        clause,
    )
    return (
        match.group(1).upper()
        if match
        else None
    )
def _describe_axis(
    axis: Dict[str, Any]
) -> str:
    return (
        "{name}: {drive}, {safety}, {kin}, "
        "parámetro {parameter}, Feed {feed}, "
        "{traversing}, Z1={z1}, Z2={z2}, "
        "Z3={z3}, Z4={z4}"
    ).format(
        name=axis.get("name"),
        drive=axis.get("drive_type"),
        safety=axis.get("safety_variant"),
        kin=axis.get("kinematics"),
        parameter=axis.get("kinematic_parameter"),
        feed=axis.get("feed_constant"),
        traversing=axis.get("traversing_range"),
        z1=axis.get("z1"),
        z2=axis.get("z2"),
        z3=axis.get("z3"),
        z4=axis.get("z4"),
    )
def local_parse(
    prompt: str,
    current_axes: List[Dict[str, Any]],
    current_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    text = _normalize(prompt)
    axes = deepcopy(current_axes or [])
    changes: List[str] = []
    warnings: List[str] = []
    cpu_model = _detect_cpu(text)
    if cpu_model:
        changes.append("CPU: " + cpu_model)
    count = _detect_axis_count(text)
    if count is not None:
        axes = _ensure_axes(
            axes,
            count,
        )
        changes.append(
            "Número de ejes: {0}".format(count)
        )
    elif not axes:
        axes = [_new_axis(1)]
    clauses = _axis_clauses(text)
    if not clauses and len(axes) == 1:
        clauses = [(0, text)]
    for axis_index, clause in clauses:
        if axis_index < 0 or axis_index >= 32:
            warnings.append(
                "Número de eje fuera de rango: {0}"
                .format(axis_index + 1)
            )
            continue
        axes = _ensure_axes(
            axes,
            max(len(axes), axis_index + 1),
        )
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
            if (
                drive == "i550"
                and safety == "Extended Safety"
            ):
                warnings.append(
                    "{0}: i550 + Extended Safety "
                    "requiere revisión manual."
                    .format(axis["name"])
                )
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
            axis["feed_constant"] = _feed(
                mode,
                parameter,
            )
            axis["cycle_length"] = (
                360.0
                if mode == "ROTARY"
                else 0.0
            )
            if not traversing:
                axis["traversing_range"] = (
                    "MODULO"
                    if mode == "ROTARY"
                    else "LIMITED"
                )
        axis.update(z_values)
        if alias is not None:
            axis["station_alias"] = alias
        if second_alias is not None:
            axis["second_station_alias"] = second_alias
        if c86:
            axis["motor_code_c86"] = c86
        changes.append(
            _describe_axis(axis)
        )
    station_sequence = re.search(
        r"\b(?:station\s*)?aliases?\s*"
        r"(?:desde|from|a partir de)\s*(\d+)\b",
        text,
    )
    second_sequence = re.search(
        r"\b(?:second|segundo|2nd)\s*"
        r"(?:station\s*)?aliases?\s*"
        r"(?:desde|from|a partir de)\s*(\d+)\b",
        text,
    )
    if station_sequence:
        start = int(
            station_sequence.group(1)
        )
        for pos, axis in enumerate(axes):
            axis["station_alias"] = start + pos
        changes.append(
            "Station Alias secuencial desde {0}"
            .format(start)
        )
    if second_sequence:
        start = int(
            second_sequence.group(1)
        )
        for pos, axis in enumerate(axes):
            axis["second_station_alias"] = start + pos
        changes.append(
            "Second Station Alias secuencial desde {0}"
            .format(start)
        )
    if not changes:
        warnings.append(
            "No se identificaron cambios. "
            "Ejemplo: CPU c520, 1 eje, eje 1 i750 "
            "Extended Safety, correa 100, LIMITED, "
            "Z1 10, Z2 20, Z3 30, Z4 40."
        )
    return {
        "axes": axes,
        "cpu_model": cpu_model,
        "axis_count": len(axes),
        "summary": "\n\n".join(
            changes
            + (
                ["Avisos: " + " ".join(warnings)]
                if warnings
                else []
            )
        ),
        "changes": changes,
        "warnings": warnings,
        "source": "local-v3",
    }
# ============================================================
# OPENAI
# ============================================================
def _openai_client():
    key = os.getenv(
        "OPENAI_API_KEY",
        ""
    ).strip()
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)
def _openai_model():
    return os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    ).strip()
def _build_openai_prompt(
    prompt: str,
    current_axes: List[Dict[str, Any]],
    current_config: Optional[Dict[str, Any]],
) -> str:
    schema = {
        "axes": [
            {
                "enabled": True,
                "name": "Axis_01",
                "drive_type": "i950",
                "safety_variant": "Basic Safety",
                "i950_variant": "Normal",
                "station_alias": 1001,
                "second_station_alias": 2001,
                "motor_code_c86": "",
                "kinematics": "ROTARY",
                "kinematic_parameter": 360.0,
                "z1": 1,
                "z2": 1,
                "z3": 1,
                "z4": 1,
                "traversing_range": "MODULO",
            }
        ],
        "cpu_model": None,
        "summary": "",
        "changes": [],
        "warnings": [],
    }
    return f"""
Eres el asistente técnico de una aplicación llamada
Lenze Machine Builder Web.
Tu trabajo es interpretar la petición del usuario y convertirla
en una propuesta de configuración de una máquina.
IMPORTANTE:
- NO inventes parámetros que el usuario no haya solicitado.
- Conserva los valores actuales cuando el usuario no los cambie.
- Nunca apliques la configuración: solo devuelve una propuesta.
- CPU permitidas: c430, c520, c550.
- Drives permitidos: i550, i750, i950.
- Kinematics permitidas: ROTARY, LEADSCREW, BELT, RACK_PINION.
- Safety permitido: Basic Safety, Extended Safety.
- i950_variant permitido: Normal, DC-Link.
- Traversing Range permitido: MODULO, LIMITED.
REGLAS DE CÁLCULO:
ROTARY:
    feed_constant = 360
LEADSCREW:
    feed_constant = kinematic_parameter
BELT:
    feed_constant = pi * kinematic_parameter
RACK_PINION:
    feed_constant = pi * kinematic_parameter
Para ROTARY:
    cycle_length = 360
Para cualquier otra cinemática:
    cycle_length = 0
Si el usuario no especifica un valor,
mantén el valor actual.
CONFIGURACIÓN ACTUAL:
{json.dumps(current_axes, ensure_ascii=False, indent=2)}
CONFIGURACIÓN GENERAL ACTUAL:
{json.dumps(current_config or {{}}, ensure_ascii=False, indent=2)}
PETICIÓN DEL USUARIO:
{prompt}
Devuelve ÚNICAMENTE JSON válido.
La estructura debe ser:
{json.dumps(schema, ensure_ascii=False, indent=2)}
"""
def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    # Caso normal
    try:
        return json.loads(text)
    except Exception:
        pass
    # El modelo puede devolver ```json ... ```
    match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return json.loads(
            match.group(1)
        )
    # Buscar el primer objeto JSON
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(
            text[start:end + 1]
        )
    raise ValueError(
        "OpenAI no devolvió un JSON válido."
    )
def _openai_interpret(
    prompt: str,
    current_axes: List[Dict[str, Any]],
    current_config: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    client = _openai_client()
    if client is None:
        raise RuntimeError(
            "OPENAI_API_KEY no está configurada."
        )
    response = client.responses.create(
        model=_openai_model(),
        input=[
            {
                "role": "system",
                "content": (
                    "Devuelve exclusivamente JSON válido. "
                    "No uses Markdown."
                ),
            },
            {
                "role": "user",
                "content": _build_openai_prompt(
                    prompt,
                    current_axes,
                    current_config,
                ),
            },
        ],
    )
    raw = response.output_text
    result = _extract_json(raw)
    axes = result.get("axes", [])
    if not isinstance(axes, list):
        raise ValueError(
            "La respuesta de OpenAI no contiene "
            "una lista válida de ejes."
        )
    axes = [
        _sanitize_axis(
            axis,
            index + 1,
        )
        for index, axis in enumerate(axes)
    ]
    # Limitar a 32 ejes
    axes = axes[:32]
    cpu_model = result.get("cpu_model")
    if cpu_model:
        cpu_model = str(
            cpu_model
        ).lower()
        if cpu_model not in SUPPORTED_CPUS:
            cpu_model = None
    warnings = result.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    changes = result.get("changes", [])
    if not isinstance(changes, list):
        changes = [str(changes)]
    summary = str(
        result.get(
            "summary",
            "Propuesta generada por OpenAI.",
        )
    )
    return {
        "axes": axes,
        "cpu_model": cpu_model,
        "axis_count": len(axes),
        "summary": summary,
        "changes": changes,
        "warnings": warnings,
        "source": "openai",
    }
# ============================================================
# TRANSCRIPCIÓN DE VOZ
# ============================================================
def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "voice.wav",
) -> str:
    key = os.getenv(
        "OPENAI_API_KEY",
        ""
    ).strip()
    if not key:
        raise RuntimeError(
            "La voz requiere configurar "
            "OPENAI_API_KEY en Railway."
        )
    from openai import OpenAI
    client = OpenAI(
        api_key=key
    )
    stream = io.BytesIO(audio_bytes)
    stream.name = filename
    result = client.audio.transcriptions.create(
        model=os.getenv(
            "OPENAI_TRANSCRIPTION_MODEL",
            "gpt-4o-mini-transcribe",
        ),
        file=stream,
    )
    return result.text
# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================
def interpret(
    prompt: str,
    current_axes: List[Dict[str, Any]],
    current_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Intenta primero interpretar mediante OpenAI.
    Si OpenAI no está disponible o devuelve una respuesta
    inválida, utiliza automáticamente el parser local.
    """
    try:
        result = _openai_interpret(
            prompt,
            current_axes,
            current_config,
        )
        return result
    except Exception as error:
        # No rompemos la aplicación si OpenAI falla.
        local_result = local_parse(
            prompt,
            current_axes,
            current_config,
        )
        local_result["warnings"].append(
            "OpenAI no disponible; se utilizó "
            "el intérprete local. Detalle: {0}"
            .format(str(error))
        )
        local_result["summary"] = (
            local_result.get("summary", "")
            + "\n\n"
            + "⚠️ OpenAI no disponible; "
              "se utilizó el intérprete local."
        )
        local_result["source"] = "local-fallback"
        return local_result
