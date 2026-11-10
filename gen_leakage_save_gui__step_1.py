#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tk GUI for generating Spectre hierarchical leakage save files."""

import contextlib
import io
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gen_leakage_save import generate
from gui_settings import save_settings, load_settings


class LeakageGeneratorGui:
    def __init__(self, window):
        self.window = window
        self.window.title("Spectre Hierarchical Leakage Save Generator")
        self.window.minsize(720, 430)

        saved = load_settings("generator")
        self.netlist = tk.StringVar(value=saved.get("netlist", ""))
        self.root = tk.StringVar(value=saved.get("root", ""))
        self.supply = tk.StringVar(value=saved.get("supply", ""))
        self.level = tk.StringVar(value=saved.get("level", "3"))
        self.save_file = tk.StringVar(value=saved.get(
            "save_file", str(Path.cwd() / "leakage_save.scs")))
        self.targets_file = tk.StringVar(value=saved.get(
            "targets_file", str(Path.cwd() / "leakage_targets.csv")))
        self.debug = tk.BooleanVar(value=bool(saved.get("debug", False)))
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        frame = ttk.Frame(window, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self._path_row(frame, 0, "Spectre netlist", self.netlist,
                       self._choose_netlist)
        self._entry_row(frame, 1, "Root instance", self.root)
        self._entry_row(frame, 2, "Supply net / terminal", self.supply)
        self._entry_row(frame, 3, "Maximum level", self.level)
        self._path_row(frame, 4, "Save output", self.save_file,
                       lambda: self._choose_output(self.save_file, ".scs"))
        self._path_row(frame, 5, "Targets output", self.targets_file,
                       lambda: self._choose_output(self.targets_file, ".csv"))

        ttk.Checkbutton(frame, text="Debug connectivity mapping",
                        variable=self.debug).grid(row=6, column=1, sticky="w", pady=4)
        ttk.Button(frame, text="Generate", command=self.run).grid(
            row=7, column=1, sticky="w", pady=(8, 8))

        self.log = tk.Text(frame, height=10, wrap="word")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(8, weight=1)

    def _entry_row(self, frame, row, label, variable):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, columnspan=2,
                                                     sticky="ew", pady=3)

    def _path_row(self, frame, row, label, variable, command):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(frame, text="Browse...", command=command).grid(
            row=row, column=2, padx=(8, 0), pady=3)

    def _choose_netlist(self):
        selected = filedialog.askopenfilename(
            title="Select Spectre netlist",
            filetypes=(("Spectre netlist", "*.scs"), ("All files", "*")))
        if selected:
            self.netlist.set(selected)

    def _choose_output(self, variable, extension):
        selected = filedialog.asksaveasfilename(
            initialfile=Path(variable.get()).name,
            defaultextension=extension,
            filetypes=((extension.upper()[1:] + " file", "*" + extension),
                       ("All files", "*")))
        if selected:
            variable.set(selected)

    def _append(self, text):
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")

    def _settings(self):
        return {
            "netlist": self.netlist.get(),
            "root": self.root.get(),
            "supply": self.supply.get(),
            "level": self.level.get(),
            "save_file": self.save_file.get(),
            "targets_file": self.targets_file.get(),
            "debug": bool(self.debug.get()),
        }

    def _save_settings(self, report_error=True):
        try:
            save_settings("generator", self._settings())
        except OSError as error:
            if report_error:
                self._append("WARNING: cannot save GUI settings: " + str(error))
            return False
        return True

    def _close(self):
        self._save_settings(report_error=False)
        self.window.destroy()

    def run(self):
        self.log.delete("1.0", "end")
        try:
            level = int(self.level.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Maximum level must be an integer.")
            return
        if not self.netlist.get() or not self.root.get() or not self.supply.get():
            messagebox.showerror(
                "Missing input", "Netlist, root instance, and supply are required.")
            return

        self._save_settings()

        diagnostics = io.StringIO()
        try:
            with contextlib.redirect_stderr(diagnostics):
                generate(self.netlist.get(), self.root.get(), self.supply.get(), level,
                         self.save_file.get(), self.targets_file.get(), self.debug.get())
        except (OSError, ValueError) as error:
            if diagnostics.getvalue():
                self._append(diagnostics.getvalue())
            self._append("ERROR: " + str(error))
            messagebox.showerror("Generation failed", str(error))
            return

        if diagnostics.getvalue():
            self._append(diagnostics.getvalue())
        self._append("Wrote " + self.save_file.get())
        self._append("Wrote " + self.targets_file.get())
        messagebox.showinfo("Generation complete",
                            "leakage_save.scs and leakage_targets.csv were generated.")


def main():
    window = tk.Tk()
    LeakageGeneratorGui(window)
    window.mainloop()


if __name__ == "__main__":
    main()
