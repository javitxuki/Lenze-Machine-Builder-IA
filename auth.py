import os
import json
import hmac
import streamlit as st

DEFAULT_USERS = {
    "javier.salvador@lenze.com": {
        "password": "admin",
        "role": "admin",
        "name": "Javier Salvador"
    },
    "javisalvador1978@gmail.com": {
        "password": "admin",
        "role": "user",
        "name": "Usuario de prueba"
    }
}


def load_users():
    raw = os.getenv("MB_USERS_JSON", "").strip()
    if not raw:
        return DEFAULT_USERS, True

    try:
        data = json.loads(raw)
    except Exception as error:
        raise RuntimeError("MB_USERS_JSON no contiene un JSON válido: " + str(error))

    if not isinstance(data, dict):
        raise RuntimeError("MB_USERS_JSON debe ser un objeto JSON de usuarios.")

    normalized = {}
    for email, profile in data.items():
        if not isinstance(profile, dict):
            continue
        normalized[str(email).strip().lower()] = {
            "password": str(profile.get("password", "")),
            "role": str(profile.get("role", "user")),
            "name": str(profile.get("name", email))
        }
    return normalized, False


def init_auth_state():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user_email", "")
    st.session_state.setdefault("user_role", "")
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("language", "ES")


def authenticate(email, password):
    users, using_defaults = load_users()
    key = str(email).strip().lower()
    profile = users.get(key)
    if not profile:
        return False, using_defaults

    valid = hmac.compare_digest(
        str(password),
        str(profile.get("password", ""))
    )
    if not valid:
        return False, using_defaults

    st.session_state.authenticated = True
    st.session_state.user_email = key
    st.session_state.user_role = profile.get("role", "user")
    st.session_state.user_name = profile.get("name", key)
    return True, using_defaults


def logout():
    for key in ("authenticated", "user_email", "user_role", "user_name"):
        st.session_state[key] = False if key == "authenticated" else ""
    st.rerun()


def render_login(t, logo_path=None):
    init_auth_state()
    left, center, right = st.columns([1, 1.25, 1])
    with center:
        if logo_path and logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        st.title(t("login_title"))
        with st.form("login_form"):
            email = st.text_input(t("email"))
            password = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(
                t("sign_in"),
                use_container_width=True,
                type="primary"
            )
        if submitted:
            ok, using_defaults = authenticate(email, password)
            if ok:
                st.rerun()
            else:
                st.error(t("invalid_login"))
        _, using_defaults = load_users()
        if using_defaults:
            st.warning(t("default_credentials_warning"))
