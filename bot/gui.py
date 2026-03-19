import os
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk
from aws_actions import run_audit, download_reports

from styles import (
    PRIMARY,
    PRIMARY_HOVER,
    BACKGROUND,
    TEXT,
    BORDER,
    TITLE_FONT,
    LABEL_FONT,
    BUTTON_FONT,
    SMALL_FONT,
)


class AWSAuditToolGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("AWS Audit Tool")
        self.geometry("430x710")
        self.configure(bg=BACKGROUND)
        self.resizable(False, False)

        self.selected_folder = tk.StringVar(value="No folder selected")
        self.run_cloudmapper = tk.BooleanVar(value=True)
        self.select_all_var = tk.BooleanVar(value=False)

        self.region_vars = {}
        self.logo_tk = None

        self._build_ui()

    def _build_ui(self):
        # Top frame
        self.top_frame = tk.Frame(self, bg=BACKGROUND, height=120)
        self.top_frame.pack(fill="x", pady=(15, 5))
        self.top_frame.pack_propagate(False)

        self._build_logo()

        # Main card container
        self.card = tk.Frame(
            self,
            bg=BACKGROUND,
            bd=1,
            relief="solid",
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=24,
            pady=22,
        )
        self.card.pack(fill="both", expand=False, padx=22, pady=(8, 10))

        # Header
        header = tk.Label(
            self.card,
            text="AWS Audit Tool",
            bg=PRIMARY,
            fg="white",
            font=TITLE_FONT,
            width=24,
            height=2,
        )
        header.pack(pady=(0, 22))

        # Regions section
        tk.Label(
            self.card,
            text="Regions",
            bg=BACKGROUND,
            fg=TEXT,
            font=LABEL_FONT,
        ).pack(anchor="w")

        self._build_regions(self.card)

        # CloudMapper section
        tk.Label(
            self.card,
            text="CloudMapper",
            bg=BACKGROUND,
            fg=TEXT,
            font=LABEL_FONT,
        ).pack(anchor="w", pady=(18, 0))

        tk.Checkbutton(
            self.card,
            text="Generate CloudMapper ZIP",
            variable=self.run_cloudmapper,
            bg=BACKGROUND,
            fg=TEXT,
            selectcolor=BACKGROUND,
            activebackground=BACKGROUND,
            activeforeground=TEXT,
            font=("Arial", 10, "bold"),
            bd=0,
            highlightthickness=0,
        ).pack(anchor="w", pady=(6, 16))

        # Folder button
        btn_folder = tk.Button(
            self.card,
            text="Select Folder",
            font=BUTTON_FONT,
            bg=PRIMARY,
            fg="white",
            activebackground=PRIMARY_HOVER,
            activeforeground="white",
            width=26,
            height=2,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.select_folder,
        )
        btn_folder.pack(pady=(0, 10))

        folder_label = tk.Label(
            self.card,
            textvariable=self.selected_folder,
            bg=BACKGROUND,
            fg=TEXT,
            font=SMALL_FONT,
            wraplength=300,
            justify="center",
            height=2,
        )
        folder_label.pack(pady=(0, 18))

        # Run button
        btn_run = tk.Button(
            self.card,
            text="Run Audit",
            font=BUTTON_FONT,
            bg=PRIMARY,
            fg="white",
            activebackground=PRIMARY_HOVER,
            activeforeground="white",
            width=26,
            height=2,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.on_run_click,
        )
        btn_run.pack(pady=(0, 12))

        # Download button
        btn_download = tk.Button(
            self.card,
            text="Download Report",
            font=BUTTON_FONT,
            bg=PRIMARY,
            fg="white",
            activebackground=PRIMARY_HOVER,
            activeforeground="white",
            width=26,
            height=2,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.on_download_click,
        )
        btn_download.pack(pady=(0, 6))

        # Bottom version
        self.bottom_frame = tk.Frame(self, bg=BACKGROUND, height=40)
        self.bottom_frame.pack(fill="x", pady=(0, 8))
        self.bottom_frame.pack_propagate(False)

        label_version = tk.Label(
            self.bottom_frame,
            text="V1.0.0",
            bg=BACKGROUND,
            fg=TEXT,
            font=SMALL_FONT,
        )
        label_version.pack(expand=True)

    def _build_logo(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "files", "logo_aya.png")

        if os.path.exists(logo_path):
            logo_img = Image.open(logo_path)
            logo_img = logo_img.resize((165, 86), Image.Resampling.LANCZOS)
            self.logo_tk = ImageTk.PhotoImage(logo_img)

            logo_label = tk.Label(
                self.top_frame,
                image=self.logo_tk,
                bg=BACKGROUND,
            )
        else:
            logo_label = tk.Label(
                self.top_frame,
                text="Aya Healthcare",
                bg=BACKGROUND,
                fg=TEXT,
                font=("Arial", 18, "bold"),
            )

        logo_label.pack(expand=True)

    def _build_regions(self, parent):
        regions_frame = tk.Frame(parent, bg=BACKGROUND)
        regions_frame.pack(anchor="w", pady=(8, 4), fill="x")

        region_names = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]

        for region in region_names:
            self.region_vars[region] = tk.BooleanVar(value=False)

        options = {
            "bg": BACKGROUND,
            "fg": TEXT,
            "font": ("Arial", 10, "bold"),
            "selectcolor": BACKGROUND,
            "activebackground": BACKGROUND,
            "activeforeground": TEXT,
            "bd": 0,
            "highlightthickness": 0,
        }

        tk.Checkbutton(
            regions_frame,
            text="us-east-1",
            variable=self.region_vars["us-east-1"],
            command=self.update_select_all_state,
            **options,
        ).grid(row=0, column=0, sticky="w", padx=(0, 18), pady=5)

        tk.Checkbutton(
            regions_frame,
            text="us-east-2",
            variable=self.region_vars["us-east-2"],
            command=self.update_select_all_state,
            **options,
        ).grid(row=0, column=1, sticky="w", padx=(0, 18), pady=5)

        tk.Checkbutton(
            regions_frame,
            text="Select All",
            variable=self.select_all_var,
            command=self.toggle_all_regions,
            **options,
        ).grid(row=0, column=2, sticky="w", pady=5)

        tk.Checkbutton(
            regions_frame,
            text="us-west-1",
            variable=self.region_vars["us-west-1"],
            command=self.update_select_all_state,
            **options,
        ).grid(row=1, column=0, sticky="w", padx=(0, 18), pady=5)

        tk.Checkbutton(
            regions_frame,
            text="us-west-2",
            variable=self.region_vars["us-west-2"],
            command=self.update_select_all_state,
            **options,
        ).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=5)

    def toggle_all_regions(self):
        state = self.select_all_var.get()
        for var in self.region_vars.values():
            var.set(state)

    def update_select_all_state(self):
        all_selected = all(var.get() for var in self.region_vars.values())
        self.select_all_var.set(all_selected)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder.set(folder)

    def get_selected_regions(self):
        return [region for region, var in self.region_vars.items() if var.get()]

    def get_form_data(self):
        return {
            "regions": self.get_selected_regions(),
            "run_cloudmapper": self.run_cloudmapper.get(),
            "selected_folder": self.selected_folder.get(),
        }

    def on_run_click(self):
        data = self.get_form_data()

        if not data["regions"]:
            messagebox.showwarning("Regions", "Please select at least one region.")
            return

        success, message = run_audit(
            regions=data["regions"],
            run_cloudmapper=data["run_cloudmapper"],
        )

        if success:
            messagebox.showinfo("Run Audit", message)
        else:
            messagebox.showerror("Run Audit", message)

    def on_download_click(self):
        data = self.get_form_data()

        success, message = download_reports(
            selected_folder=data["selected_folder"]
        )

        if success:
            messagebox.showinfo("Download Report", message)
        else:
            messagebox.showerror("Download Report", message)


if __name__ == "__main__":
    app = AWSAuditToolGUI()
    app.mainloop()