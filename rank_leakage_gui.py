#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tk GUI for hierarchical leakage-current ranking."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from rank_leakage import generate_report


class LeakageRankingGui:
    def __init__(self, window):
        self.window = window
        self.window.title("Spectre Leakage Current Ranking")
        self.window.minsize(840, 560)

        cwd = Path.cwd()
        self.current_csv = tk.StringVar(value=str(cwd / "leakage_current.csv"))
        self.output = tk.StringVar(value=str(cwd / "leakage_report.txt"))

        frame = ttk.Frame(window, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        self._path_row(frame, 0, "Current CSV", self.current_csv,
                       self._choose_current_csv)
        self._path_row(frame, 1, "Report output", self.output,
                       self._choose_output)
        ttk.Button(frame, text="Generate Ranking", command=self.run).grid(
            row=2, column=1, sticky="w", pady=(10, 8))

        report_frame = ttk.Frame(frame)
        report_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        report_frame.rowconfigure(0, weight=1)
        report_frame.columnconfigure(0, weight=1)
        self.report = tk.Text(report_frame, wrap="none", font="TkFixedFont")
        vertical = ttk.Scrollbar(report_frame, orient="vertical",
                                 command=self.report.yview)
        horizontal = ttk.Scrollbar(report_frame, orient="horizontal",
                                   command=self.report.xview)
        self.report.configure(yscrollcommand=vertical.set,
                              xscrollcommand=horizontal.set)
        self.report.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

    def _path_row(self, frame, row, label, variable, command):
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=3)
        ttk.Button(frame, text="Browse...", command=command).grid(
            row=row, column=2, padx=(8, 0), pady=3)

    def _choose_current_csv(self):
        selected = filedialog.askopenfilename(
            title="Select leakage current CSV",
            filetypes=(("CSV file", "*.csv"), ("All files", "*")))
        if selected:
            self.current_csv.set(selected)
            if self.output.get() == str(Path.cwd() / "leakage_report.txt"):
                self.output.set(str(Path(selected).with_name("leakage_report.txt")))

    def _choose_output(self):
        selected = filedialog.asksaveasfilename(
            title="Select ranking report output",
            initialfile=Path(self.output.get()).name,
            defaultextension=".txt",
            filetypes=(("Text report", "*.txt"), ("All files", "*")))
        if selected:
            self.output.set(selected)

    def run(self):
        current_csv = self.current_csv.get().strip()
        output = self.output.get().strip()
        if not current_csv:
            messagebox.showerror("Missing input", "Select leakage_current.csv first.")
            return
        self.report.delete("1.0", "end")
        try:
            report = generate_report(current_csv, output or None)
        except (OSError, ValueError) as error:
            self.report.insert("end", "ERROR: " + str(error) + "\n")
            messagebox.showerror("Ranking failed", str(error))
            return
        self.report.insert("end", report + "\n")
        self.report.see("1.0")
        if output:
            messagebox.showinfo("Ranking complete", "Wrote " + output)
        else:
            messagebox.showinfo("Ranking complete", "Ranking displayed in the window.")


def main():
    window = tk.Tk()
    LeakageRankingGui(window)
    window.mainloop()


if __name__ == "__main__":
    main()
