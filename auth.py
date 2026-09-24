import os, json, hmac
import streamlit as st

_RUNTIME_PASSWORDS={}
DEFAULT_USERS={
 "javier.salvador@lenze.com":{"password":"admin","role":"admin","name":"Javier Salvador"},
 "javisalvador1978@gmail.com":{"password":"admin","role":"user","name":"Usuario de prueba"}
}

def load_users():
    raw=os.getenv("MB_USERS_JSON","").strip()
    if not raw: return DEFAULT_USERS,True
    data=json.loads(raw)
    return {str(k).strip().lower():{"password":str(v.get("password","")),"role":str(v.get("role","user")),"name":str(v.get("name",k))} for k,v in data.items() if isinstance(v,dict)},False

def init_auth_state():
    for k,v in {"authenticated":False,"user_email":"","user_role":"","user_name":"","language":"ES"}.items(): st.session_state.setdefault(k,v)

def authenticate(email,password):
    users,defaults=load_users(); key=str(email).strip().lower(); profile=users.get(key)
    if not profile: return False,defaults
    expected=_RUNTIME_PASSWORDS.get(key,str(profile.get("password","")))
    if not hmac.compare_digest(str(password),expected): return False,defaults
    st.session_state.authenticated=True; st.session_state.user_email=key
    st.session_state.user_role=profile.get("role","user"); st.session_state.user_name=profile.get("name",key)
    return True,defaults

def logout():
    st.session_state.authenticated=False
    for k in ("user_email","user_role","user_name"): st.session_state[k]=""
    st.rerun()

def change_password(email,current,new):
    users,_=load_users(); key=str(email).strip().lower(); profile=users.get(key,{})
    expected=_RUNTIME_PASSWORDS.get(key,str(profile.get("password","")))
    if not hmac.compare_digest(str(current),expected): return False,"La contraseña actual no es correcta."
    if len(str(new))<8: return False,"La nueva contraseña debe tener al menos 8 caracteres."
    if str(new)==str(current): return False,"La nueva contraseña debe ser diferente."
    _RUNTIME_PASSWORDS[key]=str(new); return True,"Contraseña modificada correctamente."
