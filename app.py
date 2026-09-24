import json, math, base64
from pathlib import Path
import streamlit as st
from machine_builder_core import *
from auth import init_auth_state, authenticate, logout, change_password, load_users

st.set_page_config(page_title="Lenze Machine Builder Web",page_icon="⚙️",layout="wide")
st.markdown("""<style>
:root{--blue:#3155f5;--navy:#14213d;--muted:#667085;--border:#d8dee9;--bg:#f4f6f9}
[data-testid="stHeader"],#MainMenu,footer{display:none}.block-container{padding-top:.7rem!important;max-width:1220px!important}
[data-testid="stAppViewContainer"]{background:var(--bg)}
.lenze-head{background:#fff;border-bottom:3px solid var(--blue);padding:12px 18px;margin-bottom:14px;display:flex;align-items:center;gap:18px}
.lenze-head img{width:130px;max-height:46px;object-fit:contain}.lenze-title{border-left:1px solid #d7dce5;padding-left:18px}.lenze-title b{font-size:20px;color:var(--navy)}.lenze-title span{display:block;color:var(--muted);font-size:12px}
[data-testid="stExpander"]{background:#fff;border:1px solid var(--border)!important;border-radius:12px!important}
.stButton button,.stDownloadButton button{border-radius:8px;font-weight:600}
</style>""",unsafe_allow_html=True)

TEXTS={
"ES":{"title":"Lenze Machine Builder Web","subtitle":"Generación automática de proyectos PLC Designer","login":"Acceso a Machine Builder","email":"Correo electrónico","password":"Contraseña","signin":"Iniciar sesión","invalid":"Correo o contraseña incorrectos","role":"Permiso","change":"Cambiar contraseña","logout":"Cerrar sesión","current":"Contraseña actual","new":"Nueva contraseña","repeat":"Repetir nueva contraseña","save":"Guardar contraseña","nomatch":"Las contraseñas no coinciden","persist":"Para persistir el cambio tras un redespliegue, actualiza MB_USERS_JSON en Railway.","config":"Configuración","load":"Recuperar configuración","apply":"Aplicar configuración cargada","cpu":"CPU","cpu_desc":"Descriptor CPU","master":"EtherCAT Master","path":"Ruta destino del proyecto PLC Designer","axes_n":"Número de ejes","axes":"Ejes","active":"Activo","name":"Nombre","drive":"Drive","safety":"Safety","desc":"Descriptor","alias2":"Second Alias","kin_param":"Parámetro cinemático","feed":"Feed Constant","cycle":"Cycle Length","calc":"Calcular Feed Constant","calculate":"Calcular","lead":"Paso del husillo [mm/vuelta]","pulley":"Diámetro primitivo de polea [mm]","pinion":"Diámetro primitivo de piñón [mm]","download":"Descargar script PLC Designer","save_json":"Guardar configuración JSON"},
"EN":{"title":"Lenze Machine Builder Web","subtitle":"Automatic PLC Designer project generation","login":"Machine Builder access","email":"Email","password":"Password","signin":"Sign in","invalid":"Incorrect email or password","role":"Role","change":"Change password","logout":"Sign out","current":"Current password","new":"New password","repeat":"Repeat new password","save":"Save password","nomatch":"Passwords do not match","persist":"To persist the change after redeployment, update MB_USERS_JSON in Railway.","config":"Configuration","load":"Load configuration","apply":"Apply uploaded configuration","cpu":"CPU","cpu_desc":"CPU descriptor","master":"EtherCAT Master","path":"PLC Designer project destination path","axes_n":"Number of axes","axes":"Axes","active":"Enabled","name":"Name","drive":"Drive","safety":"Safety","desc":"Descriptor","alias2":"Second Alias","kin_param":"Kinematic parameter","feed":"Feed Constant","cycle":"Cycle Length","calc":"Calculate Feed Constant","calculate":"Calculate","lead":"Lead screw pitch [mm/revolution]","pulley":"Pulley pitch diameter [mm]","pinion":"Pinion pitch diameter [mm]","download":"Download PLC Designer script","save_json":"Save configuration JSON"}}

def t(k): return TEXTS[st.session_state.get("language","ES")].get(k,k)
def fmt(v):
    s=("%.12f"%float(v)).rstrip("0").rstrip("."); return s if "." in s else s+".0"
def feed_calc(mode,value):
    v=float(str(value).replace(",","."))
    if v<=0: raise ValueError("Value must be positive")
    if mode=="ROTARY": return 360.0
    if mode=="LEADSCREW": return v
    if mode in ("BELT","RACK_PINION"): return math.pi*v
    raise ValueError(mode)

def logo_html():
    p=Path(__file__).parent/'Lenze.png'
    if not p.exists(): return '<b style="color:#3155f5;font-size:25px">Lenze</b>'
    data=base64.b64encode(p.read_bytes()).decode(); return f'<img src="data:image/png;base64,{data}" alt="Lenze">'

def language_selector(key):
    choice=st.selectbox("Language",["🇪🇸","🇬🇧"],index=0 if st.session_state.language=="ES" else 1,key=key,label_visibility="collapsed")
    lang="ES" if choice=="🇪🇸" else "EN"
    if lang!=st.session_state.language: st.session_state.language=lang; st.rerun()

def login_view():
    a,b,c=st.columns([1,1.2,1])
    with b:
        st.markdown(f'<div class="lenze-head" style="justify-content:center">{logo_html()}</div>',unsafe_allow_html=True)
        language_selector("login_lang")
        st.title(t("login"))
        with st.form("login"):
            email=st.text_input(t("email")); password=st.text_input(t("password"),type="password")
            submit=st.form_submit_button(t("signin"),use_container_width=True,type="primary")
        if submit:
            ok,_=authenticate(email,password)
            if ok: st.rerun()
            else: st.error(t("invalid"))

def user_menu():
    name=st.session_state.user_name or st.session_state.user_email
    initials="".join(x[0].upper() for x in name.split() if x)[:2] or "US"
    with st.popover(f"{initials}  {name}  ▾",use_container_width=True):
        st.caption(st.session_state.user_email); st.caption(f'{t("role")}: {st.session_state.user_role}')
        action=st.selectbox("",[t("change"),t("logout")],label_visibility="collapsed",key="user_action")
        if action==t("change"):
            with st.form("password_form",clear_on_submit=True):
                cur=st.text_input(t("current"),type="password"); new=st.text_input(t("new"),type="password"); rep=st.text_input(t("repeat"),type="password")
                submit=st.form_submit_button(t("save"),use_container_width=True,type="primary")
            if submit:
                if new!=rep: st.error(t("nomatch"))
                else:
                    ok,msg=change_password(st.session_state.user_email,cur,new)
                    (st.success if ok else st.error)(msg)
                    if ok: st.info(t("persist"))
        elif st.button(t("logout"),use_container_width=True,type="primary"): logout()

def header():
    st.markdown(f'<div class="lenze-head">{logo_html()}<div class="lenze-title"><b>{t("title")}</b><span>{t("subtitle")}</span></div></div>',unsafe_allow_html=True)
    lang,space,user=st.columns([.7,4.8,2.5])
    with lang: language_selector("header_lang")
    with user: user_menu()

init_auth_state()
if not st.session_state.authenticated:
    login_view(); st.stop()
header()

@st.cache_data
def repo_data(): return load_repository()
repo=repo_data()
if "axes" not in st.session_state: st.session_state.axes=[asdict(AxisConfig(name=f"Axis_{i:02d}",station_alias=1000+i,second_station_alias=2000+i)) for i in range(1,3)]
with st.sidebar:
    st.header(t("config")); uploaded=st.file_uploader(t("load"),type=["json"])
    if uploaded and st.button(t("apply"),use_container_width=True):
        data=json.load(uploaded); st.session_state.axes=data.get("axes",st.session_state.axes); st.rerun()
cpu=st.selectbox(t("cpu"),CPU_MODELS,index=CPU_MODELS.index(st.session_state.get("cpu_model","c550")))
copts=cpu_options(repo,cpu); clabels=[f"{d['name']} [{d.get('version','')}]" for d in copts] or ["Sin descriptor"]
cpu_label=st.selectbox(t("cpu_desc"),clabels); cpu_sel=copts[clabels.index(cpu_label)] if copts else {}
masters=master_options(repo); mlabels=[f"{d['name']} [{d.get('version','')}]" for d in masters] or ["Sin descriptor"]
master_label=st.selectbox(t("master"),mlabels); master_sel=masters[mlabels.index(master_label)] if masters else {}
project_path=st.text_input(t("path"),r"C:\Temp\LenzeMachine_Auto.project")
count=st.number_input(t("axes_n"),1,32,len(st.session_state.axes),1)
while len(st.session_state.axes)<count:
    i=len(st.session_state.axes)+1; st.session_state.axes.append(asdict(AxisConfig(name=f"Axis_{i:02d}",station_alias=1000+i,second_station_alias=2000+i)))
st.session_state.axes=st.session_state.axes[:count]
st.subheader(t("axes"))
for i,a in enumerate(st.session_state.axes):
    with st.expander(f"{i+1}: {a.get('name','')}",expanded=i==0):
        c1,c2,c3,c4=st.columns(4); a["enabled"]=c1.checkbox(t("active"),a.get("enabled",True),key=f"en{i}"); a["name"]=c2.text_input(t("name"),a.get("name",f"Axis_{i+1:02d}"),key=f"name{i}"); a["drive_type"]=c3.selectbox(t("drive"),DRIVES,index=DRIVES.index(a.get("drive_type","i950")),key=f"drv{i}")
        sopts=SAFETY if a["drive_type"] in ("i750","i950") else ["Basic Safety"]; a["safety_variant"]=c4.selectbox(t("safety"),sopts,key=f"safe{i}")
        c1,c2,c3,c4=st.columns(4)
        if a["drive_type"]=="i950": a["i950_variant"]=c1.selectbox("i950 Type",["Normal","DC-Link"],key=f"i950{i}")
        else: a["i950_variant"]="Normal"
        opts=drive_options(repo,a["drive_type"],a["safety_variant"],a["i950_variant"]); labels=[f"{d['name']} [{d.get('version','')}]" for d in opts] or ["Sin descriptor"]
        dl=c2.selectbox(t("desc"),labels,key=f"desc{i}"); selected=opts[labels.index(dl)] if opts else {}; a["descriptor_label"]=dl; a["device_id"]=selected.get("device_id","")
        a["station_alias"]=c3.number_input("Alias",0,65535,int(a.get("station_alias",1001)),key=f"al{i}"); a["second_station_alias"]=c4.number_input(t("alias2"),0,65535,int(a.get("second_station_alias",2001)),key=f"al2{i}")
        c1,c2,c3,c4=st.columns(4)
        a["motor_code_c86"]=c1.text_input("C86",a.get("motor_code_c86",""),key=f"c86{i}")
        a["kinematics"]=c2.selectbox("Kinematics",KINEMATICS,index=KINEMATICS.index(a.get("kinematics","ROTARY")),key=f"kin{i}")
        kp_key=f"kp{i}"
        st.session_state.setdefault(kp_key,str(a.get("kinematic_parameter",360)))
        a["kinematic_parameter"]=c3.text_input(t("kin_param"),key=kp_key)
        a["traversing_range"]=c4.selectbox("Traversing Range",TRAVERSING,index=TRAVERSING.index(a.get("traversing_range","MODULO")),key=f"tr{i}")
        zcols=st.columns(4)
        for col,z in zip(zcols,("z1","z2","z3","z4")):
            a[z]=col.number_input(z.upper(),1,1000000,int(a.get(z,1)),key=f"{z}{i}")
        c1,c2,c3=st.columns(3)
        fkey = f"feed{i}"

        # Mantener sincronizado el widget con el modelo
        current_feed = str(
            st.session_state.axes[i].get(
            "feed_constant",
            360.0
        )
    )

    if (
        fkey not in st.session_state
        or
        st.session_state[fkey] != current_feed
    ):
        st.session_state[fkey] = current_feed

        a["feed_constant"] = c1.text_input(
            t("feed"),
            key=fkey
        )
        if a["kinematics"]=="ROTARY":
            a["cycle_length"]=c2.text_input(t("cycle"),str(a.get("cycle_length",360)),key=f"cycle{i}")
        else:
            a["cycle_length"]=0.0
        if c3.button(
            "🧮 " + t("calc"),
            key=f"fc{i}",
            use_container_width=True,
            type="primary"
        ):
            try:

                result = feed_calc(
                    a["kinematics"],
                    a["kinematic_parameter"]
                )

                # Guardar en el modelo de datos,
                # NO en el widget Streamlit
                st.session_state.axes[i]["feed_constant"] = fmt(result)

                st.rerun()

            except Exception as error:
                st.error(str(error))
cfg={"format":"LenzeMachineBuilderWeb","format_version":2,"cpu_model":cpu,"cpu_version":cpu_sel.get("version",""),"cpu_device_id":cpu_sel.get("device_id",cpu_sel.get("type","")),"ethercat_master_label":master_label,"ethercat_master_version":master_sel.get("version",""),"ethercat_master_device_id":master_sel.get("device_id",master_sel.get("type","")),"project_path":project_path,"axes":st.session_state.axes,"robot_groups":[]}
errors=validate_config(cfg)
if errors:
    for e in errors: st.error(e)
else:
    script=generate_plc_script(cfg); c1,c2=st.columns(2); c1.download_button(t("download"),script,"Create_PLCDesigner_Project_Generated.py","text/x-python",use_container_width=True); c2.download_button(t("save_json"),config_json(cfg),"machine_configuration.json","application/json",use_container_width=True)
