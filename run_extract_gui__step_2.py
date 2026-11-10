#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tk GUI launcher for the OCEAN leakage extractor."""

import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gui_settings import load_settings, save_settings
from rank_leakage import generate_report
from run_extract import run_extraction


def extract_and_rank(psf, targets, current_output, report_output, time_value=None,
                     start=None, stop=None, ocean="ocean", output_callback=None):
    """Run OCEAN extraction and immediately generate the ranking report."""
    code = run_extraction(psf, targets, current_output, time_value, start, stop,
                          ocean, output_callback)
    if code:
        raise RuntimeError("OCEAN exited with status {}".format(code))
    if output_callback:
        output_callback("Step 2/2: Generating leakage ranking...")
    return generate_report(current_output, report_output)


class LeakageExtractorGui:
    def __init__(self, window):
        self.window = window
        self.window.title("Spectre Leakage Current Extractor")
        self.window.minsize(760, 440)

        cwd = Path.cwd()
        saved = load_settings("extractor")
        self.psf = tk.StringVar(value=saved.get("psf", str(cwd / "psf")))
        self.targets = tk.StringVar(value=saved.get(
            "targets", str(cwd / "leakage_targets.csv")))
        self.output = tk.StringVar(value=saved.get(
            "output", str(cwd / "leakage_current.csv")))
        self.report_output = tk.StringVar(value=saved.get(
            "report_output", str(cwd / "leakage_report.txt")))
        self.mode = tk.StringVar(value=saved.get("mode", "average"))
        self.time_value = tk.StringVar(value=saved.get("time_value", "10u"))
        self.start = tk.StringVar(value=saved.get("start", "9u"))
        self.stop = tk.StringVar(value=saved.get("stop", "10u"))
        self.ocean = tk.StringVar(value=saved.get("ocean", "ocean"))
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        frame = ttk.Frame(window, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self._path_row(frame, 0, "PSF directory", self.psf, self._choose_psf)
        self._path_row(frame, 1, "Targets CSV", self.targets, self._choose_targets)
        self._path_row(frame, 2, "Current CSV output", self.output, self._choose_output)
        self._path_row(frame, 3, "Ranking report output", self.report_output,
                       self._choose_report_output)

        ttk.Label(frame, text="Measurement").grid(row=4, column=0, sticky="nw", pady=3)
        modes = ttk.Frame(frame)
        modes.grid(row=4, column=1, columnspan=2, sticky="ew")
        ttk.Radiobutton(modes, text="Time point", variable=self.mode,
                        value="time", command=self._update_mode).grid(row=0, column=0, sticky="w")
        self.time_entry = ttk.Entry(modes, textvariable=self.time_value, width=12)
        self.time_entry.grid(row=0, column=1, padx=(8, 20))
        ttk.Radiobutton(modes, text="Average window", variable=self.mode,
                        value="average", command=self._update_mode).grid(row=0, column=2, sticky="w")
        self.start_entry = ttk.Entry(modes, textvariable=self.start, width=12)
        self.start_entry.grid(row=0, column=3, padx=(8, 4))
        ttk.Label(modes, text="to").grid(row=0, column=4)
        self.stop_entry = ttk.Entry(modes, textvariable=self.stop, width=12)
        self.stop_entry.grid(row=0, column=5, padx=(4, 0))

        self._entry_row(frame, 5, "OCEAN executable", self.ocean)
        self.run_button = ttk.Button(frame, text="Extract and Rank", command=self.run)
        self.run_button.grid(row=6, column=1, sticky="w", pady=(10, 8))
        self.log = tk.Text(frame, height=12, wrap="word")
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(7, weight=1)
        self._update_mode()

    def _entry_row(self, frame, row, label, variable):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=variable).grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=3)

    def _path_row(self, frame, row, label, variable, command):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(frame, text="Browse...", command=command).grid(
            row=row, column=2, padx=(8, 0), pady=3)

    def _choose_psf(self):
        selected = filedialog.askdirectory(title="Select Spectre PSF directory")
        if selected:
            self.psf.set(selected)

    def _choose_targets(self):
        selected = filedialog.askopenfilename(
            title="Select leakage targets", filetypes=(("CSV file", "*.csv"), ("All files", "*")))
        if selected:
            self.targets.set(selected)

    def _choose_output(self):
        selected = filedialog.asksaveasfilename(
            title="Select current CSV output", initialfile=Path(self.output.get()).name,
            defaultextension=".csv", filetypes=(("CSV file", "*.csv"), ("All files", "*")))
        if selected:
            self.output.set(selected)

    def _choose_report_output(self):
        selected = filedialog.asksaveasfilename(
            title="Select ranking report output",
            initialfile=Path(self.report_output.get()).name,
            defaultextension=".txt",
            filetypes=(("Text report", "*.txt"), ("All files", "*")))
        if selected:
            self.report_output.set(selected)

    def _update_mode(self):
        time_mode = self.mode.get() == "time"
        self.time_entry.configure(state="normal" if time_mode else "disabled")
        state = "disabled" if time_mode else "normal"
        self.start_entry.configure(state=state)
        self.stop_entry.configure(state=state)

    def _append(self, value):
        self.log.insert("end", value.rstrip() + "\n")
        self.log.see("end")

    def _settings(self):
        return {
            "psf": self.psf.get(),
            "targets": self.targets.get(),
            "output": self.output.get(),
            "report_output": self.report_output.get(),
            "mode": self.mode.get(),
            "time_value": self.time_value.get(),
            "start": self.start.get(),
            "stop": self.stop.get(),
            "ocean": self.ocean.get(),
        }

    def _save_settings(self, report_error=True):
        try:
            save_settings("extractor", self._settings())
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
        time_mode = self.mode.get() == "time"
        time_value = self.time_value.get().strip() if time_mode else None
        start = None if time_mode else self.start.get().strip()
        stop = None if time_mode else self.stop.get().strip()
        if (not self.psf.get().strip() or not self.targets.get().strip() or
                not self.output.get().strip() or not self.report_output.get().strip()):
            messagebox.showerror(
                "Missing input", "PSF, targets CSV, current CSV, and report output are required.")
            return
        if (time_mode and not time_value) or (not time_mode and (not start or not stop)):
            messagebox.showerror("Missing measurement", "Enter a time point or both average limits.")
            return
        self._save_settings()
        self.run_button.configure(state="disabled")
        self._append("Step 1/2: Running OCEAN extraction...")
        arguments = (self.psf.get(), self.targets.get(), self.output.get(),
                     self.report_output.get(), time_value, start, stop,
                     self.ocean.get().strip() or "ocean")
        thread = threading.Thread(target=self._extract, args=arguments)
        thread.daemon = True
        thread.start()

    def _extract(self, psf, targets, output, report_output,
                 time_value, start, stop, ocean):
        try:
            report = extract_and_rank(
                psf, targets, output, report_output, time_value, start, stop,
                ocean, self._queue_output)
        except (OSError, ValueError, RuntimeError) as error:
            self.window.after(0, self._finish_error, str(error))
            return
        self.window.after(0, self._finish_success, output, report_output, report)

    def _queue_output(self, line):
        if line:
            self.window.after(0, self._append, line)

    def _finish_error(self, error):
        self.run_button.configure(state="normal")
        self._append("ERROR: " + error)
        messagebox.showerror("Extraction failed", error)

    def _finish_success(self, output, report_output, report):
        self.run_button.configure(state="normal")
        self._append("\n" + report)
        self._append("\nWrote " + output)
        self._append("Wrote " + report_output)
        messagebox.showinfo(
            "Extraction and ranking complete",
            "Generated leakage_current.csv and leakage_report.txt.")


def main():
    window = tk.Tk()
    LeakageExtractorGui(window)
    window.mainloop()


if __name__ == "__main__":
    main()
