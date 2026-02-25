"""Desktop GUI applet for rocket engine pre-design and nozzle visualization."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from engine_design import (
    NozzleConfig,
    generate_nozzle_contour,
    list_fuels,
    list_oxidizers,
    meters_to_unit,
    pressure_to_mpa,
    size_engine,
    thrust_to_newton,
)


class EngineDesignerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Rocket Engine Pre-Design Applet")
        self.root.geometry("1180x760")

        self.fuel_var = tk.StringVar(value="RP-1")
        self.ox_var = tk.StringVar(value="LOX")

        self.thrust_var = tk.StringVar(value="250")
        self.pressure_var = tk.StringVar(value="10")
        self.of_var = tk.StringVar(value="2.6")

        self.thrust_unit_var = tk.StringVar(value="kN")
        self.pressure_unit_var = tk.StringVar(value="MPa")
        self.length_unit_var = tk.StringVar(value="mm")

        self.nozzle_type_var = tk.StringVar(value="Parabolic")
        self.expansion_ratio_var = tk.StringVar(value="40")
        self.conical_half_angle_var = tk.StringVar(value="15")
        self.bell_length_percent_var = tk.StringVar(value="80")

        self.summary_var = tk.StringVar(value="Run design to compute engine parameters and plot nozzle contour.")

        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text="Rocket Engine Thermochemistry + Nozzle Sizing",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor=tk.W, pady=(0, 10))

        paned = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=8)
        right = ttk.Frame(paned, padding=8)
        paned.add(left, weight=1)
        paned.add(right, weight=1)

        self._build_propellant_inputs(left)
        self._build_nozzle_inputs(left)
        self._build_controls(left)

        self._build_results(right)
        self._build_nozzle_plot(right)

    def _build_propellant_inputs(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Mission / Propellant Inputs", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, text="Fuel").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(group, textvariable=self.fuel_var, values=list_fuels(), state="readonly", width=16).grid(
            row=0, column=1, sticky=tk.W, pady=2
        )

        ttk.Label(group, text="Oxidizer").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(
            group,
            textvariable=self.ox_var,
            values=list_oxidizers(),
            state="readonly",
            width=16,
        ).grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(group, text="Desired thrust").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.thrust_var, width=12).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Combobox(
            group,
            textvariable=self.thrust_unit_var,
            values=["N", "kN", "lbf"],
            state="readonly",
            width=8,
        ).grid(row=2, column=2, sticky=tk.W, padx=(6, 0), pady=2)

        ttk.Label(group, text="Chamber pressure").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.pressure_var, width=12).grid(row=3, column=1, sticky=tk.W, pady=2)
        ttk.Combobox(
            group,
            textvariable=self.pressure_unit_var,
            values=["MPa", "bar", "psi"],
            state="readonly",
            width=8,
        ).grid(row=3, column=2, sticky=tk.W, padx=(6, 0), pady=2)

        ttk.Label(group, text="O/F ratio").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.of_var, width=12).grid(row=4, column=1, sticky=tk.W, pady=2)

    def _build_nozzle_inputs(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Nozzle Configuration", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, text="Nozzle type").grid(row=0, column=0, sticky=tk.W, pady=2)
        nozzle_box = ttk.Combobox(
            group,
            textvariable=self.nozzle_type_var,
            values=["Conical", "Parabolic"],
            state="readonly",
            width=14,
        )
        nozzle_box.grid(row=0, column=1, sticky=tk.W, pady=2)
        nozzle_box.bind("<<ComboboxSelected>>", self._toggle_nozzle_fields)

        ttk.Label(group, text="Expansion ratio (Ae/At)").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(group, textvariable=self.expansion_ratio_var, width=12).grid(row=1, column=1, sticky=tk.W, pady=2)

        self.conical_label = ttk.Label(group, text="Conical half-angle (deg)")
        self.conical_label.grid(row=2, column=0, sticky=tk.W, pady=2)
        self.conical_entry = ttk.Entry(group, textvariable=self.conical_half_angle_var, width=12)
        self.conical_entry.grid(row=2, column=1, sticky=tk.W, pady=2)

        self.bell_label = ttk.Label(group, text="Parabolic bell length (%)")
        self.bell_label.grid(row=3, column=0, sticky=tk.W, pady=2)
        self.bell_entry = ttk.Entry(group, textvariable=self.bell_length_percent_var, width=12)
        self.bell_entry.grid(row=3, column=1, sticky=tk.W, pady=2)

        ttk.Label(group, text="Output length unit").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(
            group,
            textvariable=self.length_unit_var,
            values=["mm", "m", "in"],
            state="readonly",
            width=10,
        ).grid(row=4, column=1, sticky=tk.W, pady=2)

        self._toggle_nozzle_fields()

    def _build_controls(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(4, 10))

        ttk.Button(row, text="Run thermochemistry + design", command=self.run_design).pack(side=tk.LEFT)
        ttk.Button(row, text="Reset", command=self.reset_defaults).pack(side=tk.LEFT, padx=8)

    def _build_results(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Engine Sizing Results", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(group, textvariable=self.summary_var, justify=tk.LEFT, wraplength=520).pack(anchor=tk.W)

    def _build_nozzle_plot(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="2D Nozzle Contour", padding=8)
        group.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(group, width=560, height=420, bg="#101218", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_placeholder()

    def _draw_placeholder(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            280,
            210,
            text="Run the design to generate nozzle contour",
            fill="#d5dae3",
            font=("Segoe UI", 12),
        )

    def _toggle_nozzle_fields(self, _: object = None) -> None:
        is_conical = self.nozzle_type_var.get() == "Conical"
        conical_state = "normal" if is_conical else "disabled"
        bell_state = "disabled" if is_conical else "normal"
        self.conical_entry.configure(state=conical_state)
        self.bell_entry.configure(state=bell_state)

    def reset_defaults(self) -> None:
        self.root.destroy()
        new_root = tk.Tk()
        app = EngineDesignerApp(new_root)
        app.run()

    def run_design(self) -> None:
        try:
            thrust_n = thrust_to_newton(float(self.thrust_var.get()), self.thrust_unit_var.get())
            chamber_pressure_mpa = pressure_to_mpa(float(self.pressure_var.get()), self.pressure_unit_var.get())
            of_ratio = float(self.of_var.get())
            expansion_ratio = float(self.expansion_ratio_var.get())
            conical_half_angle_deg = float(self.conical_half_angle_var.get())
            bell_length_percent = float(self.bell_length_percent_var.get())

            if thrust_n <= 0 or chamber_pressure_mpa <= 0 or of_ratio <= 0:
                raise ValueError("Thrust, pressure, and O/F must be positive")
            if expansion_ratio <= 1.0:
                raise ValueError("Expansion ratio must be > 1")
            if not (5.0 <= conical_half_angle_deg <= 30.0):
                raise ValueError("Conical half-angle should be between 5 and 30 deg")
            if not (40.0 <= bell_length_percent <= 120.0):
                raise ValueError("Bell length should be between 40% and 120%")

            nozzle = NozzleConfig(
                nozzle_type=self.nozzle_type_var.get(),
                expansion_ratio=expansion_ratio,
                conical_half_angle_deg=conical_half_angle_deg,
                bell_length_percent=bell_length_percent,
            )

            result = size_engine(
                thrust_n=thrust_n,
                chamber_pressure_mpa=chamber_pressure_mpa,
                of_ratio=of_ratio,
                fuel=self.fuel_var.get(),
                oxidizer=self.ox_var.get(),
                nozzle=nozzle,
            )
            contour = generate_nozzle_contour(result, nozzle)
        except ValueError as err:
            messagebox.showerror("Invalid input", f"Please check your inputs.\n\n{err}")
            return

        unit = self.length_unit_var.get()
        summary = (
            f"Propellants: {self.fuel_var.get()} / {self.ox_var.get()}\n"
            f"Nozzle: {self.nozzle_type_var.get()} | Expansion ratio: {nozzle.expansion_ratio:.1f}\n"
            f"c*: {result.cstar_m_s:.0f} m/s | Isp,vac: {result.isp_vac_s:.1f} s | Cf: {result.cf:.3f}\n"
            f"Mass flow: {result.mass_flow_kg_s:.2f} kg/s\n"
            f"Throat radius: {meters_to_unit(result.throat_radius_m, unit):.2f} {unit}\n"
            f"Exit radius: {meters_to_unit(result.exit_radius_m, unit):.2f} {unit}\n"
            f"Nozzle length: {meters_to_unit(result.nozzle_length_m, unit):.2f} {unit}"
        )
        self.summary_var.set(summary)
        self._draw_contour(contour)

    def _draw_contour(self, contour: list[tuple[float, float]]) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 560)
        height = max(self.canvas.winfo_height(), 420)

        xs = [p[0] for p in contour]
        rs = [p[1] for p in contour]
        x_min, x_max = min(xs), max(xs)
        r_max = max(rs)

        pad = 40
        plot_w = width - 2 * pad
        plot_h = height - 2 * pad

        def to_canvas(x: float, r: float) -> tuple[float, float]:
            x_norm = (x - x_min) / max(x_max - x_min, 1e-6)
            y_norm = r / max(r_max, 1e-6)
            px = pad + x_norm * plot_w
            py = (height / 2.0) - y_norm * (plot_h / 2.0)
            return px, py

        top_points: list[float] = []
        bot_points: list[float] = []
        for x, r in contour:
            tx, ty = to_canvas(x, r)
            bx, by = to_canvas(x, -r)
            top_points.extend([tx, ty])
            bot_points.extend([bx, by])

        self.canvas.create_line(pad, height / 2.0, width - pad, height / 2.0, fill="#3f4656", dash=(3, 4))
        self.canvas.create_line(*top_points, fill="#77d5ff", width=2)
        self.canvas.create_line(*bot_points, fill="#77d5ff", width=2)

        self.canvas.create_text(76, 20, text="2D contour (symmetry shown)", fill="#d5dae3", font=("Segoe UI", 10))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = EngineDesignerApp(root)
    app.run()
