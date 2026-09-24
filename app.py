import json
from pathlib import Path
import streamlit as st
from machine_builder_core import *

from auth import init_auth_state, render_login, logout, change_password


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


for _language, _values in TRANSLATIONS.items():
    TEXTS.setdefault(_language, {}).update(_values)

def t(key):
    language = st.session_state.get("language", "ES")
    return TEXTS.get(language, TEXTS["ES"]).get(key, key)





def calculate_feed_constant(kinematics, parameter_1, parameter_2=0.0):
    import math
    mode = str(kinematics).upper()
    p1 = float(str(parameter_1).replace(",", "."))
    p2 = float(str(parameter_2).replace(",", ".")) if str(parameter_2).strip() else 0.0

    if mode == "ROTARY":
        return 360.0
    if mode == "LEADSCREW":
        # p1 = paso del husillo [mm/vuelta]
        return p1
    if mode == "BELT":
        # p1 = diámetro primitivo de la polea [mm]
        return math.pi * p1
    if mode == "RACK_PINION":
        # p1 = módulo [mm], p2 = número de dientes
        if p2 <= 0:
            raise ValueError("El número de dientes debe ser mayor que cero.")
        return math.pi * p1 * p2
    raise ValueError("Kinematics no reconocida: " + mode)


def format_decimal(value):
    text = "{0:.12f}".format(float(value)).rstrip("0").rstrip(".")
    return text if "." in text else text + ".0"


def render_user_menu():
    menu_label = "👤 " + (st.session_state.get("user_name") or st.session_state.user_email)
    with st.popover(menu_label, use_container_width=True):
        st.caption(st.session_state.user_email)
        st.write("**{0}:** {1}".format(t("role"), st.session_state.user_role))
        action = st.radio(
            t("user_options"),
            [t("change_password"), t("logout")],
            label_visibility="collapsed",
            key="user_menu_action"
        )

        if action == t("change_password"):
            with st.form("change_password_form", clear_on_submit=True):
                current_password = st.text_input(t("current_password"), type="password")
                new_password = st.text_input(t("new_password"), type="password")
                repeat_password = st.text_input(t("repeat_password"), type="password")
                submitted = st.form_submit_button(t("save_password"), use_container_width=True)

            if submitted:
                if new_password != repeat_password:
                    st.error(t("passwords_do_not_match"))
                else:
                    ok, message = change_password(
                        st.session_state.user_email,
                        current_password,
                        new_password
                    )
                    if ok:
                        st.success(message)
                        st.info(t("password_railway_note"))
                    else:
                        st.error(message)
        else:
            if st.button(t("logout"), use_container_width=True, type="primary"):
                logout()

init_auth_state()
LOGO_PATH = Path(__file__).resolve().parent / "Lenze.png"

# Selector compacto visible antes del login.
login_language = st.selectbox(
    "Language / Idioma",
    ["🇪🇸 ES", "🇬🇧 EN"],
    index=0 if st.session_state.get("language", "ES") == "ES" else 1,
    key="login_language_selector"
)
login_language_code = "ES" if login_language.endswith("ES") else "EN"
if login_language_code != st.session_state.get("language", "ES"):
    st.session_state.language = login_language_code
    st.rerun()

if not st.session_state.authenticated:
    render_login(t, LOGO_PATH)
    st.stop()


def render_corporate_header():
    import base64

    logo_html = ""
    if LOGO_PATH.exists():
        encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        suffix = LOGO_PATH.suffix.lower().replace(".", "") or "png"
        logo_html = (
            '<img alt="Lenze" src="data:image/{0};base64,{1}">'.format(
                suffix,
                encoded
            )
        )
    else:
        logo_html = '<strong style="color:#3155f5;font-size:24px">Lenze</strong>'

    st.markdown(
        '''<div class="lenze-shell-header">
            <div class="lenze-brand-area">
                <div class="lenze-logo-wrap">{logo}</div>
                <div class="lenze-product-title">
                    <strong>{title}</strong>
                    <span>{subtitle}</span>
                </div>
            </div>
        </div>'''.format(
            logo=logo_html,
            title=t("app_title"),
            subtitle=t("app_caption")
        ),
        unsafe_allow_html=True
    )

    lang_col, space_col, avatar_col, logout_col = st.columns([1.1, 4.6, 2.2, 1.1])

    with lang_col:
        current = st.session_state.get("language", "ES")
        language_label = st.selectbox(
            t("language"),
            ["🇪🇸 ES", "🇬🇧 EN"],
            index=0 if current == "ES" else 1,
            key="corporate_language_selector",
            label_visibility="collapsed"
        )
        requested_language = "ES" if language_label.endswith("ES") else "EN"
        if requested_language != current:
            st.session_state.language = requested_language
            st.rerun()

    with avatar_col:
        display_name = st.session_state.get("user_name") or st.session_state.get("user_email", "")
        email = st.session_state.get("user_email", "")
        role = st.session_state.get("user_role", "user")
        initials = "".join(
            part[0].upper()
            for part in display_name.replace("@", " ").split()
            if part
        )[:2] or "US"

        st.markdown(
            '''<div style="display:flex;justify-content:flex-end;align-items:center;gap:9px">
                <div style="width:34px;height:34px;border-radius:50%;background:#3155f5;
                            color:white;display:flex;align-items:center;justify-content:center;
                            font-weight:700;font-size:12px">{initials}</div>
                <div class="lenze-user-summary">
                    <div class="name">{name}</div>
                    <div class="mail">{email}</div>
                    <span class="lenze-role-pill">{role}</span>
                </div>
            </div>'''.format(
                initials=initials,
                name=display_name,
                email=email,
                role=role
            ),
            unsafe_allow_html=True
        )

    with logout_col:
        render_user_menu()



st.set_page_config(page_title="Lenze Machine Builder Web",page_icon="⚙️",layout="wide")

# ---- LENZE CORPORATE UI ------------------------------------------------------
st.markdown("""
<style>
:root {
    --lenze-blue: #3155f5;
    --lenze-blue-dark: #1f3fc7;
    --lenze-navy: #14213d;
    --lenze-text: #273248;
    --lenze-muted: #667085;
    --lenze-border: #d8dee9;
    --lenze-bg: #f4f6f9;
    --lenze-card: #ffffff;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--lenze-bg);
    color: var(--lenze-text);
}

[data-testid="stHeader"], #MainMenu, footer {
    display: none;
}

[data-testid="stAppViewBlockContainer"] {
    padding-top: 0.65rem;
    padding-bottom: 3rem;
    max-width: 1220px;
}

.block-container {
    padding-top: 0.65rem !important;
    max-width: 1220px !important;
}

/* Cabecera */
.lenze-shell-header {
    background: #ffffff;
    min-height: 68px;
    padding: 0 16px;
    border-bottom: 3px solid var(--lenze-blue);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 28px;
}

.lenze-brand-area {
    display: flex;
    align-items: center;
    min-width: 0;
    flex: 1 1 auto;
}

.lenze-logo-wrap {
    width: 128px;
    min-width: 128px;
    display: flex;
    align-items: center;
}

.lenze-logo-wrap img {
    width: 122px;
    max-height: 44px;
    object-fit: contain;
}

.lenze-product-title {
    margin-left: 18px;
    padding-left: 18px;
    border-left: 1px solid #d6dbe6;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.lenze-product-title strong {
    display: block;
    color: var(--lenze-navy);
    font-size: 17px;
    font-weight: 650;
    line-height: 1.2;
}

.lenze-product-title span {
    color: var(--lenze-muted);
    font-size: 12.5px;
}

/* Tarjetas y controles */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--lenze-border) !important;
    border-radius: 13px !important;
    background: var(--lenze-card) !important;
    box-shadow: 0 2px 8px rgba(22, 34, 58, 0.05);
}

[data-testid="stExpander"] {
    border: 1px solid var(--lenze-border) !important;
    border-radius: 12px !important;
    background: white !important;
    box-shadow: 0 2px 7px rgba(22, 34, 58, 0.045);
    overflow: hidden;
}

[data-testid="stExpander"] summary {
    font-weight: 650;
    color: var(--lenze-navy);
}

h1, h2, h3 {
    color: var(--lenze-navy) !important;
    letter-spacing: -0.015em;
}

h1 { font-size: 1.78rem !important; }
h2 { font-size: 1.34rem !important; }
h3 { font-size: 1.08rem !important; }

.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    min-height: 38px;
}

.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background: var(--lenze-blue) !important;
    border-color: var(--lenze-blue) !important;
}

.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: var(--lenze-blue) !important;
    color: var(--lenze-blue) !important;
}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-testid="stFileUploaderDropzone"] {
    border-radius: 8px !important;
}

/* Barra derecha de usuario */
.lenze-user-summary {
    text-align: right;
    line-height: 1.15;
    margin-top: 6px;
}

.lenze-user-summary .name {
    color: var(--lenze-navy);
    font-weight: 650;
    font-size: 14px;
}

.lenze-user-summary .mail {
    color: var(--lenze-muted);
    font-size: 11px;
}

.lenze-role-pill {
    display: inline-block;
    margin-top: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    background: #edf1ff;
    color: var(--lenze-blue-dark);
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
}

/* Login */
.lenze-login-title {
    text-align: center;
    margin-top: 6px;
    margin-bottom: 18px;
}

@media (max-width: 760px) {
    .lenze-shell-header { padding: 0 8px; }
    .lenze-logo-wrap { width: 94px; min-width: 94px; }
    .lenze-logo-wrap img { width: 90px; }
    .lenze-product-title { margin-left: 8px; padding-left: 8px; }
    .lenze-product-title span { display: none; }
    .lenze-product-title strong { font-size: 14px; }
}
</style>
""", unsafe_allow_html=True)
# -----------------------------------------------------------------------------

render_corporate_header()

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
        feed_key=f"feed{i}"
        if feed_key not in st.session_state:
            st.session_state[feed_key]=str(a.get("feed_constant",360.0))
        a["feed_constant"]=c1.text_input(t("feed_constant"),key=feed_key)

        with c3.popover("🧮 " + t("feed_calculator"), use_container_width=True):
            calc_mode=a["kinematics"]
            if calc_mode=="ROTARY":
                st.info("360° / revolution")
                calc_p1=360.0
                calc_p2=0.0
            elif calc_mode=="LEADSCREW":
                calc_p1=st.number_input(t("lead_pitch"),min_value=0.000001,value=10.0,key=f"calc_p1_{i}")
                calc_p2=0.0
            elif calc_mode=="BELT":
                calc_p1=st.number_input(t("pulley_diameter"),min_value=0.000001,value=100.0,key=f"calc_p1_{i}")
                calc_p2=0.0
            else:
                calc_p1=st.number_input(t("rack_module"),min_value=0.000001,value=2.0,key=f"calc_p1_{i}")
                calc_p2=st.number_input(t("pinion_teeth"),min_value=1,value=20,key=f"calc_p2_{i}")

            if st.button(t("calculate"),key=f"calculate_feed_{i}",use_container_width=True,type="primary"):
                result=calculate_feed_constant(calc_mode,calc_p1,calc_p2)
                st.session_state[feed_key]=format_decimal(result)
                a["feed_constant"]=st.session_state[feed_key]
                st.success(t("calculated_feed") + ": " + st.session_state[feed_key])
                st.rerun()

        if a["kinematics"]=="ROTARY":
            a["cycle_length"]=c2.text_input(t("cycle_length"),str(a.get("cycle_length",360.0)),key=f"cycle{i}")
        else:
            a["cycle_length"]=0.0

cfg={"format":"LenzeMachineBuilderWeb","format_version":1,"cpu_model":cpu,"cpu_version":cpu_sel.get("version",""),"cpu_device_id":cpu_sel.get("device_id",cpu_sel.get("type","")),"ethercat_master_label":master_label,"ethercat_master_version":master_sel.get("version",""),"ethercat_master_device_id":master_sel.get("device_id",master_sel.get("type","")),"project_path":project_path,"axes":st.session_state.axes,"robot_groups":[]}
errors=validate_config(cfg)
if errors:
    for e in errors: st.error(e)
else:
    script=generate_plc_script(cfg)
    c1,c2=st.columns(2)
    c1.download_button(t("download_script"),script,"Create_PLCDesigner_Project_Generated.py","text/x-python",use_container_width=True)
    c2.download_button(t("save_json"),config_json(cfg),"machine_configuration.json","application/json",use_container_width=True)
