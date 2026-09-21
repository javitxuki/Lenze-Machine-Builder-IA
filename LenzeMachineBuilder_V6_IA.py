import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import math

from PIL import Image
from PIL import ImageTk
from PIL import ImageDraw

class LenzeMachineBuilder:

    CPUS = ["c430", "c520", "c550"]

    ROBOT_TYPES = [
        "DELTA_2", "DELTA_3", "DELTA_4", "PORTAL", "BELT_PORTAL",
        "ARTICULATED_P", "SCARA", "LINEAR_DELTA", "ARTICULATED", "CUSTOMIZED"
    ]

    DRIVES = ["i550", "i750", "i950"]

    KINEMATICS = [
        "ROTARY",
        "LEADSCREW",
        "RACK_PINION",
        "BELT",
    ]

    def __init__(self, root):
        self.root = root
        self.root.title("Lenze Machine Builder")
        self.root.geometry("1800x850")
        self.rows = []
        self.robot_groups = []
        self.cpu_model = tk.StringVar(value="")

        # Preparación del futuro asistente IA.
        # Por ahora el modo IA solo muestra la interfaz y no modifica la configuración.
        self.ai_mode = tk.BooleanVar(value=False)
        self.ai_history = []
        self.ai_prompt = ""

        self.main_container = tk.Frame(root)
        self.main_container.pack(fill="both", expand=True)
        self.show_cpu_screen()

    def load_logo(self):
        try:
            logo_path = Path(__file__).parent / "Lenze.png"
            img = Image.open(logo_path)
            img = img.resize((280, 60), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            return True
        except Exception as e:
            print(f"Error cargando logo: {e}")
            return False

    def clear_main_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def show_cpu_screen(self):
        self.clear_main_container()
        self.load_logo()
        header = tk.Frame(self.main_container, bg="#003A70", height=90)
        header.pack(fill="x")
        if hasattr(self, "logo_img"):
            tk.Label(header, image=self.logo_img, bg="#003A70").pack(side="left", padx=20, pady=10)
        tk.Label(header, text="Lenze Machine Builder", font=("Segoe UI", 20, "bold"),
                 fg="white", bg="#003A70").pack(side="left", padx=15)

        card = ttk.LabelFrame(self.main_container, text="1. Selección del controlador", padding=30)
        card.pack(pady=100, padx=30)
        tk.Label(card, text="Modelo de CPU", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, padx=10, pady=15)
        cpu_combo = ttk.Combobox(card, values=self.CPUS, textvariable=self.cpu_model,
                                 state="readonly", width=18, font=("Segoe UI", 12))
        cpu_combo.grid(row=0, column=1, padx=10, pady=15)
        cpu_combo.focus_set()
        tk.Button(card, text="Continuar", command=self.enter_axis_configuration,
                  bg="#003A70", fg="white", font=("Segoe UI", 11, "bold"),
                  padx=25, pady=7).grid(row=1, column=0, columnspan=2, pady=20)

        # El asistente IA también está disponible desde la selección de CPU.
        self.ai_mode.set(False)
        self.create_ai_panel()
        self.create_ai_floating_button()

    def enter_axis_configuration(self):
        if self.cpu_model.get() not in self.CPUS:
            messagebox.showwarning("CPU requerida", "Selecciona un modelo de CPU antes de continuar.")
            return
        self.build_main_screen()

    def build_main_screen(self):
        self.clear_main_container()
        header = tk.Frame(self.main_container, bg="#003A70")
        header.pack(fill="x")
        if hasattr(self, "logo_img"):
            tk.Label(header, image=self.logo_img, bg="#003A70").pack(side="left", padx=10, pady=10)
        tk.Label(header, text="Lenze Machine Builder", font=("Segoe UI", 18, "bold"),
                 fg="white", bg="#003A70").pack(side="left", padx=15)
        tk.Label(header, text=f"CPU: {self.cpu_model.get()}", font=("Segoe UI", 11, "bold"),
                 fg="white", bg="#003A70").pack(side="right", padx=20)

        top = tk.Frame(self.main_container)
        top.pack(fill="x", padx=10, pady=10)
        tk.Button(top, text="< Cambiar CPU", command=self.show_cpu_screen).pack(side="left", padx=5)
        tk.Label(top, text="Número de ejes").pack(side="left", padx=(15, 0))
        self.axis_count = tk.IntVar(value=8)
        tk.Spinbox(top, from_=1, to=64, textvariable=self.axis_count, width=5).pack(side="left", padx=5)
        tk.Button(top, text="Crear ejes", command=self.build_rows).pack(side="left", padx=5)
        tk.Button(top, text="Calcular Feed Constant", command=self.calculate_feed_constants).pack(side="left", padx=5)
        tk.Button(top, text="Generar proyecto", command=self.generate).pack(side="left", padx=20)

        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        axes_tab = tk.Frame(self.notebook)
        self.notebook.add(axes_tab, text="Configuración de ejes")

        # La c430 no dispone de configuración de grupos robóticos.
        # La pestaña y sus widgets solo se crean para c520 y c550.
        if self.cpu_model.get() in ("c520", "c550"):
            groups_tab = tk.Frame(self.notebook)
            self.notebook.add(groups_tab, text="Grupos robóticos")
            self.build_robot_groups_ui(groups_tab)

        self.canvas = tk.Canvas(axes_tab)
        scroll_y = ttk.Scrollbar(axes_tab, orient="vertical", command=self.canvas.yview)
        scroll_x = ttk.Scrollbar(axes_tab, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.build_rows()

        # Selector IA en el extremo opuesto al panel lateral.
        self.ai_mode.set(False)
        self.create_ai_panel()
        self.create_ai_floating_button()

    def create_ai_floating_button(self):
        """Crea el selector IA en la esquina inferior izquierda."""
        self.ai_selector = tk.Checkbutton(
            self.main_container,
            text="IA (Preview)",
            variable=self.ai_mode,
            indicatoron=False,
            command=self.toggle_ai_panel,
            font=("Segoe UI", 12, "bold"),
            bg="#003A70",
            fg="white",
            activebackground="#005A9C",
            activeforeground="white",
            selectcolor="#00A651",
            cursor="hand2",
            padx=24,
            pady=12,
            relief="raised",
            bd=2
        )
        self.ai_selector.place(
            relx=0.0,
            rely=1.0,
            x=40,
            y=-40,
            anchor="sw"
        )
        self.ai_selector.lift()

    def create_microphone_icon(self):
        """Genera una imagen de micrófono integrada para evitar archivos externos."""
        size = 24
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        white = (255, 255, 255, 255)

        # Cápsula del micrófono.
        draw.rounded_rectangle((8, 2, 16, 14), radius=4, fill=white)

        # Soporte y arco inferior.
        draw.arc((5, 7, 19, 19), start=0, end=180, fill=white, width=2)
        draw.line((12, 18, 12, 21), fill=white, width=2)
        draw.line((8, 21, 16, 21), fill=white, width=2)

        return ImageTk.PhotoImage(image)

    def create_ai_panel(self):
        """Crea el panel visual del futuro asistente IA y lo deja oculto."""
        self.ai_frame = ttk.LabelFrame(
            self.main_container,
            text="Asistente IA (Preview)",
            padding=10
        )

        info = tk.Label(
            self.ai_frame,
            text=(
                "Describe la máquina o la configuración en lenguaje natural.\n"
                "Esta versión es solo una vista previa y todavía no procesa peticiones."
            ),
            justify="left",
            anchor="w",
            wraplength=330
        )
        info.pack(fill="x", pady=(0, 10))

        self.ai_chat = tk.Text(
            self.ai_frame,
            width=44,
            height=24,
            state="disabled",
            wrap="word",
            font=("Segoe UI", 10)
        )
        self.ai_chat.pack(fill="both", expand=True, pady=(0, 10))

        input_frame = tk.Frame(self.ai_frame)
        input_frame.pack(fill="x")

        self.ai_input = tk.Entry(
            input_frame,
            font=("Segoe UI", 10)
        )
        self.ai_input.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.ai_input.bind("<Return>", lambda event: self.ai_send_message())

        # Selector de micrófono para simular la futura interacción por voz.
        # El icono se genera como imagen, por lo que no necesita archivos externos.
        self.ai_voice_enabled = tk.BooleanVar(value=False)
        self.mic_icon = self.create_microphone_icon()

        self.ai_voice_btn = tk.Checkbutton(
            input_frame,
            image=self.mic_icon,
            variable=self.ai_voice_enabled,
            indicatoron=False,
            bg="#404040",
            activebackground="#606060",
            selectcolor="#00A651",
            cursor="hand2",
            command=self.ai_voice_preview,
            width=34,
            height=30,
            bd=2,
            relief="raised",
            offrelief="raised",
            overrelief="raised"
        )
        self.ai_voice_btn.pack(side="right", padx=(0, 5))

        self.ai_send = tk.Button(
            input_frame,
            text="Enviar",
            command=self.ai_send_message,
            bg="#003A70",
            fg="white",
            activebackground="#005A9C",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=12
        )
        self.ai_send.pack(side="right", padx=(0, 5))

        self.ai_frame.place_forget()

    def toggle_ai_panel(self):
        """Muestra u oculta el panel de IA según el estado del selector."""
        if self.ai_mode.get():
            self.ai_frame.place(
                relx=1.0,
                rely=0.0,
                x=-18,
                y=94,
                width=390,
                relheight=1.0,
                height=-155,
                anchor="ne"
            )
            self.ai_frame.lift()
            self.ai_selector.lift()
            self.ai_input.focus_set()
        else:
            self.ai_frame.place_forget()

    def ai_voice_preview(self):
        """Activa o desactiva visualmente la futura interacción por voz."""
        if self.ai_voice_enabled.get():
            self.ai_voice_btn.configure(relief="sunken")
            preview_text = (
                "Voz activada (Preview): el micrófono permanecerá marcado. "
                "La interacción por voz estará disponible en una futura versión.\n\n"
            )
        else:
            self.ai_voice_btn.configure(relief="raised")
            preview_text = "Voz desactivada (Preview).\n\n"

        self.ai_chat.configure(state="normal")
        self.ai_chat.insert(tk.END, preview_text)
        self.ai_chat.configure(state="disabled")
        self.ai_chat.see(tk.END)

    def ai_send_message(self):
        """Registra el texto introducido sin ejecutar todavía ninguna IA."""
        text = self.ai_input.get().strip()
        if not text:
            return

        self.ai_prompt = text
        self.ai_history.append({"role": "user", "content": text})
        preview_reply = (
            "Función disponible próximamente. En una futura versión podré "
            "generar la configuración, validar errores, crear el proyecto y "
            "preparar la documentación."
        )
        self.ai_history.append({"role": "assistant", "content": preview_reply})

        self.ai_chat.configure(state="normal")
        self.ai_chat.insert(tk.END, f"Usuario: {text}\n")
        self.ai_chat.insert(tk.END, f"IA: {preview_reply}\n\n")
        self.ai_chat.configure(state="disabled")
        self.ai_chat.see(tk.END)
        self.ai_input.delete(0, tk.END)

    def build_robot_groups_ui(self, parent):
        controls = ttk.LabelFrame(parent, text="Nuevo grupo robótico", padding=10)
        controls.pack(fill="x", padx=10, pady=10)
        self.group_name = tk.StringVar(value="RobotGroup_01")
        self.group_type = tk.StringVar(value=self.ROBOT_TYPES[0])
        tk.Label(controls, text="Nombre").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(controls, textvariable=self.group_name, width=25).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(controls, text="Modelo de robot Lenze").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Combobox(controls, values=self.ROBOT_TYPES, textvariable=self.group_type,
                     state="readonly", width=22).grid(row=0, column=3, padx=5, pady=5)
        tk.Label(controls, text="Ejes que componen el grupo (selección múltiple)").grid(
            row=1, column=0, columnspan=2, padx=5, pady=(10, 5), sticky="w")
        self.group_axes_list = tk.Listbox(controls, selectmode=tk.MULTIPLE, exportselection=False,
                                         height=8, width=35)
        self.group_axes_list.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        tk.Button(controls, text="Añadir grupo", command=self.add_robot_group,
                  bg="#003A70", fg="white").grid(row=2, column=2, padx=10, pady=5, sticky="n")

        table_frame = ttk.LabelFrame(parent, text="Grupos configurados", padding=10)
        # Reserva una franja inferior para que el selector IA no se superponga
        # al recuadro ni a los controles de los grupos configurados.
        table_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(10, 90)
        )
        self.groups_tree = ttk.Treeview(table_frame, columns=("name", "type", "axes"), show="headings", height=12)
        self.groups_tree.heading("name", text="Nombre")
        self.groups_tree.heading("type", text="Modelo")
        self.groups_tree.heading("axes", text="Ejes asignados")
        self.groups_tree.column("name", width=220)
        self.groups_tree.column("type", width=200)
        self.groups_tree.column("axes", width=600)
        self.groups_tree.pack(fill="both", expand=True)
        tk.Button(table_frame, text="Eliminar grupo seleccionado", command=self.delete_robot_group).pack(anchor="e", pady=8)

    def refresh_group_axis_list(self):
        if not hasattr(self, "group_axes_list"):
            return
        self.group_axes_list.delete(0, tk.END)
        for i, row in enumerate(self.rows, start=1):
            self.group_axes_list.insert(tk.END, f"Eje {i}: {row[2].get()}")

    def add_robot_group(self):
        name = self.group_name.get().strip()
        selected = [i + 1 for i in self.group_axes_list.curselection()]
        if not name:
            messagebox.showwarning("Nombre requerido", "Introduce un nombre para el grupo robótico.")
            return
        if any(g["name"].lower() == name.lower() for g in self.robot_groups):
            messagebox.showerror("Grupo duplicado", f"Ya existe un grupo llamado {name}.")
            return
        if not selected:
            messagebox.showwarning("Ejes requeridos", "Selecciona al menos un eje para el grupo.")
            return
        already_used = {axis for g in self.robot_groups for axis in g["axes"]}
        duplicated = sorted(set(selected) & already_used)
        if duplicated:
            messagebox.showerror("Ejes ya asignados", "Estos ejes ya pertenecen a otro grupo: " + ", ".join(map(str, duplicated)))
            return
        group = {"name": name, "robot_type": self.group_type.get(), "axes": selected}
        self.robot_groups.append(group)
        self.groups_tree.insert("", tk.END, values=(name, group["robot_type"], ", ".join(map(str, selected))))
        self.group_name.set(f"RobotGroup_{len(self.robot_groups)+1:02}")
        self.group_axes_list.selection_clear(0, tk.END)

    def delete_robot_group(self):
        selected = self.groups_tree.selection()
        if not selected:
            return
        index = self.groups_tree.index(selected[0])
        self.groups_tree.delete(selected[0])
        del self.robot_groups[index]

    def build_rows(self):

        for w in self.frame.winfo_children():
            w.destroy()

        self.rows = []

        headers = [
            "Eje",
            "Activo",
            "Drive",
            "Nombre",
            "Alias",
            "2nd Alias",
            "C86",
            "Kinematics",
            "Diameter/Pitch/Rotation",
            "Z1",
            "Z2",
            "Z3",
            "Z4",
            "Traversing Range",
            "Feed Constant",
            "Cycle"
        ]

        for c, h in enumerate(headers):

            tk.Label(
                self.frame,
                text=h,
                font=("Arial", 10, "bold")
            ).grid(
                row=0,
                column=c,
                padx=3,
                pady=3
            )

        for i in range(self.axis_count.get()):

            en = tk.BooleanVar(value=True)

            drv = tk.StringVar(value="i950")

            nam = tk.StringVar(
                value=f"Axis_{i+1:02}"
            )

            ali = tk.IntVar(value=1001+i)

            ali2 = tk.IntVar(value=2001+i)

            c86 = tk.StringVar()

            kin = tk.StringVar(value="ROTARY")
            kin_value = tk.DoubleVar(value=360.0)

            z1 = tk.DoubleVar(value=1.0)
            z2 = tk.DoubleVar(value=1.0)
            z3 = tk.DoubleVar(value=1.0)
            z4 = tk.DoubleVar(value=1.0)

            trav = tk.StringVar(value="MODULO")

            feed = tk.DoubleVar(value=360.0)

            cycle = tk.DoubleVar(value=360.0)

            tk.Label(
                self.frame,
                text=str(i+1)
            ).grid(row=i+1,column=0)

            tk.Checkbutton(
                self.frame,
                variable=en
            ).grid(row=i+1,column=1)

            ttk.Combobox(
                self.frame,
                values=self.DRIVES,
                textvariable=drv,
                width=8
            ).grid(row=i+1,column=2)

            tk.Entry(
                self.frame,
                textvariable=nam,
                width=20
            ).grid(row=i+1,column=3)

            tk.Entry(
                self.frame,
                textvariable=ali,
                width=10
            ).grid(row=i+1,column=4)

            tk.Entry(
                self.frame,
                textvariable=ali2,
                width=10
            ).grid(row=i+1,column=5)

            tk.Entry(
                self.frame,
                textvariable=c86,
                width=12
            ).grid(row=i+1,column=6)

            kin_combo = ttk.Combobox(
                self.frame,
                values=self.KINEMATICS,
                textvariable=kin,
                width=15

            )

            kin_combo.grid(
                row=i+1,
                column=7
            )

            entry_param = tk.Entry(
                self.frame,
                textvariable=kin_value,
                width=10
            )
            entry_param.grid(
                row=i+1,
                column=8
            )

            tk.Entry(self.frame,textvariable=z1,width=6).grid(row=i+1,column=9)
            tk.Entry(self.frame,textvariable=z2,width=6).grid(row=i+1,column=10)
            tk.Entry(self.frame,textvariable=z3,width=6).grid(row=i+1,column=11)
            tk.Entry(self.frame,textvariable=z4,width=6).grid(row=i+1,column=12)

            ttk.Combobox(
                self.frame,
                values=["LIMITED","MODULO"],
                textvariable=trav,
                width=10,
                state="readonly"
            ).grid(
                row=i+1,
                column=13
            )

            tk.Entry(
                self.frame,
                textvariable=feed,
                width=10
            ).grid(row=i+1,column=14)

            cycle_entry = tk.Entry(
                self.frame,
                textvariable=cycle,
                width=10
            )
            cycle_entry.grid(
                row=i+1,
                column=15
            )

            def update_kinematics(
                event=None,
                kin=kin,
                cycle_entry=cycle_entry,
                entry_param=entry_param,
                cycle=cycle
            ):

                if kin.get() == "ROTARY":

                    cycle_entry.grid()

                    cycle_entry.configure(
                        state="normal"
                    )

                else:

                    cycle.set(0)

                    cycle_entry.grid_remove()



            kin_combo.bind(
                "<<ComboboxSelected>>",
                update_kinematics
            )

            update_kinematics()

            self.rows.append(
                (
                    en,
                    drv,
                    nam,
                    ali,
                    ali2,
                    c86,
                    kin,
                    kin_value,
                    z1,
                    z2,
                    z3,
                    z4,
                    trav,
                    feed,
                    cycle
                )
            )

        self.refresh_group_axis_list()
        if self.robot_groups:
            self.robot_groups.clear()
            for item in self.groups_tree.get_children():
                self.groups_tree.delete(item)

    def calculate_feed_constants(self):

        for row in self.rows:

            (
                en,
                drv,
                nam,
                ali,
                ali2,
                c86,
                kin,
                kin_value,
                z1,
                z2,
                z3,
                z4,
                trav,
                feed,
                cycle
            ) = row

            try:

                ratio = (
                    z2.get() * z4.get()
                ) / (
                    z1.get() * z3.get()
                )

                if kin.get() == "ROTARY":

                    feed.set(
                        cycle.get()
                    )

                elif kin.get() == "LEADSCREW":

                    feed.set(
                        kin_value.get()
                    )

                elif kin.get() == "BELT":

                    feed.set(
                        math.pi *
                        kin_value.get() 
                        
                    )

                elif kin.get() == "RACK_PINION":

                    feed.set(
                        math.pi *
                        kin_value.get()
                        
                    )

            except ZeroDivisionError:

                pass 
        
    def generate(self):

        folder = filedialog.askdirectory(
            title="Selecciona carpeta destino"
        )

        if not folder:
            return

        axes = []

        aliases = set()

        for i, r in enumerate(self.rows,start=1):

            (
                en,
                drv,
                nam,
                ali,
                ali2,
                c86,
                kin,
                kin_value,
                z1,
                z2,
                z3,
                z4,
                trav,
                feed,
                cycle
            ) = r

            if ali.get() in aliases:
                messagebox.showerror(
                    "Error",
                    f"Alias duplicado en eje {i}"
                )
                return

            if ali2.get() in aliases:
                messagebox.showerror(
                    "Error",
                    f"Second Alias duplicado en eje {i}"
                )
                return

            aliases.add(ali.get())
            aliases.add(ali2.get())

            axes.append({

                "id": i,

                "enabled": en.get(),

                "drive_type": drv.get(),

                "name": nam.get(),

                "station_alias": ali.get(),

                "second_station_alias": ali2.get(),

                "motor_code_c86": c86.get(),

                "kinematics": {

                    "type": kin.get(),
                    "kinematic_parameter":
                     kin_value.get(),

                    "z1": z1.get(),
                    "z2": z2.get(),
                    "z3": z3.get(),
                    "z4": z4.get(),

                    "traversing_range": trav.get(),

                    "feed_constant": feed.get(),

                    "cycle": cycle.get()

                }
            })

        # Protección adicional: una c430 nunca guarda grupos robóticos.
        robot_groups_to_export = (
            self.robot_groups
            if self.cpu_model.get() in ("c520", "c550")
            else []
        )

        machine = {
            "machine_name": "LenzeMachine",
            "cpu_model": self.cpu_model.get(),
            "axes": axes,
            "robot_groups": robot_groups_to_export
        }

        out = Path(folder)

        (out / "machine.json").write_text(
            json.dumps(machine,indent=4),
            encoding="utf-8"
        )

        gvl = [
            "VAR_GLOBAL",
            f"gAxis : ARRAY[1..{len(axes)}] OF ST_AxisConfig;",
            "END_VAR"
        ]

        (out / "GVL_Axes.st").write_text(
            "\n".join(gvl),
            encoding="utf-8"
        )

        aliases_st = ["VAR_GLOBAL"]

        aliases_st.append(
            "gAlias : ARRAY[1..%d] OF UINT := [%s];" %
            (
                len(axes),
                ",".join(
                    str(a["station_alias"])
                    for a in axes
                )
            )
        )

        aliases_st.append(
            "END_VAR"
        )

        (out / "GVL_Aliases.st").write_text(
            "\n".join(aliases_st),
            encoding="utf-8"
        )

        manager = [
            f"FOR AxisIdx:=1 TO {len(axes)} DO",
            "",
            "    IF gAxis[AxisIdx].Enabled THEN",
            "",
            "        fbAxisControl[AxisIdx]();",
            "",
            "    END_IF;",
            "",
            "END_FOR;"
        ]

        (out / "AxisManager.st").write_text(
            "\n".join(manager),
            encoding="utf-8"
        )

        kin_st = []

        for axis in axes:

            kin_st.append(
                f"(* {axis['name']} *)"
            )

            kin_st.append(
                f"MotorCodeC86 := '{axis['motor_code_c86']}';"
            )

            kin_st.append(
                f"Z1 := {axis['kinematics']['z1']};"
            )

            kin_st.append(
                f"Z2 := {axis['kinematics']['z2']};"
            )

            kin_st.append(
                f"Z3 := {axis['kinematics']['z3']};"
            )

            kin_st.append(
                f"Z4 := {axis['kinematics']['z4']};"
            )

            kin_st.append(
                f"TraversingRange := {axis['kinematics']['traversing_range']};"
            )

            kin_st.append(
                f"FeedConstant := {axis['kinematics']['feed_constant']};"
            )

            kin_st.append(
                f"Cycle := {axis['kinematics']['cycle']};"
            )

            kin_st.append("")

        (out / "Kinematics.st").write_text(
            "\n".join(kin_st),
            encoding="utf-8"
        )

        # El archivo de grupos robóticos solo se genera para c520 y c550.
        if self.cpu_model.get() in ("c520", "c550"):
            robot_st = [f"(* CPU: {self.cpu_model.get()} *)", "VAR_GLOBAL"]
            for idx, group in enumerate(robot_groups_to_export, start=1):
                axes_text = ",".join(str(a) for a in group["axes"])
                robot_st.append(
                    f"(* Group {idx}: {group['name']} / {group['robot_type']} / Axes [{axes_text}] *)"
                )
            robot_st.append("END_VAR")
            (out / "GVL_RobotGroups.st").write_text(
                "\n".join(robot_st),
                encoding="utf-8"
            )

        messagebox.showinfo(
            "OK",
            "Proyecto generado correctamente"
        )

if __name__ == "__main__":

    root = tk.Tk()

    LenzeMachineBuilder(root)

    root.mainloop()