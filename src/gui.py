import os
import json
import threading
import subprocess
import pandas as pd
import customtkinter as ctk
from tkinter import filedialog, messagebox
from src.utils import load_config, open_file_or_folder, open_screenshots_folder
from src.scraper import run_price_guard_audit

# Scrap Mechanic Industrial Dark/Orange Palette
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class PriceGuardGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = load_config()
        self.app_version = self.config.get("app_version", "v1.0.0")

        self.title(f"PriceGuard {self.app_version} - Industrial Price & Stock Intelligence")
        self.geometry("680x790")
        self.resizable(False, False)
        self.configure(fg_color="#121212")

        # Set custom window icon if exists
        icon_path = os.path.abspath("assets/logo.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.stop_requested = False
        self.urls_list = self.config.get("test_urls", [])

        SAVED_URLS_FILE = "config/saved_urls.json"
        if os.path.exists(SAVED_URLS_FILE):
            try:
                with open(SAVED_URLS_FILE, "r", encoding="utf-8") as f:
                    self.urls_list = json.load(f)
            except Exception:
                pass

        # --- TARGET URL MANAGER FRAME ---
        self.url_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", border_color="#ff6600", border_width=1, corner_radius=6)
        self.url_frame.pack(padx=15, pady=(10, 4), fill="x")

        self.url_header_row = ctk.CTkFrame(self.url_frame, fg_color="transparent")
        self.url_header_row.pack(fill="x", padx=8, pady=(6, 2))

        self.url_title_lbl = ctk.CTkLabel(
            self.url_header_row, 
            text="⚙️ Target Product Endpoints (USD $):", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ff6600"
        )
        self.url_title_lbl.pack(side="left")

        # Import File & Info Buttons
        self.btn_top_box = ctk.CTkFrame(self.url_header_row, fg_color="transparent")
        self.btn_top_box.pack(side="right")

        self.import_btn = ctk.CTkButton(
            self.btn_top_box, text="📁 Import File (.xlsx/.txt)", width=130, height=22,
            fg_color="#27ae60", hover_color="#1e8449", text_color="#ffffff",
            font=ctk.CTkFont(size=10, weight="bold"), corner_radius=4, command=self.import_urls_from_file
        )
        self.import_btn.pack(side="left", padx=(0, 5))

        self.info_btn = ctk.CTkButton(
            self.btn_top_box, text="ℹ️ Info", width=50, height=22,
            fg_color="#ff6600", hover_color="#cc5200", text_color="#ffffff",
            corner_radius=4, command=self.show_url_info
        )
        self.info_btn.pack(side="left")

        # Input field + Add Button
        self.input_row = ctk.CTkFrame(self.url_frame, fg_color="transparent")
        self.input_row.pack(fill="x", padx=8, pady=(0, 4))

        self.url_entry = ctk.CTkEntry(
            self.input_row, width=490, 
            placeholder_text="Paste e-commerce URL or use [📁 Import File] button above",
            border_color="#ff6600", corner_radius=4
        )
        self.url_entry.pack(side="left", padx=(0, 8))
        self.url_entry.bind("<Return>", lambda event: self.add_url())

        self.add_btn = ctk.CTkButton(
            self.input_row, text="➕ Add URL", width=80, 
            fg_color="#ff6600", hover_color="#cc5200", text_color="#ffffff",
            corner_radius=4, command=self.add_url
        )
        self.add_btn.pack(side="left")

        # URLs Scrollable List
        self.urls_scroll = ctk.CTkScrollableFrame(self.url_frame, height=95, fg_color="#121212", corner_radius=4)
        self.urls_scroll.pack(padx=8, pady=(0, 6), fill="x")

        self.render_url_list()

        # --- SETTINGS ROW ---
        self.settings_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", border_color="#333333", border_width=1, corner_radius=6)
        self.settings_frame.pack(padx=15, pady=4, fill="x")

        self.headless_switch = ctk.CTkSwitch(
            self.settings_frame, text="Headless Mode (Silent Run)", 
            font=ctk.CTkFont(size=11, weight="bold"),
            progress_color="#ff6600"
        )
        self.headless_switch.pack(side="left", padx=12, pady=8)

        self.format_label = ctk.CTkLabel(self.settings_frame, text="Export Format:", font=ctk.CTkFont(size=11, weight="bold"))
        self.format_label.pack(side="left", padx=(10, 5), pady=8)

        self.format_option = ctk.CTkSegmentedButton(
            self.settings_frame, values=["Excel (.xlsx)", "CSV (.csv)", "JSON (.json)"],
            selected_color="#ff6600", selected_hover_color="#cc5200"
        )
        self.format_option.set("Excel (.xlsx)")
        self.format_option.pack(side="right", padx=12, pady=8)

        # --- CONTROLS FRAME ---
        self.control_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", border_color="#333333", border_width=1, corner_radius=6)
        self.control_frame.pack(padx=15, pady=4, fill="x")

        self.warning_label = ctk.CTkLabel(
            self.control_frame, 
            text="⚠️ Notice: Do not close the automated browser window during execution.", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            text_color="#ffaa00"
        )
        self.warning_label.pack(padx=8, pady=(4, 2))

        # Action Row
        self.action_row = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.action_row.pack(fill="x", padx=8, pady=4)

        self.start_btn = ctk.CTkButton(
            self.action_row, text="⚡ RUN PRICE & STOCK AUDIT", 
            font=ctk.CTkFont(size=13, weight="bold"), height=36, width=440,
            fg_color="#ff6600", hover_color="#cc5200", text_color="#ffffff",
            corner_radius=4, command=self.start_audit_thread
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            self.action_row, text="🛑 CANCEL", 
            font=ctk.CTkFont(size=13, weight="bold"), height=36, width=180,
            fg_color="#d32f2f", hover_color="#9a0007", text_color="#ffffff",
            corner_radius=4, state="disabled", command=self.request_stop
        )
        self.stop_btn.pack(side="left")

        # Progress bar row with Percent label
        self.progress_row = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.progress_row.pack(fill="x", padx=8, pady=(0, 6))

        self.progress_bar = ctk.CTkProgressBar(self.progress_row, progress_color="#ff6600", width=580)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", padx=(0, 8))

        self.percent_lbl = ctk.CTkLabel(self.progress_row, text="0%", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff6600", width=40)
        self.percent_lbl.pack(side="left")

        # --- LIVE DATA GRID RESULTS TABLE (Read-Only) ---
        self.grid_label = ctk.CTkLabel(self, text="📊 Live Extracted Results Grid:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff6600")
        self.grid_label.pack(padx=15, anchor="w")

        self.grid_textbox = ctk.CTkTextbox(self, width=650, height=105, fg_color="#121212", text_color="#27ae60", font=ctk.CTkFont(family="Consolas", size=10), corner_radius=4, state="disabled")
        self.grid_textbox.pack(padx=15, pady=(2, 4))
        self.init_grid_header()

        # --- LIVE TERMINAL LOGS (Read-Only) ---
        self.log_label = ctk.CTkLabel(self, text="Real-Time Execution Logs:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ffffff")
        self.log_label.pack(padx=15, anchor="w")

        self.log_textbox = ctk.CTkTextbox(self, width=650, height=90, fg_color="#121212", text_color="#ffaa00", font=ctk.CTkFont(family="Consolas", size=10), corner_radius=4, state="disabled")
        self.log_textbox.pack(padx=15, pady=(2, 6))

        # --- FOOTER BUTTONS (70% Green Report + 30% Orange Screenshots) ---
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(padx=15, pady=(4, 10), fill="x")

        self.open_output_btn = ctk.CTkButton(
            self.footer_frame, text="📂 Open Executive Dataset Report", height=36, width=440,
            fg_color="#2e7d32", hover_color="#1b5e20", text_color="#ffffff",
            font=ctk.CTkFont(size=11, weight="bold"), corner_radius=4, 
            command=lambda: open_file_or_folder("output.xlsx")
        )
        self.open_output_btn.pack(side="left", padx=(0, 8))

        self.open_shots_btn = ctk.CTkButton(
            self.footer_frame, text="📸 Screenshots", height=36, width=190,
            fg_color="#ff6600", hover_color="#cc5200", text_color="#ffffff",
            font=ctk.CTkFont(size=11, weight="bold"), corner_radius=4, 
            command=open_screenshots_folder
        )
        self.open_shots_btn.pack(side="left")

    def init_grid_header(self):
        self.grid_textbox.configure(state="normal")
        self.grid_textbox.delete("1.0", "end")
        header = f"{'#':<3} | {'PRODUCT TITLE':<38} | {'PRICE (USD)':<12} | {'STOCK STATUS'}\n"
        divider = "-" * 75 + "\n"
        self.grid_textbox.insert("end", header + divider)
        self.grid_textbox.configure(state="disabled")

    def update_live_grid(self, idx, title, price, status):
        self.grid_textbox.configure(state="normal")
        title_str = title[:36] + ".." if len(title) > 38 else f"{title:<38}"
        price_str = f"${price:,.2f}" if price > 0 else "$0.00"
        row_str = f"{idx:<3} | {title_str} | {price_str:<12} | {status}\n"
        self.grid_textbox.insert("end", row_str)
        self.grid_textbox.see("end")
        self.grid_textbox.configure(state="disabled")

    def update_progress(self, current, total):
        pct = current / total
        self.progress_bar.set(pct)
        self.percent_lbl.configure(text=f"{int(pct * 100)}%")

    def show_url_info(self):
        messagebox.showinfo(
            "Target URL Information", 
            "PriceGuard Target URL Info:\n\n"
            "• Currently optimized for e-commerce product endpoints (USD $).\n"
            "• Supports tracking of price changes and stock availability flags.\n"
            "• You can import 100s of URLs at once using [📁 Import File].\n"
            "• Select Export Format: Excel (.xlsx), CSV, or JSON."
        )

    def import_urls_from_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel & Text Files", "*.xlsx *.txt *.csv")])
        if not file_path:
            return

        new_urls = []
        try:
            if file_path.endswith(".xlsx") or file_path.endswith(".csv"):
                df = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
                for col in df.columns:
                    for val in df[col].dropna():
                        val_str = str(val).strip()
                        if val_str.startswith("http://") or val_str.startswith("https://"):
                            new_urls.append(val_str)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        val_str = line.strip()
                        if val_str.startswith("http://") or val_str.startswith("https://"):
                            new_urls.append(val_str)

            if not new_urls:
                messagebox.showwarning("Warning", "No valid URLs found in file!")
                return

            clear_existing = messagebox.askyesno(
                "Import Option", 
                "Do you want to CLEAR the current URL list before importing?"
            )

            if clear_existing:
                self.urls_list = []

            added_count = 0
            for u in new_urls:
                if u not in self.urls_list:
                    self.urls_list.append(u)
                    added_count += 1

            self.save_urls_state()
            self.render_url_list()
            messagebox.showinfo("Import Success", f"Successfully loaded {added_count} product URLs!")
            self.log(f"[IMPORT] Loaded {added_count} URLs from: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to parse file:\n{e}")

    def add_url(self):
        url = self.url_entry.get().strip()
        if url and url not in self.urls_list:
            self.urls_list.append(url)
            self.url_entry.delete(0, "end")
            self.save_urls_state()
            self.render_url_list()

    def remove_url(self, url):
        if url in self.urls_list:
            self.urls_list.remove(url)
            self.save_urls_state()
            self.render_url_list()

    def save_urls_state(self):
        try:
            os.makedirs("config", exist_ok=True)
            with open("config/saved_urls.json", "w", encoding="utf-8") as f:
                json.dump(self.urls_list, f, ensure_ascii=False)
        except Exception:
            pass

    def render_url_list(self):
        for child in self.urls_scroll.winfo_children():
            child.destroy()

        if not self.urls_list:
            empty_lbl = ctk.CTkLabel(self.urls_scroll, text="No target URLs added yet. Paste a URL or use [📁 Import File] above.", text_color="#7f8c8d")
            empty_lbl.pack(pady=10)
            return

        for idx, url in enumerate(self.urls_list):
            row_frame = ctk.CTkFrame(self.urls_scroll, fg_color="#121212", border_color="#333333", border_width=1, corner_radius=4)
            row_frame.pack(fill="x", padx=4, pady=3)

            display_text = url if len(url) <= 65 else url[:62] + "..."
            lbl = ctk.CTkLabel(row_frame, text=f"{idx+1}. {display_text}", font=ctk.CTkFont(size=11), text_color="#ffffff", anchor="w")
            lbl.pack(side="left", padx=8, pady=4, expand=True, fill="x")

            del_btn = ctk.CTkButton(
                row_frame, text="✕", width=22, height=22, 
                fg_color="transparent", hover_color="#d32f2f", text_color="#ff6600",
                command=lambda u=url: self.remove_url(u)
            )
            del_btn.pack(side="right", padx=6, pady=4)

    def log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def request_stop(self):
        if messagebox.askyesno("Confirm Cancellation", "Are you sure you want to cancel the price audit pipeline?"):
            self.stop_requested = True
            self.log("[USER] Audit cancellation requested. Stopping pipeline...")

    def start_audit_thread(self):
        self.stop_requested = False
        self.start_btn.configure(state="disabled", text="⏳ AUDIT IN PROGRESS...", fg_color="#5c5c5c")
        self.stop_btn.configure(state="normal")
        
        self.progress_bar.set(0)
        self.percent_lbl.configure(text="0%")

        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        self.init_grid_header()
        self.log(f"[START] Initiating PriceGuard {self.app_version} audit pipeline...")

        threading.Thread(target=self.run_automation_backend, daemon=True).start()

    def stop_loading_ui(self):
        self.progress_bar.set(1.0)
        self.percent_lbl.configure(text="100%")
        self.start_btn.configure(state="normal", text="⚡ RUN PRICE & STOCK AUDIT", fg_color="#ff6600")
        self.stop_btn.configure(state="disabled")

    def run_automation_backend(self):
        if not self.urls_list:
            self.log("[ERROR] No target URLs in list! Add at least one URL above.")
            self.stop_loading_ui()
            self.progress_bar.set(0)
            self.percent_lbl.configure(text="0%")
            messagebox.showwarning("Warning", "Please add at least one target product URL!")
            return

        is_headless = self.headless_switch.get() == 1
        chosen_format = self.format_option.get()

        try:
            res_file = run_price_guard_audit(
                self.urls_list, 
                log_callback=self.log, 
                stop_checker=lambda: self.stop_requested,
                headless=is_headless,
                export_format=chosen_format,
                item_callback=self.update_live_grid,
                progress_callback=self.update_progress
            )
            if not self.stop_requested:
                messagebox.showinfo("Success", f"PriceGuard Audit Complete!\nDataset saved to {res_file}")
        except Exception as e:
            self.log(f"[CRITICAL ERROR] {e}")
            messagebox.showerror("Error", f"Audit Failed:\n{e}")
        finally:
            self.stop_loading_ui()

if __name__ == "__main__":
    app = PriceGuardGUI()
    app.mainloop()