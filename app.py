"""Desktop GUI applet for engine pre-design and regenerative cooling optimization."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from cooling_optimizer import EngineInputs, estimate_regen_temperatures, history_to_text, random_search
from engine_design import (
    NozzleConfig,
    generate_engine_contour,
    get_propellant_pair,
    list_fuels,
    list_oxidizers,
    list_pairs_for_fuel,
    meters_to_unit,
    mpa_to_pressure,
    pressure_to_mpa,
    size_engine,
    thrust_to_newton,
)

COOLANT_LIBRARY: dict[str, dict[str, float]] = {
    "RP-1": {"cp": 2100.0, "rho": 810.0, "mu": 0.0018, "k": 0.12},
    "Ethanol": {"cp": 2600.0, "rho": 789.0, "mu": 0.0012, "k": 0.17},
    "Jet-A": {"cp": 2100.0, "rho": 800.0, "mu": 0.0016, "k": 0.13},
    "IPA": {"cp": 2650.0, "rho": 786.0, "mu": 0.0021, "k": 0.14},
    "Liquid Methane": {"cp": 3500.0, "rho": 422.0, "mu": 0.00011, "k": 0.20},
    "Liquid Oxygen": {"cp": 1700.0, "rho": 1140.0, "mu": 0.00019, "k": 0.15},
    "Liquid Hydrogen": {"cp": 9700.0, "rho": 71.0, "mu": 0.000013, "k": 0.10},
}

MATERIALS = {"Copper Alloy": 330.0, "Inconel 718": 11.4, "Stainless Steel": 16.0}


class EngineCoolingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Rocket Engine Design + Regen Cooling")
        self.root.geometry("1250x820")

        self.latest_result = None

        self._init_engine_vars()
        self._init_regen_vars()
        self._build_ui()

    def _init_engine_vars(self) -> None:
        self.fuel_var = tk.StringVar(value="RP-1")
        self.ox_var = tk.StringVar(value="LOX")
        self.of_var = tk.StringVar(value="2.6")
        self.suggested_of_var = tk.StringVar(value="Suggested O/F: --")

        self.thrust_var = tk.StringVar(value="250")
        self.pressure_var = tk.StringVar(value="10")
        self.exit_pressure_var = tk.StringVar(value="0.1")

        self.thrust_unit_var = tk.StringVar(value="kN")
        self.pressure_unit_var = tk.StringVar(value="MPa")
        self.length_unit_var = tk.StringVar(value="mm")

        self.nozzle_type_var = tk.StringVar(value="Parabolic")
        self.conv_angle_var = tk.StringVar(value="30")
        self.div_angle_var = tk.StringVar(value="15")
        self.bell_length_percent_var = tk.StringVar(value="80")

        self.lstar_var = tk.StringVar(value="1.1")
        self.contraction_ratio_var = tk.StringVar(value="4.0")

        self.engine_summary_var = tk.StringVar(value="Run design to compute engine/chamber/nozzle parameters.")

    def _init_regen_vars(self) -> None:
        self.coolant_var = tk.StringVar(value="RP-1")
        self.coolant_mass_flow_var = tk.StringVar(value="2.8")
        self.coolant_inlet_temp_var = tk.StringVar(value="290")
        self.coolant_cp_var = tk.StringVar(value="2100")
        self.coolant_rho_var = tk.StringVar(value="810")
        self.coolant_mu_var = tk.StringVar(value="0.0018")
        self.coolant_k_var = tk.StringVar(value="0.12")

        self.wall_material_var = tk.StringVar(value="Copper Alloy")
        self.wall_thickness_var = tk.StringVar(value="1.2")
        self.heat_flux_var = tk.StringVar(value="12")
        self.wall_length_var = tk.StringVar(value="1.2")
        self.chamber_temp_var = tk.StringVar(value="3500")
        self.gamma_var = tk.StringVar(value="1.22")

        self.bounds_vars = {
            "channel_count": (tk.StringVar(value="120"), tk.StringVar(value="420")),
            "width_mm": (tk.StringVar(value="0.8"), tk.StringVar(value="3.5")),
            "height_mm": (tk.StringVar(value="0.9"), tk.StringVar(value="4.5")),
            "rib_thickness_mm": (tk.StringVar(value="0.5"), tk.StringVar(value="2.4")),
        }
        self.iterations_var = tk.StringVar(value="1400")
        self.regen_summary_var = tk.StringVar(value="Run optimization in Regen tab to estimate channel geometry and temperatures.")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Rocket Engine Preliminary Design Suite",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)

        engine_tab = ttk.Frame(notebook, padding=8)
        regen_tab = ttk.Frame(notebook, padding=8)
        notebook.add(engine_tab, text="Engine Design")
        notebook.add(regen_tab, text="Regen Cooling")

        self._build_engine_tab(engine_tab)
        self._build_regen_tab(regen_tab)

    def _build_engine_tab(self, parent: ttk.Frame) -> None:
        split = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        split.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(split, padding=6)
        right = ttk.Frame(split, padding=6)
        split.add(left, weight=1)
        split.add(right, weight=1)

        self._build_propellant_section(left)
        self._build_chamber_nozzle_section(left)

        buttons = ttk.Frame(left)
        buttons.pack(fill=tk.X, pady=(6, 8))
        ttk.Button(buttons, text="Run engine design", command=self.run_engine_design).pack(side=tk.LEFT)

        result_group = ttk.LabelFrame(right, text="Engine Results", padding=8)
        result_group.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(result_group, textvariable=self.engine_summary_var, justify=tk.LEFT, wraplength=560).pack(anchor=tk.W)

        plot_group = ttk.LabelFrame(right, text="2D Chamber + Nozzle Contour", padding=8)
        plot_group.pack(fill=tk.BOTH, expand=True)
        self.engine_canvas = tk.Canvas(plot_group, width=620, height=500, bg="#11141a", highlightthickness=1)
        self.engine_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_engine_placeholder()

    def _build_propellant_section(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Mission / Propellants", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, text="Fuel").grid(row=0, column=0, sticky=tk.W, pady=2)
        fuel_box = ttk.Combobox(group, textvariable=self.fuel_var, values=list_fuels(), state="readonly", width=16)
        fuel_box.grid(row=0, column=1, sticky=tk.W, pady=2)
        fuel_box.bind("<<ComboboxSelected>>", self.on_fuel_change)

        ttk.Label(group, text="Oxidizer").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.oxidizer_box = ttk.Combobox(group, textvariable=self.ox_var, values=list_oxidizers(), state="readonly", width=16)
        self.oxidizer_box.grid(row=1, column=1, sticky=tk.W, pady=2)
        self.oxidizer_box.bind("<<ComboboxSelected>>", self.update_suggested_of)

        ttk.Label(group, text="O/F ratio").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.of_var, width=12).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(group, textvariable=self.suggested_of_var, foreground="#1f5f9c").grid(row=2, column=2, sticky=tk.W, padx=8)

        ttk.Label(group, text="Thrust").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.thrust_var, width=12).grid(row=3, column=1, sticky=tk.W, pady=2)
        ttk.Combobox(group, textvariable=self.thrust_unit_var, values=["N", "kN", "lbf"], state="readonly", width=8).grid(
            row=3, column=2, sticky=tk.W, padx=6
        )

        ttk.Label(group, text="Chamber pressure").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.pressure_var, width=12).grid(row=4, column=1, sticky=tk.W, pady=2)
        ttk.Combobox(group, textvariable=self.pressure_unit_var, values=["MPa", "bar", "psi"], state="readonly", width=8).grid(
            row=4, column=2, sticky=tk.W, padx=6
        )

        ttk.Label(group, text="Exit pressure").grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.exit_pressure_var, width=12).grid(row=5, column=1, sticky=tk.W, pady=2)
        ttk.Combobox(group, textvariable=self.pressure_unit_var, values=["MPa", "bar", "psi"], state="readonly", width=8).grid(
            row=5, column=2, sticky=tk.W, padx=6
        )

        ttk.Label(group, text="Display length unit").grid(row=6, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(group, textvariable=self.length_unit_var, values=["mm", "m", "in"], state="readonly", width=10).grid(
            row=6, column=1, sticky=tk.W, pady=2
        )

        self.on_fuel_change()

    def _build_chamber_nozzle_section(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Chamber + Nozzle Configuration", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, text="Nozzle type").grid(row=0, column=0, sticky=tk.W, pady=2)
        type_box = ttk.Combobox(group, textvariable=self.nozzle_type_var, values=["Conical", "Parabolic"], state="readonly", width=14)
        type_box.grid(row=0, column=1, sticky=tk.W, pady=2)
        type_box.bind("<<ComboboxSelected>>", self._toggle_nozzle_fields)

        ttk.Label(group, text="Converging half-angle (deg)").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.conv_angle_var, width=12).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(group, text="Diverging half-angle (deg)").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.div_angle_var, width=12).grid(row=2, column=1, sticky=tk.W)

        self.bell_label = ttk.Label(group, text="Bell length (%)")
        self.bell_label.grid(row=3, column=0, sticky=tk.W, pady=2)
        self.bell_entry = ttk.Entry(group, textvariable=self.bell_length_percent_var, width=12)
        self.bell_entry.grid(row=3, column=1, sticky=tk.W)

        ttk.Label(group, text="Characteristic length L* (m)").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.lstar_var, width=12).grid(row=4, column=1, sticky=tk.W)

        ttk.Label(group, text="Contraction ratio (Ac/At)").grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.contraction_ratio_var, width=12).grid(row=5, column=1, sticky=tk.W)

        self._toggle_nozzle_fields()

    def _build_regen_tab(self, parent: ttk.Frame) -> None:
        split = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        split.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(split, padding=6)
        right = ttk.Frame(split, padding=6)
        split.add(left, weight=1)
        split.add(right, weight=1)

        self._build_regen_inputs(left)
        self._build_regen_bounds(left)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(6, 8))
        ttk.Button(controls, text="Load from engine tab", command=self.load_engine_into_regen).pack(side=tk.LEFT)
        ttk.Button(controls, text="Run regen optimization", command=self.run_regen).pack(side=tk.LEFT, padx=8)

        output_group = ttk.LabelFrame(right, text="Regen Results (with Bartz estimate)", padding=8)
        output_group.pack(fill=tk.BOTH, expand=True)
        ttk.Label(output_group, textvariable=self.regen_summary_var, justify=tk.LEFT, wraplength=560).pack(anchor=tk.W)

        self.regen_history = tk.Text(output_group, height=20, wrap=tk.WORD)
        self.regen_history.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.regen_history.configure(state=tk.DISABLED)

    def _build_regen_inputs(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Coolant / Wall Inputs", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, text="Coolant preset").grid(row=0, column=0, sticky=tk.W)
        cb = ttk.Combobox(group, textvariable=self.coolant_var, values=list(COOLANT_LIBRARY.keys()), state="readonly", width=16)
        cb.grid(row=0, column=1, sticky=tk.W)
        cb.bind("<<ComboboxSelected>>", self.on_coolant_change)

        entries = [
            ("Coolant mass flow (kg/s)", self.coolant_mass_flow_var),
            ("Coolant inlet temp (K)", self.coolant_inlet_temp_var),
            ("Coolant Cp (J/kg-K)", self.coolant_cp_var),
            ("Coolant density (kg/m³)", self.coolant_rho_var),
            ("Coolant viscosity (Pa·s)", self.coolant_mu_var),
            ("Coolant k (W/m-K)", self.coolant_k_var),
            ("Heat flux estimate (MW/m²)", self.heat_flux_var),
            ("Hot-wall length (m)", self.wall_length_var),
            ("Gas temperature (K)", self.chamber_temp_var),
            ("Gamma", self.gamma_var),
            ("Wall thickness (mm)", self.wall_thickness_var),
        ]
        for row, (label, var) in enumerate(entries, start=1):
            ttk.Label(group, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            ttk.Entry(group, textvariable=var, width=12).grid(row=row, column=1, sticky=tk.W, pady=2)

        ttk.Label(group, text="Chamber material").grid(row=len(entries) + 1, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(group, textvariable=self.wall_material_var, values=list(MATERIALS.keys()), state="readonly", width=16).grid(
            row=len(entries) + 1, column=1, sticky=tk.W, pady=2
        )

        self.on_coolant_change()

    def _build_regen_bounds(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Geometry Optimization Bounds", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, text="Variable").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(group, text="Min").grid(row=0, column=1)
        ttk.Label(group, text="Max").grid(row=0, column=2)

        for row, key in enumerate(["channel_count", "width_mm", "height_mm", "rib_thickness_mm"], start=1):
            ttk.Label(group, text=key).grid(row=row, column=0, sticky=tk.W, pady=2)
            lo, hi = self.bounds_vars[key]
            ttk.Entry(group, textvariable=lo, width=8).grid(row=row, column=1)
            ttk.Entry(group, textvariable=hi, width=8).grid(row=row, column=2)

        ttk.Label(group, text="Iterations").grid(row=6, column=0, sticky=tk.W, pady=4)
        ttk.Entry(group, textvariable=self.iterations_var, width=8).grid(row=6, column=1, sticky=tk.W)

    def on_fuel_change(self, _: object = None) -> None:
        oxidizers = list_pairs_for_fuel(self.fuel_var.get())
        self.oxidizer_box.configure(values=oxidizers)
        if self.ox_var.get() not in oxidizers and oxidizers:
            self.ox_var.set(oxidizers[0])
        self.update_suggested_of()

    def update_suggested_of(self, _: object = None) -> None:
        try:
            pair = get_propellant_pair(self.fuel_var.get(), self.ox_var.get())
            self.suggested_of_var.set(f"Suggested O/F: {pair.of_opt:.2f}")
            if abs(float(self.of_var.get())) < 1e-9:
                self.of_var.set(f"{pair.of_opt:.2f}")
        except Exception:
            self.suggested_of_var.set("Suggested O/F: --")

    def on_coolant_change(self, _: object = None) -> None:
        preset = COOLANT_LIBRARY[self.coolant_var.get()]
        self.coolant_cp_var.set(str(preset["cp"]))
        self.coolant_rho_var.set(str(preset["rho"]))
        self.coolant_mu_var.set(str(preset["mu"]))
        self.coolant_k_var.set(str(preset["k"]))

    def _toggle_nozzle_fields(self, _: object = None) -> None:
        self.bell_entry.configure(state="disabled" if self.nozzle_type_var.get() == "Conical" else "normal")

    def run_engine_design(self) -> None:
        try:
            thrust_n = thrust_to_newton(float(self.thrust_var.get()), self.thrust_unit_var.get())
            pc_mpa = pressure_to_mpa(float(self.pressure_var.get()), self.pressure_unit_var.get())
            pe_mpa = pressure_to_mpa(float(self.exit_pressure_var.get()), self.pressure_unit_var.get())
            of_ratio = float(self.of_var.get())
            nozzle = NozzleConfig(
                nozzle_type=self.nozzle_type_var.get(),
                exit_pressure_mpa=pe_mpa,
                converging_half_angle_deg=float(self.conv_angle_var.get()),
                conical_half_angle_deg=float(self.div_angle_var.get()),
                bell_length_percent=float(self.bell_length_percent_var.get()),
                lstar_m=float(self.lstar_var.get()),
                contraction_ratio=float(self.contraction_ratio_var.get()),
            )
            if pe_mpa >= pc_mpa:
                raise ValueError("Exit pressure must be below chamber pressure")
            if nozzle.contraction_ratio <= 1.1:
                raise ValueError("Contraction ratio must be > 1.1")

            result = size_engine(thrust_n, pc_mpa, of_ratio, self.fuel_var.get(), self.ox_var.get(), nozzle)
            contour = generate_engine_contour(result, nozzle)
        except ValueError as err:
            messagebox.showerror("Invalid input", str(err))
            return

        self.latest_result = (result, nozzle, pc_mpa)
        u = self.length_unit_var.get()
        pressure_unit = self.pressure_unit_var.get()
        summary = (
            f"{self.fuel_var.get()} / {self.ox_var.get()} | O/F={of_ratio:.2f} (opt {get_propellant_pair(self.fuel_var.get(), self.ox_var.get()).of_opt:.2f})\n"
            f"c*: {result.cstar_m_s:.0f} m/s | Isp,vac: {result.isp_vac_s:.1f} s | Cf: {result.cf:.3f}\n"
            f"Mass flow: {result.mass_flow_kg_s:.2f} kg/s (Fuel {result.fuel_flow_kg_s:.2f}, Ox {result.oxidizer_flow_kg_s:.2f})\n"
            f"Ae/At (computed from Pc/Pe): {result.expansion_ratio:.2f} | Pe: {mpa_to_pressure(nozzle.exit_pressure_mpa, pressure_unit):.3f} {pressure_unit}\n"
            f"Chamber length: {meters_to_unit(result.chamber_length_m, u):.2f} {u} | Chamber radius: {meters_to_unit(result.chamber_radius_m, u):.2f} {u}\n"
            f"Converging length: {meters_to_unit(result.converging_length_m, u):.2f} {u} | Nozzle length: {meters_to_unit(result.nozzle_length_m, u):.2f} {u}"
        )
        self.engine_summary_var.set(summary)
        self._draw_engine_contour(contour, u)

    def _draw_engine_placeholder(self) -> None:
        self.engine_canvas.delete("all")
        self.engine_canvas.create_text(300, 250, text="Run engine design to render chamber + nozzle", fill="#d8dde8")

    def _draw_engine_contour(self, contour: list[tuple[float, float]], unit: str) -> None:
        c = self.engine_canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 620), max(c.winfo_height(), 500)
        pad = 55
        xs = [p[0] for p in contour]
        rs = [p[1] for p in contour]
        x_min, x_max = min(xs), max(xs)
        r_max = max(rs)

        def tx(x: float) -> float:
            return pad + (x - x_min) / max(x_max - x_min, 1e-9) * (w - 2 * pad)

        def ty(r: float) -> float:
            return h / 2 - (r / max(r_max, 1e-9)) * (h / 2 - pad)

        c.create_line(pad, h / 2, w - pad, h / 2, fill="#5f697d")
        c.create_line(pad, pad, pad, h - pad, fill="#5f697d")
        c.create_text(w - 28, h / 2 + 14, text=f"x [{unit}]", fill="#cfd6e3")
        c.create_text(35, pad - 16, text=f"r [{unit}]", fill="#cfd6e3")

        top, bot = [], []
        for x, r in contour:
            top.extend([tx(x), ty(r)])
            bot.extend([tx(x), ty(-r)])
        c.create_line(*top, fill="#77d5ff", width=2)
        c.create_line(*bot, fill="#77d5ff", width=2)

        # Ticks and labels
        for i in range(6):
            xv = x_min + (x_max - x_min) * (i / 5)
            xp = tx(xv)
            c.create_line(xp, h / 2 - 4, xp, h / 2 + 4, fill="#5f697d")
            c.create_text(xp, h / 2 + 18, text=f"{meters_to_unit(xv, unit):.1f}", fill="#cfd6e3", font=("Segoe UI", 8))
        for i in range(5):
            rv = r_max * (i / 4)
            yp = ty(rv)
            c.create_line(pad - 4, yp, pad + 4, yp, fill="#5f697d")
            c.create_text(pad - 22, yp, text=f"{meters_to_unit(rv, unit):.1f}", fill="#cfd6e3", font=("Segoe UI", 8))

    def load_engine_into_regen(self) -> None:
        if self.latest_result is None:
            messagebox.showerror("No engine data", "Run engine design first.")
            return
        result, _, pc_mpa = self.latest_result
        self.coolant_mass_flow_var.set(f"{max(result.fuel_flow_kg_s * 0.9, 0.1):.3f}")
        self.wall_length_var.set(f"{(result.chamber_length_m + result.converging_length_m + result.nozzle_length_m):.3f}")
        self.heat_flux_var.set(f"{(6.0 + 0.9 * pc_mpa):.2f}")
        self.chamber_temp_var.set(f"{result.flame_temp_k:.1f}")
        self.gamma_var.set(f"{result.gamma:.3f}")

    def run_regen(self) -> None:
        try:
            engine = EngineInputs(
                chamber_pressure_mpa=pressure_to_mpa(float(self.pressure_var.get()), self.pressure_unit_var.get()),
                heat_flux_mw_m2=float(self.heat_flux_var.get()),
                coolant_mass_flow_kg_s=float(self.coolant_mass_flow_var.get()),
                coolant_cp_j_kgk=float(self.coolant_cp_var.get()),
                coolant_density_kg_m3=float(self.coolant_rho_var.get()),
                coolant_viscosity_pa_s=float(self.coolant_mu_var.get()),
                coolant_thermal_conductivity_w_mk=float(self.coolant_k_var.get()),
                wall_length_m=float(self.wall_length_var.get()),
            )
            bounds = {k: (float(v[0].get()), float(v[1].get())) for k, v in self.bounds_vars.items()}
            iterations = int(self.iterations_var.get())
            if iterations <= 0:
                raise ValueError("Iterations must be positive")

            best_geom, best_metrics, history = random_search(engine, bounds, iterations=iterations)
            regen = estimate_regen_temperatures(
                engine=engine,
                geometry=best_geom,
                chamber_temp_k=float(self.chamber_temp_var.get()),
                gamma=float(self.gamma_var.get()),
                wall_thermal_conductivity_w_mk=MATERIALS[self.wall_material_var.get()],
                wall_thickness_mm=float(self.wall_thickness_var.get()),
                coolant_inlet_temp_k=float(self.coolant_inlet_temp_var.get()),
            )
        except ValueError as err:
            messagebox.showerror("Invalid input", str(err))
            return

        summary = (
            f"Best geometry: N={best_geom.channel_count}, w={best_geom.width_mm:.2f} mm, h={best_geom.height_mm:.2f} mm, rib={best_geom.rib_thickness_mm:.2f} mm\n"
            f"Pressure drop: {best_metrics['pressure_drop_mpa']:.3f} MPa | Coolant ΔT (geom model): {best_metrics['coolant_delta_t_k']:.1f} K\n"
            f"Bartz q\" estimate: {regen['q_flux_mw_m2']:.2f} MW/m² | h_g: {regen['h_g_w_m2k']:.0f} W/m²-K | h_c: {regen['h_c_w_m2k']:.0f} W/m²-K\n"
            f"Wall hot temp: {regen['wall_hot_k']:.1f} K | Wall cold temp: {regen['wall_cold_k']:.1f} K\n"
            f"Coolant outlet temp: {regen['coolant_outlet_k']:.1f} K (rise {regen['coolant_rise_k']:.1f} K)"
        )
        self.regen_summary_var.set(summary)

        self.regen_history.configure(state=tk.NORMAL)
        self.regen_history.delete("1.0", tk.END)
        self.regen_history.insert("1.0", history_to_text(history, top_n=10))
        self.regen_history.configure(state=tk.DISABLED)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = EngineCoolingApp(root)
    app.run()
