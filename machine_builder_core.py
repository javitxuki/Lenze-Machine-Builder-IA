from __future__ import annotations
import json, re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

CPU_MODELS = ["c430", "c520", "c550"]
DRIVES = ["i550", "i750", "i950"]
SAFETY = ["Basic Safety", "Extended Safety"]
KINEMATICS = ["ROTARY", "LEADSCREW", "BELT", "RACK_PINION"]
TRAVERSING = ["MODULO", "LIMITED"]

@dataclass
class AxisConfig:
    enabled: bool = True
    name: str = "Axis_01"
    drive_type: str = "i950"
    safety_variant: str = "Basic Safety"
    i950_variant: str = "Normal"
    descriptor_label: str = ""
    device_id: str = ""
    station_alias: int = 1001
    second_station_alias: int = 2001
    motor_code_c86: str = ""
    kinematics: str = "ROTARY"
    kinematic_parameter: float = 360.0
    z1: int = 1
    z2: int = 1
    z3: int = 1
    z4: int = 1
    traversing_range: str = "MODULO"
    feed_constant: float = 360.0
    cycle_length: float = 360.0


def version_key(value: str):
    nums=[]
    for x in re.split(r"[^0-9]+", str(value)):
        if x: nums.append(int(x))
    return tuple(nums or [0])


def load_repository(path: str | Path = "device_repository.json") -> dict:
    p=Path(path)
    if not p.exists(): return {"devices": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _devices(repo): return repo.get("devices", []) if isinstance(repo, dict) else []


def cpu_options(repo, model):
    exact=f"Controller {model}".lower()
    values=[d for d in _devices(repo) if str(d.get("name","")).lower()==exact]
    return sorted(values,key=lambda d:version_key(d.get("version","")), reverse=True)


def master_options(repo):
    vals=[]
    for d in _devices(repo):
        n=str(d.get("name","")).lower(); did=str(d.get("device_id",d.get("type","")))
        if "ethercat master" in n and "slave" not in n:
            vals.append({**d,"device_id":did})
    return sorted(vals,key=lambda d:version_key(d.get("version","")), reverse=True)


def drive_options(repo, drive, safety="Basic Safety", i950_variant="Normal"):
    out=[]
    for d in _devices(repo):
        name=str(d.get("name", "")); low=name.lower(); did=str(d.get("device_id",d.get("type","")))
        if drive.lower() not in low: continue
        if not did.startswith("DeviceID(type=65,"): continue
        if drive in ("i750","i950"):
            ext=("extended" in low or "(es" in low)
            if safety=="Extended Safety" and not ext: continue
            if safety=="Basic Safety" and ext: continue
        if drive=="i950":
            dc=("dc-link" in low or "dc link" in low or "dclink" in low)
            if i950_variant=="DC-Link" and not dc: continue
            if i950_variant!="DC-Link" and dc: continue
        out.append({**d,"device_id":did})
    return sorted(out,key=lambda d:version_key(d.get("version","")), reverse=True)


def normalize_number(value):
    return float(str(value).strip().replace(" ","").replace(",","."))


def lreal(value):
    n=normalize_number(value); s=f"{n:.12f}".rstrip("0").rstrip(".")
    return s if "." in s else s+".0"


def validate_config(cfg):
    errors=[]; names=set(); aliases=set(); aliases2=set()
    axes=[a for a in cfg.get("axes",[]) if a.get("enabled",True)]
    if not axes: errors.append("Debe existir al menos un eje activo.")
    for i,a in enumerate(axes,1):
        name=str(a.get("name","")).strip()
        if not name: errors.append(f"Eje {i}: nombre vacío.")
        if name in names: errors.append(f"Nombre duplicado: {name}.")
        names.add(name)
        for key,seen,label in [("station_alias",aliases,"Alias"),("second_station_alias",aliases2,"Second Alias")]:
            v=int(a.get(key,0))
            if v in seen: errors.append(f"{label} duplicado: {v}.")
            seen.add(v)
        for z in ("z1","z2","z3","z4"):
            if int(a.get(z,0))<=0: errors.append(f"{name}: {z.upper()} debe ser mayor que cero.")
        if str(a.get("kinematics","ROTARY")).upper()!="ROTARY": a["cycle_length"]=0.0
    return errors


def config_json(cfg): return json.dumps(cfg,indent=2,ensure_ascii=False)


def axis_st(axes):
    dec=["PROGRAM PLC_PRG","VAR"]; impl=[]
    for a in axes:
        if not a.get("enabled",True): continue
        name=re.sub(r"\W","_",a["name"]); ref="Axis_"+name
        rotary=str(a.get("kinematics","ROTARY")).upper()=="ROTARY"
        tr="L_MC1P_TraversingRange.Modulo" if a.get("traversing_range","MODULO")=="MODULO" else "L_MC1P_TraversingRange.Limited"
        dec += [f"    fbChangeMachineData_{name} : L_MC1P_ChangeMachineData;",f"    xExecuteChangeMachineData_{name} : BOOL := TRUE;",f"    xMachineDataDone_{name} : BOOL;",f"    xMachineDataError_{name} : BOOL;"]
        impl += [f"// Machine data for {a['name']}",f"fbChangeMachineData_{name}(",f"    Axis := {ref},",f"    xExecute := xExecuteChangeMachineData_{name},","    xSetFeedconstant := TRUE,",f"    lrFeedconstant := {lreal(a.get('feed_constant',0))},","    xSetGearFactor := TRUE,",f"    dwGearDenominator := {int(a.get('z1',1))}, // Z1",f"    dwGearNumerator := {int(a.get('z2',1))},   // Z2","    xSetAddGearFactor := TRUE,",f"    dwAddGearDenominator := {int(a.get('z3',1))}, // Z3",f"    dwAddGearNumerator := {int(a.get('z4',1))},   // Z4","    xSetPosResolution := FALSE,","    dwPosResolution := 0,","    xSetOrientation := FALSE,","    xOrientation := FALSE,","    xSetTraversingRange := TRUE,",f"    eTraversingRange := {tr},",f"    xSetCycleLength := {'TRUE' if rotary else 'FALSE'},",f"    lrCycleLength := {lreal(a.get('cycle_length',0) if rotary else 0)}",");","",f"xMachineDataDone_{name} := fbChangeMachineData_{name}.xDone;",f"xMachineDataError_{name} := fbChangeMachineData_{name}.xError;",f"IF xMachineDataDone_{name} OR xMachineDataError_{name} THEN",f"    xExecuteChangeMachineData_{name} := FALSE;","END_IF;",""]
    dec.append("END_VAR")
    return "\n".join(dec)+"\n", "\n".join(impl)


def generate_plc_script(cfg):
    errors=validate_config(cfg)
    if errors: raise ValueError("\n".join(errors))
    axes=[a for a in cfg["axes"] if a.get("enabled",True)]
    declaration,implementation=axis_st(axes)
    slaves=[]
    for a in axes:
        slaves.append({k:a.get(k) for k in ["name","drive_type","safety_variant","i950_variant","descriptor_label","device_id","station_alias","second_station_alias","z1","z2","z3","z4","feed_constant","traversing_range","cycle_length","kinematics"]})
    return f"""# -*- coding: utf-8 -*-
# Generado por Lenze Machine Builder Web
# Ejecutar en PLC Designer 4.2: Tools > Scripting > Execute Script File
import traceback
CPU_MODEL = {cfg['cpu_model']!r}
CPU_VERSION = {cfg.get('cpu_version','')!r}
CPU_DEVICE_ID = {cfg.get('cpu_device_id','')!r}
ETHERCAT_MASTER_DEVICE_ID = {cfg.get('ethercat_master_device_id','')!r}
ETHERCAT_MASTER_VERSION = {cfg.get('ethercat_master_version','')!r}
PROJECT_PATH = {cfg.get('project_path',r'C:\\Temp\\LenzeMachine_Auto.project')!r}
ETHERCAT_SLAVES = {slaves!r}

def log(text): print("[Machine Builder] " + str(text))

def exact_device(search_text, expected_id):
    for d in device_repository.get_all_devices(search_text) or []:
        if str(d.device_id)==str(expected_id): return d
    raise Exception("DeviceId no encontrado: " + str(expected_id))

def find_one(parent,name):
    found=parent.find(name,True)
    return found[0] if found else None

def main():
    project=projects.create(PROJECT_PATH)
    cpu=exact_device("Controller " + CPU_MODEL, CPU_DEVICE_ID)
    project.add(cpu.device_info.default_instance_name,cpu.device_id)
    controller=project.find("Device",True)[0]
    master_desc=exact_device("EtherCAT Master",ETHERCAT_MASTER_DEVICE_ID)
    controller.add("EtherCAT_Master",master_desc.device_id)
    master=project.find("EtherCAT_Master",True)[0]
    sync_desc=None
    for d in device_repository.get_all_devices("Controller Sync Device") or []:
        if "controller" in str(d.device_info.name).lower() and "sync" in str(d.device_info.name).lower(): sync_desc=d; break
    if sync_desc is None: raise Exception("Controller Sync Device no encontrado")
    master.add("Controller_Sync_Device",sync_desc.device_id)
    for slave in ETHERCAT_SLAVES:
        desc=exact_device(slave["drive_type"],slave["device_id"])
        try: master.add(slave["name"],desc.device_id)
        except Exception as error:
            if not project.find(slave["name"],True): raise error
    application=find_one(project,"Application")
    plc_prg=find_one(application,"PLC_PRG")
    if plc_prg is None:
        try:
            plc_prg=application.create_pou("PLC_PRG",PouType.Program)
        except:
            plc_prg=application.create_pou("PLC_PRG")
    plc_prg.textual_declaration.replace({declaration!r})
    plc_prg.textual_implementation.replace({implementation!r})
    task_cfg=find_one(application,"Task Configuration") or application.create_task_configuration()
    task=find_one(task_cfg,"MainTask") or task_cfg.create_task("MainTask")
    task.interval="T#10ms"
    try: task.priority=1
    except: pass
    try: task.pous.add("PLC_PRG")
    except: pass
    project.save()
    log("Proyecto generado: " + PROJECT_PATH)

try: main()
except Exception as error:
    log("ERROR: " + str(error)); traceback.print_exc(); raise
"""
