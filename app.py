"""Desktop GUI applet for regenerative cooling channel optimization."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from cooling_optimizer import EngineInputs, history_to_text, random_search


class CoolingOptimizerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Regenerative Cooling Channel Optimizer")
        self.root.geometry("980x680")

        self.inputs: dict[str, tk.StringVar] = {}
        self.bounds: dict[str, tuple[tk.StringVar, tk.StringVar]] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            main,
            text="Rocket Engine Regenerative Cooling Optimizer",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor=tk.W, pady=(0, 12))

        split = ttk.Panedwindow(main, orient=tk.HORIZONTAL)
        split.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(split, padding=8)
        right = ttk.Frame(split, padding=8)
        split.add(left, weight=1)
        split.add(right, weight=1)

        self._build_engine_input_section(left)
        self._build_bounds_section(left)
        self._build_controls(left)
        self._build_results_section(right)

    def _build_engine_input_section(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Engine & Coolant Inputs", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        fields = [
            ("chamber_pressure_mpa", "Chamber pressure (MPa)", "12.0"),
            ("heat_flux_mw_m2", "Wall heat flux (MW/m²)", "18.0"),
            ("coolant_mass_flow_kg_s", "Coolant mass flow (kg/s)", "2.8"),
            ("coolant_cp_j_kgk", "Coolant Cp (J/kg-K)", "2500"),
            ("coolant_density_kg_m3", "Coolant density (kg/m³)", "820"),
            ("coolant_viscosity_pa_s", "Coolant viscosity (Pa·s)", "0.00045"),
            ("wall_length_m", "Cooling jacket length (m)", "1.1"),
        ]

        for row, (key, label, default) in enumerate(fields):
            ttk.Label(group, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar(value=default)
            ttk.Entry(group, textvariable=var, width=14).grid(row=row, column=1, sticky=tk.E, pady=2)
            self.inputs[key] = var

    def _build_bounds_section(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Geometry Search Bounds", padding=8)
        group.pack(fill=tk.X, pady=(0, 10))

        ranges = [
            ("channel_count", "Channel count", "120", "420"),
            ("width_mm", "Channel width (mm)", "0.8", "3.5"),
            ("height_mm", "Channel height (mm)", "0.9", "4.5"),
            ("rib_thickness_mm", "Rib thickness (mm)", "0.5", "2.4"),
        ]

        ttk.Label(group, text="Variable").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(group, text="Min").grid(row=0, column=1, padx=4)
        ttk.Label(group, text="Max").grid(row=0, column=2, padx=4)

        for row, (key, name, low, high) in enumerate(ranges, start=1):
            ttk.Label(group, text=name).grid(row=row, column=0, sticky=tk.W, pady=2)
            low_var = tk.StringVar(value=low)
            high_var = tk.StringVar(value=high)
            ttk.Entry(group, textvariable=low_var, width=8).grid(row=row, column=1, padx=2)
            ttk.Entry(group, textvariable=high_var, width=8).grid(row=row, column=2, padx=2)
            self.bounds[key] = (low_var, high_var)

        self.iterations = tk.StringVar(value="1800")
        ttk.Label(group, text="Iterations").grid(row=len(ranges) + 1, column=0, sticky=tk.W, pady=(6, 2))
        ttk.Entry(group, textvariable=self.iterations, width=8).grid(row=len(ranges) + 1, column=1, sticky=tk.W)

    def _build_controls(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(row, text="Run optimization", command=self.run_optimization).pack(side=tk.LEFT)
        ttk.Button(row, text="Reset defaults", command=self.reset_defaults).pack(side=tk.LEFT, padx=8)

    def _build_results_section(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Optimization Results", padding=8)
        group.pack(fill=tk.BOTH, expand=True)

        self.summary_var = tk.StringVar(value="Run optimization to see the best channel geometry.")
        ttk.Label(group, textvariable=self.summary_var, justify=tk.LEFT, wraplength=420).pack(anchor=tk.W)

        ttk.Label(group, text="Top candidates:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(8, 4))

        self.history_box = tk.Text(group, height=22, wrap=tk.WORD)
        self.history_box.pack(fill=tk.BOTH, expand=True)
        self.history_box.configure(state=tk.DISABLED)

    def reset_defaults(self) -> None:
        self.root.destroy()
        new_root = tk.Tk()
        app = CoolingOptimizerApp(new_root)
        app.run()

    def run_optimization(self) -> None:
        try:
            engine = EngineInputs(**{k: float(v.get()) for k, v in self.inputs.items()})
            bounds = {
                key: (float(low.get()), float(high.get())) for key, (low, high) in self.bounds.items()
            }
            iterations = int(self.iterations.get())
            if iterations <= 0:
                raise ValueError("Iterations must be positive")
        except ValueError as err:
            messagebox.showerror("Invalid input", f"Please check your inputs.\n\n{err}")
            return

        best_geometry, best_metrics, history = random_search(engine, bounds, iterations=iterations)

        summary = (
            f"Best geometry after {iterations} samples:\n"
            f"• Channels: {best_geometry.channel_count}\n"
            f"• Width: {best_geometry.width_mm:.2f} mm\n"
            f"• Height: {best_geometry.height_mm:.2f} mm\n"
            f"• Rib thickness: {best_geometry.rib_thickness_mm:.2f} mm\n\n"
            f"Predicted performance:\n"
            f"• Pressure drop: {best_metrics['pressure_drop_mpa']:.3f} MPa\n"
            f"• Coolant ΔT: {best_metrics['coolant_delta_t_k']:.1f} K\n"
            f"• Flow area: {best_metrics['total_flow_area_mm2']:.1f} mm²\n"
            f"• Reynolds number: {best_metrics['reynolds']:.0f}\n"
            f"• Manufacturability score: {best_metrics['manufacturability']:.2f}"
        )
        self.summary_var.set(summary)

        self.history_box.configure(state=tk.NORMAL)
        self.history_box.delete("1.0", tk.END)
        self.history_box.insert("1.0", history_to_text(history, top_n=10))
        self.history_box.configure(state=tk.DISABLED)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = CoolingOptimizerApp(root)
    app.run()
