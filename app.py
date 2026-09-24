import json
import math
import base64
from pathlib import Path

import streamlit as st

from machine_builder_core import *
from auth import init_auth_state, authenticate, logout, change_password

st.set_page_config(
    page_title="Lenze Machine Builder Web",
    page_icon="⚙️",
    layout="wide",
)

st.markdown(
    """
<style>
:root {
    --lenze-blue: #3155f5;
    --lenze-navy: #14213d;
    --lenze-muted: #667085;
    --lenze-border: #d8dee9;
    --lenze-bg: #f4f6f9;
}
[data-testid="stHeader"], #MainMenu, footer { display: none; }
.block-container { padding-top: .7rem !important; max-width: 1220px !important; }
[data-testid="stAppViewContainer"] { background: var(--lenze-bg); }
.lenze-head {
    background: #fff;
    border-bottom: 3px solid var(--lenze-blue);
    padding: 12px 18px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 18px;
}
.lenze-head img { width: 130px; max-height: 46px; object-fit: contain; }
.lenze-title { border-left: 1px solid #d7dce5; padding-left: 18px; }
.lenze-title b { font-size: 20px; color: var(--lenze-navy); }
.lenze-title span { display: block; color: var(--lenze-muted); font-size: 12px; }
[data-testid="stExpander"] {
    background: #fff;
    border: 1px solid var(--lenze-border) !important;
    border-radius: 12px !important;
}
.stButton button, .stDownloadButton button { border-radius: 8px; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

TEXTS = {
    "ES": {
        "title": "Lenze Machine Builder Web",
        "subtitle": "Generación automática de proyectos PLC Designer",
        "login": "Acceso a Machine Builder",
        "email": "Correo electrónico",
        "password": "Contraseña",
        "signin": "Iniciar sesión",
        "invalid": "Correo o contraseña incorrectos",
        "role": "Permiso",
        "change": "Cambiar contraseña",
        "logout": "Cerrar sesión",
        "current": "Contraseña actual",
        "new": "Nueva contraseña",
        "repeat": "Repetir nueva contraseña",
        "save": "Guardar contraseña",
        "nomatch": "Las contraseñas no coinciden",
        "persist": "Para persistir el cambio tras un redespliegue, actualiza MB_USERS_JSON en Railway.",
        "config": "Configuración",
        "load": "Recuperar configuración",
        "apply": "Aplicar configuración cargada",
        "cpu": "CPU",
        "cpu_desc": "Descriptor CPU",
        "master": "EtherCAT Master",
        "path": "Ruta destino del proyecto PLC Designer",
        "axes_n": "Número de ejes",
        "axes": "Ejes",
        "active": "Activo",
        "name": "Nombre",
        "drive": "Drive",
        "safety": "Safety",
        "desc": "Descriptor",
        "alias2": "Second Alias",
        "kin_param": "Parámetro cinemático",
        "feed": "Feed Constant",
        "cycle": "Cycle Length",
        "calc": "Calcular Feed Constant",
        "download": "Descargar script PLC Designer",
        "save_json": "Guardar configuración JSON",
    },
    "EN": {
        "title": "Lenze Machine Builder Web",
        "subtitle": "Automatic PLC Designer project generation",
        "login": "Machine Builder access",
        "email": "Email",
        "password": "Password",
        "signin": "Sign in",
        "invalid": "Incorrect email or password",
        "role": "Role",
        "change": "Change password",
        "logout": "Sign out",
        "current": "Current password",
        "new": "New password",
        "repeat": "Repeat new password",
        "save": "Save password",
        "nomatch": "Passwords do not match",
        "persist": "To persist the change after redeployment, update MB_USERS_JSON in Railway.",
        "config": "Configuration",
        "load": "Load configuration",
        "apply": "Apply uploaded configuration",
        "cpu": "CPU",
        "cpu_desc": "CPU descriptor",
        "master": "EtherCAT Master",
        "path": "PLC Designer project destination path",
        "axes_n": "Number of axes",
        "axes": "Axes",
        "active": "Enabled",
        "name": "Name",
        "drive": "Drive",
        "safety": "Safety",
        "desc": "Descriptor",
        "alias2": "Second Alias",
        "kin_param": "Kinematic parameter",
        "feed": "Feed Constant",
        "cycle": "Cycle Length",
        "calc": "Calculate Feed Constant",
        "download": "Download PLC Designer script",
        "save_json": "Save configuration JSON",
    },
}


def t(key):
    return TEXTS[st.session_state.get("language", "ES")].get(key, key)


def format_decimal(value):
    text = ("%.12f" % float(value)).rstrip("0").rstrip(".")
    return text if "." in text else text + ".0"


def calculate_feed_constant(kinematics, kinematic_parameter):
    value = float(str(kinematic_parameter).strip().replace(",", "."))
    if value <= 0:
        raise ValueError("El parámetro cinemático debe ser mayor que cero.")

    mode = str(kinematics).upper()
    if mode == "ROTARY":
        return 360.0
    if mode == "LEADSCREW":
        return value
    if mode in ("BELT", "RACK_PINION"):
        return math.pi * value
    raise ValueError("Kinematics no reconocida: " + mode)


def logo_html():
    logo_path = Path(__file__).parent / "Lenze.png"
    if not logo_path.exists():
        return '<b style="color:#3155f5;font-size:25px">Lenze</b>'
    payload = base64.b64encode(logo_path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{payload}" alt="Lenze">'


def language_selector(key):
    choice = st.selectbox(
        "Language",
        ["🇪🇸", "🇬🇧"],
        index=0 if st.session_state.language == "ES" else 1,
        key=key,
        label_visibility="collapsed",
    )
    language = "ES" if choice == "🇪🇸" else "EN"
    if language != st.session_state.language:
        st.session_state.language = language
        st.rerun()


def login_view():
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            f'<div class="lenze-head" style="justify-content:center">{logo_html()}</div>',
            unsafe_allow_html=True,
        )
        language_selector("login_language")
        st.title(t("login"))
        with st.form("login_form"):
            email = st.text_input(t("email"))
            password = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(
                t("signin"), use_container_width=True, type="primary"
            )
        if submitted:
            success, _ = authenticate(email, password)
            if success:
                st.rerun()
            else:
                st.error(t("invalid"))


def user_menu():
    name = st.session_state.user_name or st.session_state.user_email
    initials = "".join(part[0].upper() for part in name.split() if part)[:2] or "US"
    with st.popover(f"{initials}  {name}  ▾", use_container_width=True):
        st.caption(st.session_state.user_email)
        st.caption(f'{t("role")}: {st.session_state.user_role}')
        action = st.selectbox(
            "",
            [t("change"), t("logout")],
            label_visibility="collapsed",
            key="user_action",
        )
        if action == t("change"):
            with st.form("password_form", clear_on_submit=True):
                current = st.text_input(t("current"), type="password")
                new = st.text_input(t("new"), type="password")
                repeated = st.text_input(t("repeat"), type="password")
                submitted = st.form_submit_button(
                    t("save"), use_container_width=True, type="primary"
                )
            if submitted:
                if new != repeated:
                    st.error(t("nomatch"))
                else:
                    success, message = change_password(
                        st.session_state.user_email, current, new
                    )
                    (st.success if success else st.error)(message)
                    if success:
                        st.info(t("persist"))
        elif st.button(t("logout"), use_container_width=True, type="primary"):
            logout()


def header():
    st.markdown(
        f'<div class="lenze-head">{logo_html()}'
        f'<div class="lenze-title"><b>{t("title")}</b>'
        f'<span>{t("subtitle")}</span></div></div>',
        unsafe_allow_html=True,
    )
    language_col, _, user_col = st.columns([0.7, 4.8, 2.5])
    with language_col:
        language_selector("header_language")
    with user_col:
        user_menu()


def request_feed_update(axis_index, result):
    """Callback ejecutado antes del rerun de Streamlit."""
    formatted = format_decimal(result)
    st.session_state.axes[axis_index]["feed_constant"] = formatted
    st.session_state[f"feed{axis_index}"] = formatted


init_auth_state()
if not st.session_state.authenticated:
    login_view()
    st.stop()

header()


@st.cache_data
def repo_data():
    return load_repository()


repo = repo_data()

if "axes" not in st.session_state:
    st.session_state.axes = [
        asdict(
            AxisConfig(
                name=f"Axis_{index:02d}",
                station_alias=1000 + index,
                second_station_alias=2000 + index,
            )
        )
        for index in range(1, 3)
    ]

with st.sidebar:
    st.header(t("config"))
    uploaded = st.file_uploader(t("load"), type=["json"])
    if uploaded and st.button(t("apply"), use_container_width=True):
        loaded = json.load(uploaded)
        st.session_state.axes = loaded.get("axes", st.session_state.axes)
        # Eliminar estados de widgets por eje para reconstruirlos con los datos cargados.
        for key in list(st.session_state.keys()):
            if key.startswith(("feed", "kp", "cycle", "en", "name", "drv", "safe")):
                del st.session_state[key]
        st.rerun()

cpu = st.selectbox(
    t("cpu"),
    CPU_MODELS,
    index=CPU_MODELS.index(st.session_state.get("cpu_model", "c550")),
)
cpu_values = cpu_options(repo, cpu)
cpu_labels = [f"{item['name']} [{item.get('version', '')}]" for item in cpu_values] or [
    "Sin descriptor"
]
cpu_label = st.selectbox(t("cpu_desc"), cpu_labels)
cpu_selected = cpu_values[cpu_labels.index(cpu_label)] if cpu_values else {}

master_values = master_options(repo)
master_labels = [
    f"{item['name']} [{item.get('version', '')}]" for item in master_values
] or ["Sin descriptor"]
master_label = st.selectbox(t("master"), master_labels)
master_selected = (
    master_values[master_labels.index(master_label)] if master_values else {}
)

project_path = st.text_input(t("path"), r"C:\Temp\LenzeMachine_Auto.project")
axis_count = st.number_input(t("axes_n"), 1, 32, len(st.session_state.axes), 1)

while len(st.session_state.axes) < axis_count:
    index = len(st.session_state.axes) + 1
    st.session_state.axes.append(
        asdict(
            AxisConfig(
                name=f"Axis_{index:02d}",
                station_alias=1000 + index,
                second_station_alias=2000 + index,
            )
        )
    )
st.session_state.axes = st.session_state.axes[:axis_count]

st.subheader(t("axes"))

for i, axis in enumerate(st.session_state.axes):
    with st.expander(f"{i + 1}: {axis.get('name', '')}", expanded=i == 0):
        col1, col2, col3, col4 = st.columns(4)
        axis["enabled"] = col1.checkbox(
            t("active"), axis.get("enabled", True), key=f"en{i}"
        )
        axis["name"] = col2.text_input(
            t("name"), axis.get("name", f"Axis_{i + 1:02d}"), key=f"name{i}"
        )
        axis["drive_type"] = col3.selectbox(
            t("drive"),
            DRIVES,
            index=DRIVES.index(axis.get("drive_type", "i950")),
            key=f"drv{i}",
        )
        safety_options = (
            SAFETY if axis["drive_type"] in ("i750", "i950") else ["Basic Safety"]
        )
        axis["safety_variant"] = col4.selectbox(
            t("safety"), safety_options, key=f"safe{i}"
        )

        col1, col2, col3, col4 = st.columns(4)
        if axis["drive_type"] == "i950":
            axis["i950_variant"] = col1.selectbox(
                "i950 Type", ["Normal", "DC-Link"], key=f"i950{i}"
            )
        else:
            axis["i950_variant"] = "Normal"

        descriptors = drive_options(
            repo,
            axis["drive_type"],
            axis["safety_variant"],
            axis["i950_variant"],
        )
        descriptor_labels = [
            f"{item['name']} [{item.get('version', '')}]" for item in descriptors
        ] or ["Sin descriptor"]
        descriptor_label = col2.selectbox(t("desc"), descriptor_labels, key=f"desc{i}")
        descriptor_selected = (
            descriptors[descriptor_labels.index(descriptor_label)] if descriptors else {}
        )
        axis["descriptor_label"] = descriptor_label
        axis["device_id"] = descriptor_selected.get("device_id", "")
        axis["station_alias"] = col3.number_input(
            "Alias", 0, 65535, int(axis.get("station_alias", 1001)), key=f"alias{i}"
        )
        axis["second_station_alias"] = col4.number_input(
            t("alias2"),
            0,
            65535,
            int(axis.get("second_station_alias", 2001)),
            key=f"alias2_{i}",
        )

        col1, col2, col3, col4 = st.columns(4)
        axis["motor_code_c86"] = col1.text_input(
            "C86", axis.get("motor_code_c86", ""), key=f"c86{i}"
        )
        axis["kinematics"] = col2.selectbox(
            "Kinematics",
            KINEMATICS,
            index=KINEMATICS.index(axis.get("kinematics", "ROTARY")),
            key=f"kin{i}",
        )
        kinematic_key = f"kp{i}"
        st.session_state.setdefault(
            kinematic_key, str(axis.get("kinematic_parameter", 360.0))
        )
        axis["kinematic_parameter"] = col3.text_input(
            t("kin_param"), key=kinematic_key
        )
        axis["traversing_range"] = col4.selectbox(
            "Traversing Range",
            TRAVERSING,
            index=TRAVERSING.index(axis.get("traversing_range", "MODULO")),
            key=f"traversing{i}",
        )

        z_columns = st.columns(4)
        for column, z_name in zip(z_columns, ("z1", "z2", "z3", "z4")):
            axis[z_name] = column.number_input(
                z_name.upper(),
                1,
                1000000,
                int(axis.get(z_name, 1)),
                key=f"{z_name}_{i}",
            )

        col1, col2, col3 = st.columns(3)
        feed_key = f"feed{i}"
        if feed_key not in st.session_state:
            st.session_state[feed_key] = str(axis.get("feed_constant", 360.0))

        axis["feed_constant"] = col1.text_input(t("feed"), key=feed_key)

        if axis["kinematics"] == "ROTARY":
            axis["cycle_length"] = col2.text_input(
                t("cycle"),
                str(axis.get("cycle_length", 360.0)),
                key=f"cycle{i}",
            )
        else:
            axis["cycle_length"] = 0.0

        # El callback se ejecuta antes del rerun, por lo que puede modificar feed{i}.
        try:
            calculated_feed = calculate_feed_constant(
                axis["kinematics"], axis["kinematic_parameter"]
            )
            col3.button(
                "🧮 " + t("calc"),
                key=f"calculate_feed{i}",
                use_container_width=True,
                type="primary",
                on_click=request_feed_update,
                args=(i, calculated_feed),
            )
        except Exception as error:
            col3.button(
                "🧮 " + t("calc"),
                key=f"calculate_feed{i}",
                use_container_width=True,
                disabled=True,
                help=str(error),
            )

configuration = {
    "format": "LenzeMachineBuilderWeb",
    "format_version": 2,
    "cpu_model": cpu,
    "cpu_version": cpu_selected.get("version", ""),
    "cpu_device_id": cpu_selected.get("device_id", cpu_selected.get("type", "")),
    "ethercat_master_label": master_label,
    "ethercat_master_version": master_selected.get("version", ""),
    "ethercat_master_device_id": master_selected.get(
        "device_id", master_selected.get("type", "")
    ),
    "project_path": project_path,
    "axes": st.session_state.axes,
    "robot_groups": [],
}

validation_errors = validate_config(configuration)
if validation_errors:
    for validation_error in validation_errors:
        st.error(validation_error)
else:
    generated_script = generate_plc_script(configuration)
    left, right = st.columns(2)
    left.download_button(
        t("download"),
        generated_script,
        "Create_PLCDesigner_Project_Generated.py",
        "text/x-python",
        use_container_width=True,
    )
    right.download_button(
        t("save_json"),
        config_json(configuration),
        "machine_configuration.json",
        "application/json",
        use_container_width=True,
    )
