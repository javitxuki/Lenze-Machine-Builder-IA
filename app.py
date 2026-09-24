import json
from pathlib import Path
import streamlit as st
from machine_builder_core import *

from auth import init_auth_state, render_login, logout


TEXTS = {
    "ES": {
        "app_title": "Lenze Machine Builder Web",
        "app_caption": "Configura la máquina y descarga el script para ejecutarlo localmente en PLC Designer 4.2.",
        "login_title": "Acceso a Machine Builder",
        "email": "Correo electrónico",
        "password": "Contraseña",
        "sign_in": "Iniciar sesión",
        "invalid_login": "Correo o contraseña incorrectos.",
        "default_credentials_warning": "Credenciales de prueba activas. Configura MB_USERS_JSON en Railway y cambia las contraseñas.",
        "language": "Idioma",
        "user": "Usuario",
        "role": "Permiso",
        "logout": "Cerrar sesión",
        "configuration": "Configuración",
        "recover_configuration": "Recuperar configuración",
        "apply_configuration": "Aplicar configuración cargada",
        "cpu": "CPU",
        "cpu_descriptor": "Descriptor CPU",
        "ethercat_master": "EtherCAT Master",
        "project_path": "Ruta destino del proyecto PLC Designer",
        "axis_count": "Número de ejes",
        "axes": "Ejes",
        "active": "Activo",
        "name": "Nombre",
        "drive": "Drive",
        "safety": "Safety",
        "descriptor": "Descriptor",
        "alias": "Alias",
        "second_alias": "Second Alias",
        "kinematics": "Kinematics",
        "kinematic_parameter": "Parámetro cinemático",
        "traversing_range": "Traversing Range",
        "feed_constant": "Feed Constant",
        "cycle_length": "Cycle Length",
        "download_script": "Descargar script PLC Designer",
        "save_json": "Guardar configuración JSON"
    },
    "EN": {
        "app_title": "Lenze Machine Builder Web",
        "app_caption": "Configure the machine and download the script to run locally in PLC Designer 4.2.",
        "login_title": "Machine Builder access",
        "email": "Email",
        "password": "Password",
        "sign_in": "Sign in",
        "invalid_login": "Incorrect email or password.",
        "default_credentials_warning": "Test credentials are active. Configure MB_USERS_JSON in Railway and change the passwords.",
        "language": "Language",
        "user": "User",
        "role": "Role",
        "logout": "Sign out",
        "configuration": "Configuration",
        "recover_configuration": "Load configuration",
        "apply_configuration": "Apply uploaded configuration",
        "cpu": "CPU",
        "cpu_descriptor": "CPU descriptor",
        "ethercat_master": "EtherCAT Master",
        "project_path": "PLC Designer project destination path",
        "axis_count": "Number of axes",
        "axes": "Axes",
        "active": "Enabled",
        "name": "Name",
        "drive": "Drive",
        "safety": "Safety",
        "descriptor": "Descriptor",
        "alias": "Alias",
        "second_alias": "Second Alias",
        "kinematics": "Kinematics",
        "kinematic_parameter": "Kinematic parameter",
        "traversing_range": "Traversing Range",
        "feed_constant": "Feed Constant",
        "cycle_length": "Cycle Length",
        "download_script": "Download PLC Designer script",
        "save_json": "Save configuration JSON"
    }
}


def t(key):
    language = st.session_state.get("language", "ES")
    return TEXTS.get(language, TEXTS["ES"]).get(key, key)


init_auth_state()
LOGO_PATH = Path(__file__).resolve().parent / "Lenze.png"

# Selector de idioma disponible también antes del login.
language_col, spacer_col = st.columns([1, 5])
with language_col:
    st.selectbox(
        "Language / Idioma",
        ["ES", "EN"],
        key="language"
    )

if not st.session_state.authenticated:
    render_login(t, LOGO_PATH)
    st.stop()


st.set_page_config(page_title="Lenze Machine Builder Web",page_icon="⚙️",layout="wide")
header_logo, header_title, header_user = st.columns([1, 4, 2])
with header_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with header_title:
    st.title(t("app_title"))
    st.caption(t("app_caption"))
with header_user:
    st.write("**{0}:** {1}".format(t("user"), st.session_state.user_email))
    st.write("**{0}:** {1}".format(t("role"), st.session_state.user_role))
    if st.button(t("logout"), use_container_width=True):
        logout()

@st.cache_data
def repo_data(): return load_repository()
repo=repo_data()
if not repo.get("devices"):
    st.warning("No se encontró device_repository.json. Sube o añade el repositorio para disponer de descriptores reales.")

if "axes" not in st.session_state:
    st.session_state.axes=[asdict(AxisConfig(name=f"Axis_{i:02d}",station_alias=1000+i,second_station_alias=2000+i)) for i in range(1,3)]

with st.sidebar:
    st.header(t("configuration"))
    uploaded=st.file_uploader(t("recover_configuration"),type=["json"])
    if uploaded and st.button(t("apply_configuration"),use_container_width=True):
        data=json.load(uploaded); st.session_state.axes=data.get("axes",st.session_state.axes)
        for k,v in data.items():
            if k!="axes": st.session_state[k]=v
        st.rerun()

cpu=st.selectbox(t("cpu"),CPU_MODELS,index=CPU_MODELS.index(st.session_state.get("cpu_model","c550")))
copts=cpu_options(repo,cpu)
clabels=[f"{d['name']} [{d.get('version','')}]" for d in copts] or ["Sin descriptor"]
cpu_label=st.selectbox(t("cpu_descriptor"),clabels)
cpu_sel=copts[clabels.index(cpu_label)] if copts else {}
masters=master_options(repo); mlabels=[f"{d['name']} [{d.get('version','')}]" for d in masters] or ["Sin descriptor"]
master_label=st.selectbox(t("ethercat_master"),mlabels); master_sel=masters[mlabels.index(master_label)] if masters else {}
project_path=st.text_input(t("project_path"),r"C:\Temp\LenzeMachine_Auto.project")
count=st.number_input(t("axis_count"),1,32,len(st.session_state.axes),1)
while len(st.session_state.axes)<count:
    i=len(st.session_state.axes)+1; st.session_state.axes.append(asdict(AxisConfig(name=f"Axis_{i:02d}",station_alias=1000+i,second_station_alias=2000+i)))
if len(st.session_state.axes)>count: st.session_state.axes=st.session_state.axes[:count]

st.subheader(t("axes"))
for i,a in enumerate(st.session_state.axes):
    with st.expander(f"Eje {i+1}: {a.get('name','')}",expanded=(i==0)):
        c1,c2,c3,c4=st.columns(4)
        a["enabled"]=c1.checkbox(t("active"),a.get("enabled",True),key=f"en{i}")
        a["name"]=c2.text_input(t("name"),a.get("name",f"Axis_{i+1:02d}"),key=f"name{i}")
        a["drive_type"]=c3.selectbox(t("drive"),DRIVES,index=DRIVES.index(a.get("drive_type","i950")),key=f"drv{i}")
        saf_opts=SAFETY if a["drive_type"] in ("i750","i950") else ["Basic Safety"]
        a["safety_variant"]=c4.selectbox(t("safety"),saf_opts,key=f"safe{i}")
        c1,c2,c3,c4=st.columns(4)
        if a["drive_type"]=="i950": a["i950_variant"]=c1.selectbox("i950 Type",["Normal","DC-Link"],key=f"i950{i}")
        else: a["i950_variant"]="Normal"
        opts=drive_options(repo,a["drive_type"],a["safety_variant"],a["i950_variant"])
        labels=[f"{d['name']} [{d.get('version','')}]" for d in opts] or ["Sin descriptor"]
        dl=c2.selectbox(t("descriptor"),labels,key=f"desc{i}"); selected=opts[labels.index(dl)] if opts else {}
        a["descriptor_label"]=dl; a["device_id"]=selected.get("device_id","")
        a["station_alias"]=c3.number_input(t("alias"),0,65535,int(a.get("station_alias",1001)),key=f"al{i}")
        a["second_station_alias"]=c4.number_input(t("second_alias"),0,65535,int(a.get("second_station_alias",2001)),key=f"al2{i}")
        c1,c2,c3,c4=st.columns(4)
        a["motor_code_c86"]=c1.text_input("C86",a.get("motor_code_c86",""),key=f"c86{i}")
        a["kinematics"]=c2.selectbox(t("kinematics"),KINEMATICS,index=KINEMATICS.index(a.get("kinematics","ROTARY")),key=f"kin{i}")
        a["kinematic_parameter"]=c3.text_input(t("kinematic_parameter"),str(a.get("kinematic_parameter",360.0)),key=f"kp{i}")
        a["traversing_range"]=c4.selectbox(t("traversing_range"),TRAVERSING,index=TRAVERSING.index(a.get("traversing_range","MODULO")),key=f"tr{i}")
        c1,c2,c3,c4=st.columns(4)
        for col,z in zip((c1,c2,c3,c4),("z1","z2","z3","z4")): a[z]=col.number_input(z.upper(),1,1000000,int(a.get(z,1)),key=f"{z}{i}")
        c1,c2,c3=st.columns(3)
        a["feed_constant"]=c1.text_input(t("feed_constant"),str(a.get("feed_constant",360.0)),key=f"feed{i}")
        if a["kinematics"]=="ROTARY": a["cycle_length"]=c2.text_input(t("cycle_length"),str(a.get("cycle_length",360.0)),key=f"cycle{i}")
        else: a["cycle_length"]=0.0

cfg={"format":"LenzeMachineBuilderWeb","format_version":1,"cpu_model":cpu,"cpu_version":cpu_sel.get("version",""),"cpu_device_id":cpu_sel.get("device_id",cpu_sel.get("type","")),"ethercat_master_label":master_label,"ethercat_master_version":master_sel.get("version",""),"ethercat_master_device_id":master_sel.get("device_id",master_sel.get("type","")),"project_path":project_path,"axes":st.session_state.axes,"robot_groups":[]}
errors=validate_config(cfg)
if errors:
    for e in errors: st.error(e)
else:
    script=generate_plc_script(cfg)
    c1,c2=st.columns(2)
    c1.download_button(t("download_script"),script,"Create_PLCDesigner_Project_Generated.py","text/x-python",use_container_width=True)
    c2.download_button(t("save_json"),config_json(cfg),"machine_configuration.json","application/json",use_container_width=True)
