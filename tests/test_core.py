# -*- coding: utf-8 -*-
"""Pruebas del núcleo, del asistente local y de la autenticación.

    python -m unittest discover -s tests -v
"""
import ast
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import machine_builder_core as core  # noqa: E402


def sample_config(**overrides):
    repo = core.load_repository(ROOT / "device_repository.json")
    cpu = core.cpu_options(repo, "c520")[0]
    master = core.master_options(repo)[0]
    drive = core.drive_options(repo, "i950")[0]
    axes = [
        dict(core.normalize_axis({"name": "Table", "device_id": drive["device_id"],
                                  "kinematics": "ROTARY", "traversing_range": "MODULO",
                                  "feed_constant": 360, "cycle_length": 360,
                                  "z1": 11, "z2": 580}, 1)),
        dict(core.normalize_axis({"name": "Axis_Y", "device_id": drive["device_id"],
                                  "kinematics": "BELT", "kinematic_parameter": 50,
                                  "traversing_range": "LIMITED", "feed_constant": 157.08,
                                  "z3": 3, "z4": 7, "station_alias": 1002,
                                  "second_station_alias": 2002}, 2)),
    ]
    cfg = {
        "cpu_model": "c520", "cpu_device_id": cpu["device_id"],
        "ethercat_master_device_id": master["device_id"],
        "project_path": r"C:\Temp\Máquina.project",
        "axes": axes,
        "robot_groups": [{"name": "Robot1", "type": "CARTESIAN_2D", "axes": {"X": "Table", "Y": "Axis_Y"}}],
    }
    cfg.update(overrides)
    return cfg


class CoreTests(unittest.TestCase):

    def test_feed_constant(self):
        self.assertEqual(core.calculate_feed_constant("ROTARY", 360), 360.0)
        self.assertEqual(core.calculate_feed_constant("LEADSCREW", "5,5"), 5.5)
        self.assertAlmostEqual(core.calculate_feed_constant("BELT", 50), 157.0796, places=3)
        with self.assertRaises(ValueError):
            core.calculate_feed_constant("BELT", 0)

    def test_normalize_axis_maps_ai_values(self):
        a = core.normalize_axis({"safety_variant": "Advanced Safety", "i950_variant": "dc link",
                                 "traversing_range": "LINEAR", "z1": "0"}, 1)
        self.assertEqual(a["safety_variant"], "Extended Safety")
        self.assertEqual(a["i950_variant"], "DC-Link")
        self.assertEqual(a["traversing_range"], "LIMITED")
        self.assertEqual(a["z1"], 1)
        self.assertEqual(core.normalize_axis({"drive_type": "i550", "safety_variant": "Extended Safety"})["safety_variant"],
                         "Basic Safety")

    def test_validation_catches_bad_names_and_aliases(self):
        cfg = sample_config()
        cfg["axes"][1]["name"] = "Eje ñ"
        cfg["axes"][1]["station_alias"] = cfg["axes"][0]["station_alias"]
        errors = core.validate_config(cfg)
        self.assertTrue(any("nombre" in e for e in errors), errors)
        self.assertTrue(any("Alias duplicado" in e for e in errors), errors)

    def test_script_is_ascii_and_compiles(self):
        script = core.generate_plc_script(sample_config())
        script.encode("ascii")  # IronPython 2.7 y "coding: ascii"
        ast.parse(script)
        self.assertNotIn("L_MC1P_ChangeMachineData", script)
        self.assertIn("M\\xe1quina", script)  # la ruta con tilde, escapada

    def test_script_machine_data(self):
        script = core.generate_plc_script(sample_config())
        tree = ast.parse(script)
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
                except Exception:
                    pass
        axes = {a["name"]: dict(a["machine_data"]) for a in values["AXES"]}
        table, belt = axes["Table"], axes["Axis_Y"]
        self.assertEqual(table["MOTION_KIND"], "2")
        self.assertEqual(table["TRAVERSING_RANGE"], "0")
        self.assertEqual(table["CYCLE_LENGTH"], "360.0")
        self.assertEqual(table["GEAR_NUMERATOR"], "580")
        self.assertEqual(table["GEAR_DENOMINATOR"], "11")
        self.assertEqual(belt["MOTION_KIND"], "1")
        self.assertEqual(belt["TRAVERSING_RANGE"], "1")
        self.assertNotIn("CYCLE_LENGTH", belt)
        self.assertEqual(belt["FEED_CONSTANT"], "157.08")
        self.assertEqual(belt["ADD_GEAR_NUMERATOR"], "7")
        self.assertEqual(belt["ADD_GEAR_DENOMINATOR"], "3")
        self.assertEqual(values["PARAMETERS"]["FEED_CONSTANT"], 32)

    def test_drive_options_safety_filters(self):
        repo = core.load_repository(ROOT / "device_repository.json")
        basic = core.drive_options(repo, "i950", "Basic Safety")
        extended = core.drive_options(repo, "i950", "Extended Safety")
        self.assertTrue(basic and extended)
        self.assertFalse({d["device_id"] for d in basic} & {d["device_id"] for d in extended})


class AssistantTests(unittest.TestCase):

    def test_local_parse_uses_app_values(self):
        os.environ.pop("OPENAI_API_KEY", None)
        import ai_assistant
        result = ai_assistant.interpret("2 ejes; eje 1 i950 extended safety dc link modulo; "
                                        "eje 2 i550 belt 50 lineal z1 2", [])
        a1, a2 = result["axes"]
        self.assertEqual(a1["safety_variant"], "Extended Safety")
        self.assertEqual(a1["i950_variant"], "DC-Link")
        self.assertEqual(a1["traversing_range"], "MODULO")
        self.assertEqual(a2["drive_type"], "i550")
        self.assertEqual(a2["kinematics"], "BELT")
        self.assertEqual(a2["traversing_range"], "LIMITED")
        self.assertEqual(a2["z1"], 2)
        for axis in result["axes"]:
            self.assertIn(axis["traversing_range"], core.TRAVERSING)
            self.assertIn(axis["safety_variant"], core.SAFETY)


class AuthTests(unittest.TestCase):

    def test_hash_roundtrip_and_no_default_users(self):
        import auth
        stored = auth.hash_password("secreto123")
        self.assertTrue(auth.verify_password("secreto123", stored))
        self.assertFalse(auth.verify_password("otra", stored))
        os.environ.pop("MB_USERS_JSON", None)
        users, problem = auth.load_users()
        self.assertEqual(users, {})
        self.assertTrue(problem)



class GroupAndIdentificationTests(unittest.TestCase):

    def test_group_order_and_2d_compatibility(self):
        self.assertEqual(core.group_axis_order({"type": "CARTESIAN_3D", "axes": {"Z": "c", "X": "a", "Y": "b"}}),
                         ["a", "b", "c"])
        # un 2D guardado con X/Y: la Y va a A2 (la Z de Portal_2dof)
        self.assertEqual(core.group_axis_order({"type": "CARTESIAN_2D", "axes": {"X": "a", "Y": "b"}}),
                         ["a", "b"])

    def test_script_groups_and_identification(self):
        cfg = sample_config(ethercat_identification="STATION_ALIAS",
                            robot_groups=[{"name": "Portal", "type": "CARTESIAN_2D",
                                           "axes": {"X": "Table", "Z": "Axis_Y"}}])
        tree = ast.parse(core.generate_plc_script(cfg))
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                  and isinstance(n.value, (ast.Constant, ast.List, ast.Dict, ast.Tuple))}
        self.assertEqual(values["IDENTIFICATION_MODE"], 1)
        group = values["ROBOT_GROUPS"][0]
        self.assertEqual(group["device"], [33121, "1028 0124", "4.2.0.0"])
        self.assertEqual(group["order"], ["Table", "Axis_Y"])

    def test_unsupported_group_type_is_an_error(self):
        cfg = sample_config(robot_groups=[{"name": "G", "type": "GANTRY", "axes": {}}])
        self.assertTrue(any("cinemática" in e for e in core.validate_config(cfg)))


if __name__ == "__main__":
    unittest.main()
