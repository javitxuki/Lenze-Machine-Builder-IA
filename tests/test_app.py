# -*- coding: utf-8 -*-
"""Pruebas de la interfaz con el banco de Streamlit (sin navegador).

    python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from streamlit.testing.v1 import AppTest
except Exception:  # Streamlit no instalado: se saltan estas pruebas
    AppTest = None


def logged_in_app():
    os.environ.pop("OPENAI_API_KEY", None)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["authenticated"] = True
    at.session_state["user_email"] = "test@example.com"
    at.session_state["user_role"] = "admin"
    at.session_state["user_name"] = "Test User"
    return at


@unittest.skipIf(AppTest is None, "Streamlit no está instalado")
class AppTests(unittest.TestCase):

    def test_login_screen_without_users(self):
        os.environ.pop("MB_USERS_JSON", None)
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        self.assertFalse(at.exception, at.exception)
        self.assertTrue(any("MB_USERS_JSON" in e.value for e in at.error))

    def test_main_screen_generates_script(self):
        at = logged_in_app().run()
        self.assertFalse(at.exception, at.exception)
        self.assertFalse(at.error, [e.value for e in at.error])
        self.assertEqual(len(at.session_state["axes"]), 2)

    def test_assistant_proposal_applies_to_every_axis(self):
        at = logged_in_app().run()
        at.chat_input[0].set_value("3 ejes; eje 1 i750 extended safety; eje 2 i550 belt 50; "
                                   "eje 3 i950 dc link leadscrew 10 lineal").run()
        self.assertFalse(at.exception, at.exception)
        apply = [b for b in at.button if "Aplicar propuesta" in b.label][0]
        apply.click().run()
        self.assertFalse(at.exception, at.exception)
        axes = at.session_state["axes"]
        self.assertEqual(len(axes), 3)
        self.assertEqual(at.session_state["drv_0"], "i750")
        self.assertEqual(at.session_state["safe_0"], "Extended Safety")
        self.assertEqual(at.session_state["drv_1"], "i550")
        self.assertEqual(at.session_state["kin_1"], "BELT")
        self.assertEqual(at.session_state["drv_2"], "i950")
        self.assertEqual(at.session_state["i950_2"], "DC-Link")
        self.assertEqual(at.session_state["trav_2"], "LIMITED")

    def test_loaded_configuration_keeps_descriptors(self):
        at = logged_in_app().run()
        axes = [dict(a) for a in at.session_state["axes"]]
        axes[0]["drive_type"] = "i950"
        axes[0]["safety_variant"] = "Extended Safety"
        at.session_state["pending_loaded_configuration"] = {
            "cpu_model": "c520", "project_path": r"C:\Temp\Loaded.project", "axes": axes,
            "robot_groups": [{"name": "R1", "type": "CARTESIAN_2D",
                              "axes": {"X": axes[0]["name"], "Y": axes[1]["name"]}}],
        }
        at.run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(at.session_state["cpu_model"], "c520")
        self.assertEqual(at.session_state["safe_0"], "Extended Safety")
        self.assertEqual(at.session_state["project_path"], r"C:\Temp\Loaded.project")
        self.assertEqual(len(at.session_state["robot_groups"]), 1)


if __name__ == "__main__":
    unittest.main()
