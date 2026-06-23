"""
main.py — Script Launcher UI
================================
The only file your team needs to run. Open it with:
    python main.py

It will let you pick an input file, choose which script to run,
and show you the results — no terminal knowledge needed.
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import sys
import os
import importlib.util
from pathlib import Path
from datetime import datetime

# ── Resolve paths relative to this file ──────────────────────────────────────
BASE_DIR     = Path(__file__).parent
SRC_DIR      = BASE_DIR / "src"
DATA_DIR     = BASE_DIR / "data"      # where users place their input files
EXAMPLES_DIR = BASE_DIR / "examples"  # read-only reference files

# ── Discover scripts in src/ automatically ───────────────────────────────────
def discover_scripts() -> dict[str, Path]:
    """Return {display_name: path} for every .py in src/."""
    scripts = {}
    if SRC_DIR.exists():
        for f in sorted(SRC_DIR.glob("*.py")):
            if not f.name.startswith("_"):
                label = f.stem.replace("_", " ").title()
                scripts[label] = f
    return scripts


# ── Dynamic script runner ─────────────────────────────────────────────────────
def run_script(script_path: Path, input_file: Path, log):
    """
    Import script_path as a module and call its run(input_file) function.
    Falls back to run_main(input_file) or main(input_file) if run() is absent.

    Each script in src/ should expose one of:
        def run(input_file: str): ...
        def run_main(input_file: str): ...
        def main(input_file: str): ...
    """
    spec   = importlib.util.spec_from_file_location(script_path.stem, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for fn_name in ("run", "run_main", "main"):
        fn = getattr(module, fn_name, None)
        if callable(fn):
            log(f"  Calling {script_path.name}::{fn_name}('{input_file}')")
            fn(str(input_file))
            return

    raise AttributeError(
        f"{script_path.name} has no run(), run_main(), or main() function.\n"
        f"Add one so the launcher knows what to call."
    )


# ── Colour + font tokens ──────────────────────────────────────────────────────
BG          = "#F7F8FA"
PANEL       = "#FFFFFF"
ACCENT      = "#4361EE"
ACCENT_DARK = "#2F4AC9"
SUCCESS     = "#2ECC71"
ERROR       = "#E74C3C"
TEXT        = "#1A1D2E"
MUTED       = "#6B7280"
BORDER      = "#E2E5EC"
MONO        = ("Consolas", "Courier New", "monospace")
SANS        = ("Segoe UI", "Helvetica Neue", "Arial")


# ── Main application window ───────────────────────────────────────────────────
class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FairVote Script Launcher")
        self.configure(bg=BG)
        self.minsize(680, 560)
        self.resizable(True, True)

        self.scripts      = discover_scripts()
        self.selected_var = tk.StringVar()
        self.file_var     = tk.StringVar(value="No file selected")
        self.input_file   = None
        self._running     = False

        self._build_ui()
        self._center_window()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header bar ────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=ACCENT, pady=18, padx=28)
        header.pack(fill="x")

        tk.Label(
            header, text="FairVote Script Launcher",
            bg=ACCENT, fg="white",
            font=(SANS[0], 18, "bold")
        ).pack(side="left")

        tk.Label(
            header, text="Run your data scripts without touching the terminal",
            bg=ACCENT, fg="#C5CEFF",
            font=(SANS[0], 10)
        ).pack(side="left", padx=(14, 0), pady=(4, 0))

        # ── Main content ──────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG, padx=28, pady=20)
        body.pack(fill="both", expand=True)

        # Step 1 — Choose script
        self._section(body, "1  Choose a script")

        script_frame = tk.Frame(body, bg=PANEL, relief="flat",
                                highlightthickness=1,
                                highlightbackground=BORDER)
        script_frame.pack(fill="x", pady=(0, 18))

        if not self.scripts:
            tk.Label(
                script_frame,
                text="⚠  No scripts found in src/.  Add .py files there to get started.",
                bg=PANEL, fg=ERROR, font=(SANS[0], 10), padx=14, pady=14
            ).pack(anchor="w")
        else:
            for i, name in enumerate(self.scripts):
                bg_row = PANEL if i % 2 == 0 else "#F9FAFB"
                row = tk.Frame(script_frame, bg=bg_row)
                row.pack(fill="x")

                rb = tk.Radiobutton(
                    row,
                    text=name,
                    variable=self.selected_var,
                    value=name,
                    bg=bg_row, activebackground=bg_row,
                    fg=TEXT, selectcolor=PANEL,
                    font=(SANS[0], 10),
                    padx=14, pady=10,
                    cursor="hand2"
                )
                rb.pack(side="left")

                path_label = tk.Label(
                    row,
                    text=str(self.scripts[name].relative_to(BASE_DIR)),
                    bg=bg_row, fg=MUTED,
                    font=(MONO[0], 8),
                    padx=8
                )
                path_label.pack(side="right", padx=12)

            # Auto-select first script
            self.selected_var.set(next(iter(self.scripts)))

        # Step 2 — Choose input file
        self._section(body, "2  Choose your input file")

        file_frame = tk.Frame(body, bg=PANEL, relief="flat",
                              highlightthickness=1,
                              highlightbackground=BORDER,
                              padx=14, pady=12)
        file_frame.pack(fill="x", pady=(0, 18))

        browse_btn = tk.Button(
            file_frame,
            text="Browse…",
            command=self._browse_file,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_DARK, activeforeground="white",
            font=(SANS[0], 10, "bold"),
            relief="flat", bd=0,
            padx=16, pady=7,
            cursor="hand2"
        )
        browse_btn.pack(side="left")

        self.file_label = tk.Label(
            file_frame,
            textvariable=self.file_var,
            bg=PANEL, fg=MUTED,
            font=(MONO[0], 9),
            anchor="w"
        )
        self.file_label.pack(side="left", padx=12, fill="x", expand=True)

        example_btn = tk.Button(
            file_frame,
            text="View example files",
            command=self._open_examples,
            bg=BG, fg=ACCENT,
            activebackground=BORDER,
            font=(SANS[0], 9),
            relief="flat", bd=0,
            padx=10, pady=7,
            cursor="hand2"
        )
        example_btn.pack(side="right")

        # Step 3 — Run
        self._section(body, "3  Run")

        run_row = tk.Frame(body, bg=BG)
        run_row.pack(fill="x", pady=(0, 14))

        self.run_btn = tk.Button(
            run_row,
            text="▶  Run Script",
            command=self._on_run,
            bg=SUCCESS, fg="white",
            activebackground="#27AE60", activeforeground="white",
            font=(SANS[0], 11, "bold"),
            relief="flat", bd=0,
            padx=22, pady=10,
            cursor="hand2"
        )
        self.run_btn.pack(side="left")

        self.status_label = tk.Label(
            run_row,
            text="",
            bg=BG, fg=MUTED,
            font=(SANS[0], 9),
            padx=16
        )
        self.status_label.pack(side="left")

        # Log / output area
        log_header = tk.Frame(body, bg=BG)
        log_header.pack(fill="x", pady=(4, 4))
        tk.Label(log_header, text="Output log", bg=BG, fg=MUTED,
                 font=(SANS[0], 9, "bold")).pack(side="left")

        self.clear_btn = tk.Button(
            log_header, text="Clear",
            command=self._clear_log,
            bg=BG, fg=MUTED,
            activebackground=BORDER,
            font=(SANS[0], 8),
            relief="flat", bd=0,
            cursor="hand2"
        )
        self.clear_btn.pack(side="right")

        self.log_box = scrolledtext.ScrolledText(
            body,
            height=10,
            bg="#1A1D2E", fg="#C5CEFF",
            insertbackground="white",
            font=(MONO[0], 9),
            relief="flat",
            bd=0,
            padx=12, pady=10,
            state="disabled",
            wrap="word"
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_config("success", foreground=SUCCESS)
        self.log_box.tag_config("error",   foreground=ERROR)
        self.log_box.tag_config("muted",   foreground="#6B7280")

        # Opening hint
        self._log("Ready. Select a script, choose your input file, then click Run.\n", "muted")

    def _section(self, parent, text):
        tk.Label(
            parent, text=text,
            bg=BG, fg=TEXT,
            font=(SANS[0], 10, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 6))

    # ── Actions ───────────────────────────────────────────────────────────────
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select your input file",
            initialdir=str(DATA_DIR) if DATA_DIR.exists() else str(BASE_DIR),
            filetypes=[
                ("Common data files", "*.csv *.xlsx *.xls *.json *.txt"),
                ("CSV files",         "*.csv"),
                ("Excel files",       "*.xlsx *.xls"),
                ("JSON files",        "*.json"),
                ("All files",         "*.*"),
            ]
        )
        if path:
            self.input_file = Path(path)
            self.file_var.set(str(self.input_file))
            self.file_label.config(fg=TEXT)

    def _open_folder(self, folder: Path):
        """Open a folder in the system file explorer, with an in-app fallback."""
        if not folder.exists():
            self._show_examples_window(folder, missing=True)
            return
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(folder)])
            else:
                import subprocess
                result = subprocess.run(
                    ["xdg-open", str(folder)],
                    capture_output=True
                )
                if result.returncode != 0:
                    raise OSError("xdg-open failed")
        except OSError:
            # No file manager available — show files in-app instead
            self._show_examples_window(folder)

    def _open_examples(self):
        self._open_folder(EXAMPLES_DIR)

    def _show_examples_window(self, folder: Path, missing: bool = False):
        """In-app fallback: show a small window listing the example files."""
        win = tk.Toplevel(self)
        win.title("Example Files")
        win.configure(bg=BG)
        win.minsize(480, 320)
        win.grab_set()

        tk.Label(
            win, text="Example Files",
            bg=BG, fg=TEXT,
            font=(SANS[0], 13, "bold"),
            padx=20, pady=14
        ).pack(anchor="w")

        if missing:
            tk.Label(
                win,
                text=f"⚠  Folder not found:\n{folder}",
                bg=BG, fg=ERROR,
                font=(SANS[0], 9),
                justify="left",
                padx=20
            ).pack(anchor="w")
        else:
            tk.Label(
                win,
                text=str(folder),
                bg=BG, fg=MUTED,
                font=(MONO[0], 8),
                padx=20
            ).pack(anchor="w")

            files = sorted(folder.iterdir()) if folder.exists() else []
            if not files:
                tk.Label(
                    win, text="No files found in examples/.",
                    bg=BG, fg=MUTED,
                    font=(SANS[0], 9), padx=20, pady=8
                ).pack(anchor="w")
            else:
                frame = tk.Frame(win, bg=PANEL,
                                 highlightthickness=1,
                                 highlightbackground=BORDER,
                                 padx=0, pady=0)
                frame.pack(fill="both", expand=True, padx=20, pady=(8, 16))

                for i, f in enumerate(files):
                    bg_row = PANEL if i % 2 == 0 else "#F9FAFB"
                    row = tk.Frame(frame, bg=bg_row)
                    row.pack(fill="x")
                    tk.Label(
                        row, text=f.name,
                        bg=bg_row, fg=TEXT,
                        font=(MONO[0], 9),
                        padx=14, pady=8, anchor="w"
                    ).pack(side="left")
                    tk.Label(
                        row,
                        text=f"{f.stat().st_size / 1024:.1f} KB" if f.is_file() else "folder",
                        bg=bg_row, fg=MUTED,
                        font=(MONO[0], 8),
                        padx=12
                    ).pack(side="right")

        tk.Button(
            win, text="Close",
            command=win.destroy,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_DARK,
            font=(SANS[0], 9, "bold"),
            relief="flat", bd=0,
            padx=16, pady=6,
            cursor="hand2"
        ).pack(pady=(0, 16))

    def _on_run(self):
        if self._running:
            return

        script_name = self.selected_var.get()
        if not script_name:
            self._set_status("Please select a script first.", ERROR)
            return
        if not self.input_file or not self.input_file.exists():
            self._set_status("Please select a valid input file first.", ERROR)
            return

        script_path = self.scripts[script_name]
        self._running = True
        self.run_btn.config(state="disabled", text="Running…", bg=MUTED)
        self._set_status("", "")

        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log(f"\n[{timestamp}] Running: {script_name}\n", "muted")
        self._log(f"  Input file: {self.input_file}\n")

        def worker():
            try:
                run_script(script_path, self.input_file, self._log)
                self.after(0, self._run_done, True, None)
            except Exception as exc:
                self.after(0, self._run_done, False, exc)

        threading.Thread(target=worker, daemon=True).start()

    def _run_done(self, success: bool, exc):
        self._running = False
        self.run_btn.config(state="normal", text="▶  Run Script", bg=SUCCESS)
        if success:
            self._log("\n✓ Script finished successfully.\n", "success")
            self._set_status("Finished successfully.", SUCCESS)
        else:
            self._log(f"\n✗ Error: {exc}\n", "error")
            self._set_status(f"Error: {exc}", ERROR)

    # ── Logging helpers ───────────────────────────────────────────────────────
    def _log(self, msg: str, tag: str = ""):
        self.log_box.config(state="normal")
        if tag:
            self.log_box.insert("end", msg, tag)
        else:
            self.log_box.insert("end", msg)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")
        self._log("Log cleared.\n", "muted")

    def _set_status(self, msg: str, color: str):
        self.status_label.config(text=msg, fg=color or MUTED)

    # ── Utils ─────────────────────────────────────────────────────────────────
    def _center_window(self):
        self.update_idletasks()
        w, h = 720, 620
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()