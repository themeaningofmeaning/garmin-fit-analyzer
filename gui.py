import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import pandas as pd
import webbrowser
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import json
import hashlib
from datetime import datetime
import time

# NOTE: Absolute import for the root folder structure
from analyzer import FitAnalyzer

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- DATABASE MANAGER ---
class DatabaseManager:
    def __init__(self, db_path='runner_stats.db'):
        self.db_path = db_path
        self.create_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_tables(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS activities (
                    hash TEXT PRIMARY KEY,
                    filename TEXT,
                    date TEXT,
                    json_data TEXT,
                    session_id INTEGER
                )
            ''')

    def activity_exists(self, file_hash):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM activities WHERE hash = ?", (file_hash,))
            return cursor.fetchone() is not None

    def insert_activity(self, activity_data, file_hash, session_id):
        json_str = json.dumps(activity_data, default=str)
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO activities (hash, filename, date, json_data, session_id) VALUES (?, ?, ?, ?, ?)",
                (file_hash, activity_data.get('filename'), activity_data.get('date'), json_str, session_id)
            )
            
    def delete_activity(self, file_hash):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM activities WHERE hash = ?", (file_hash,))

    def get_count(self):
        with self.get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]

    def get_activities(self, timeframe="All Time", current_session_id=None):
        query = "SELECT json_data, hash FROM activities"
        params = []
        
        if timeframe == "Last Import" and current_session_id:
            query += " WHERE session_id = ?"
            params.append(current_session_id)
        elif timeframe == "Last 30 Days":
            date_Limit = (datetime.now() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            query += " WHERE date >= ?"
            params.append(date_Limit)
        elif timeframe == "Last 90 Days":
            date_Limit = (datetime.now() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
            query += " WHERE date >= ?"
            params.append(date_Limit)
        elif timeframe == "This Year":
            current_year = datetime.now().year
            query += " WHERE date >= ?"
            params.append(f"{current_year}-01-01")
            
        query += " ORDER BY date DESC"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for row in rows:
                d = json.loads(row[0])
                d['db_hash'] = row[1]
                results.append(d)
            return results

# --- HELPER: FILE HASHING ---
def calculate_file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

class GarminAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Garmin FIT Analyzer v4.0 (Pro)")
        self.geometry("1200x900")
        
        self.lift()
        self.focus_force()
        self.attributes('-topmost', True)
        self.after_idle(self.attributes, '-topmost', False)

        self.db = DatabaseManager()
        self.current_session_id = None
        self.df = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar (Redesigned Layout)
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1) 

        self.logo_label = ctk.CTkLabel(self.sidebar, text="Garmin\nAnalyzer 🏃‍♂️", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 15))

        # --- CLUSTER 1: DATA INGEST ---
        self.lbl_filter = ctk.CTkLabel(self.sidebar, text="TIMEFRAME", text_color="gray", font=("Arial", 10, "bold"))
        self.lbl_filter.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.filter_var = ctk.StringVar(value="Last 30 Days")
        self.combo_filter = ctk.CTkComboBox(
            self.sidebar, 
            values=["Last Import", "Last 30 Days", "Last 90 Days", "This Year", "All Time"],
            command=self.on_filter_change,
            variable=self.filter_var
        )
        self.combo_filter.grid(row=2, column=0, padx=20, pady=(5, 15))

        self.btn_load = ctk.CTkButton(self.sidebar, text="📂 Import Folder", command=self.select_folder)
        self.btn_load.grid(row=3, column=0, padx=20, pady=8)

        self.btn_csv = ctk.CTkButton(self.sidebar, text="💾 Export CSV", command=self.save_csv, state="disabled")
        self.btn_csv.grid(row=4, column=0, padx=20, pady=8)

        self.btn_copy = ctk.CTkButton(self.sidebar, text="📋 Copy for LLM", command=self.copy_to_clipboard, state="disabled", fg_color="#2CC985", text_color="black")
        self.btn_copy.grid(row=5, column=0, padx=20, pady=8)
        
        # Spacer Line
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333").grid(row=6, column=0, padx=20, pady=20, sticky="ew")

        # --- CLUSTER 2: THE DESTINATION ---
        self.btn_dashboard = ctk.CTkButton(
            self.sidebar, 
            text="🚀 Launch Trends 📈", 
            command=self.generate_dashboard, 
            state="disabled", 
            fg_color="#4d94ff", 
            height=40,
            font=("Arial", 13, "bold")
        )
        self.btn_dashboard.grid(row=7, column=0, padx=20, pady=10)

        # --- CLUSTER 3: STATS ---
        self.stats_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.stats_frame.grid(row=9, column=0, padx=20, pady=(40, 20), sticky="ew")
        
        self.lbl_db_count = ctk.CTkLabel(self.stats_frame, text=f"Runs Stored: {self.db.get_count()}", font=("Arial", 12, "bold"), text_color="#2CC985")
        self.lbl_db_count.pack(anchor="center")
        
        self.status_label = ctk.CTkLabel(self.stats_frame, text="Ready", text_color="gray", font=("Arial", 11))
        self.status_label.pack(anchor="center", pady=(5,0))

        # --- LOADING HUD ---
        self.progress_frame = ctk.CTkFrame(self, fg_color="#1F1F1F", border_width=2, border_color="#2CC985", corner_radius=15, width=350, height=80)
        self.progress_frame.grid_propagate(False) 
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="ANALYZING...", font=("Arial", 14, "bold"), text_color="white")
        self.progress_label.place(relx=0.5, rely=0.3, anchor="center")
        self.progress = ctk.CTkProgressBar(self.progress_frame, mode="determinate", width=250, height=12, progress_color="#2CC985")
        self.progress.set(0)
        self.progress.place(relx=0.5, rely=0.7, anchor="center")

        # 2. Main Area (Cleaned Up - No Quick Preview)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # Tab 1: Report (Default)
        self.tab_report = self.tabview.add("📄 Report")
        self.textbox = ctk.CTkTextbox(self.tab_report, font=("Consolas", 14))
        self.textbox.pack(fill="both", expand=True)
        self.textbox.tag_config("center", justify="center")
        
        # Tab 2: Activities
        self.tab_db = self.tabview.add("🏃 Activities")
        self.db_scroll = ctk.CTkScrollableFrame(self.tab_db)
        self.db_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Initial Load
        self.after(500, self.refresh_data_view)

    # --- LOGIC ---
    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.btn_load.configure(state="disabled")
            self.combo_filter.configure(state="disabled")
            self.progress_frame.place(relx=0.6, rely=0.5, anchor="center")
            self.progress_frame.lift()
            self.progress.set(0)
            threading.Thread(target=self.process_folder_thread, args=(folder_selected,), daemon=True).start()

    def process_folder_thread(self, folder):
        self.current_session_id = int(time.time())
        fit_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".fit")]
        total_files = len(fit_files)
        
        if total_files == 0:
            self.after(0, lambda: messagebox.showinfo("Info", "No .FIT files found!"))
            self.after(0, self.reset_ui_state)
            return

        analyzer = FitAnalyzer() 
        processed_count = 0
        new_count = 0
        
        for i, filepath in enumerate(fit_files):
            try:
                f_hash = calculate_file_hash(filepath)
                if not self.db.activity_exists(f_hash):
                    result = analyzer.analyze_file(filepath)
                    if result:
                        self.db.insert_activity(result, f_hash, self.current_session_id)
                        new_count += 1
                processed_count += 1
                self.after(0, self.update_progress, processed_count, total_files)
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

        self.after(0, lambda: self.finish_import(new_count, total_files))

    def update_progress(self, current, total):
        if total > 0:
            val = current / total
            self.progress.set(val)
            self.progress_label.configure(text=f"IMPORTING... ({current}/{total})")

    def reset_ui_state(self):
        self.progress_frame.place_forget()
        self.btn_load.configure(state="normal")
        self.combo_filter.configure(state="normal")

    def finish_import(self, new_count, total_files):
        self.reset_ui_state()
        self.lbl_db_count.configure(text=f"Runs Stored: {self.db.get_count()}")
        
        if new_count > 0:
            self.status_label.configure(text=f"Imported {new_count} new", text_color="#2CC985")
        else:
            self.status_label.configure(text="No new runs", text_color="orange")

        self.filter_var.set("Last Import")
        self.refresh_data_view()
        self.tabview.set("📄 Report")
        
        if new_count == 0:
            self.textbox.delete("0.0", "end")
            self.textbox.insert("0.0", "\n\n⚠️ No new runs were imported.\n(All files were duplicates).", "center")

    def on_filter_change(self, choice):
        self.refresh_data_view()

    def refresh_data_view(self):
        filter_mode = self.filter_var.get()
        activities = self.db.get_activities(filter_mode, self.current_session_id)
        
        self.build_activity_grid(activities)

        if not activities:
            self.textbox.delete("0.0", "end")
            msg = "\n\nNo runs found for this timeframe."
            if filter_mode == "Last Import":
                msg += "\n\nTry importing a new folder!"
            self.textbox.insert("0.0", msg, "center")
            self.df = None
            self.btn_dashboard.configure(state="disabled")
            return

        self.df = pd.DataFrame(activities)
        if not self.df.empty:
            self.df['date_obj'] = pd.to_datetime(self.df['date'])
            self.df = self.df.sort_values('date_obj')

        self.update_report_text(activities)
        
        self.btn_csv.configure(state="normal")
        self.btn_copy.configure(state="normal")
        self.btn_dashboard.configure(state="normal")

    def build_activity_grid(self, activities):
        for widget in self.db_scroll.winfo_children():
            widget.destroy()
            
        if not activities:
            ctk.CTkLabel(self.db_scroll, text="No activities found.").pack(pady=20)
            return

        # GRID HEADER
        columns = ["Date", "Filename", "Dist", "Elev", "EF", "Cost", "Cadence", ""]
        min_widths = [90, 200, 60, 60, 50, 50, 60, 40]

        h_frame = ctk.CTkFrame(self.db_scroll, fg_color="transparent")
        h_frame.pack(fill="x", pady=(0, 5))
        
        for i, col in enumerate(columns):
            lbl = ctk.CTkLabel(h_frame, text=col, font=("Arial", 12, "bold"), text_color="gray", anchor="w")
            if min_widths[i] > 0:
                lbl.configure(width=min_widths[i])
            lbl.pack(side="left", padx=5)

        # DATA ROWS
        for i, act in enumerate(activities):
            bg = "#2b2b2b" if i % 2 == 0 else "#232323"
            row = ctk.CTkFrame(self.db_scroll, fg_color=bg, height=35)
            row.pack(fill="x", pady=1)
            
            date_str = act.get('date', '')[:10]
            name_str = act.get('filename', '')[:30]
            dist_str = f"{act.get('distance_mi', 0):.1f} mi"
            elev_str = f"{act.get('elevation_ft', 0)} ft"
            ef_str = f"{act.get('efficiency_factor', 0):.2f}"
            cost = act.get('decoupling', 0)
            cost_color = "#2CC985" if cost <= 5 else "#ff4d4d"
            cost_str = f"{cost:.1f}%"
            cad_str = f"{act.get('avg_cadence', 0)} spm"

            vals = [date_str, name_str, dist_str, elev_str, ef_str, cost_str, cad_str]
            
            for j, val in enumerate(vals):
                lbl = ctk.CTkLabel(row, text=val, anchor="w", width=min_widths[j])
                if j == 5: 
                    lbl.configure(text_color=cost_color)
                lbl.pack(side="left", padx=5)
            
            # REFINED GHOST BUTTON (Premium)
            btn_del = ctk.CTkButton(
                row, text="×", width=25, height=25, 
                fg_color="transparent", 
                hover_color="#330000", # Subtle Dark Red Glow
                text_color="#666",     # Muted text normally
                font=("Arial", 18, "bold"),
                command=lambda h=act['db_hash']: self.delete_run(h)
            )
            # Add hover effect manually to toggle text color to red
            btn_del.bind("<Enter>", lambda e, b=btn_del: b.configure(text_color="#ff4d4d"))
            btn_del.bind("<Leave>", lambda e, b=btn_del: b.configure(text_color="#666"))
            
            btn_del.pack(side="right", padx=5)

    def delete_run(self, file_hash):
        if messagebox.askyesno("Confirm", "Delete this activity?"):
            self.db.delete_activity(file_hash)
            self.lbl_db_count.configure(text=f"Runs Stored: {self.db.get_count()}") 
            self.refresh_data_view() 

    def update_report_text(self, results):
        avg_ef = 0
        if self.df is not None and not self.df.empty:
            avg_ef = self.df['efficiency_factor'].mean()
        report_text = ""
        sorted_results = sorted(results, key=lambda x: x.get('date', ''), reverse=True)
        for data in sorted_results: 
            report_text += self.format_run_data(data, avg_ef)
            report_text += "\n" + "="*40 + "\n"
        self.textbox.delete("0.0", "end")
        self.textbox.insert("0.0", report_text)

    def format_run_data(self, d, folder_avg_ef=0):
        decoupling = d.get('decoupling', 0)
        d_status = ""
        if decoupling < 5: d_status = " (✅ Excellent)"
        elif decoupling <= 10: d_status = " (⚠️ Moderate)"
        else: d_status = " (🛑 High Fatigue)"
        ef = d.get('efficiency_factor', 0)
        hrr_list = d.get('hrr_list', [])
        hrr_str = str(hrr_list) if hrr_list else "--"
        return f"""
RUN: {d.get('date')} ({d.get('filename')})
--------------------------------------------------
Distance:   {d.get('distance_mi')} mi
Pace:       {d.get('pace')} /mi
EF:         {ef:.2f}
Decoupling: {decoupling}%{d_status}
HRR:        {hrr_str}
"""

    def generate_dashboard(self):
        """Creates an Interactive Plotly Dashboard (V4.0: Stacked Graphs + Embedded Legend)."""
        if self.df is None or self.df.empty: return

        # --- 1. Smart Trend Logic ---
        try:
            x_nums = (self.df['date_obj'] - self.df['date_obj'].min()).dt.total_seconds()
            y_ef = self.df['efficiency_factor']
            from scipy.stats import linregress
            slope, intercept, r_value, p_value, std_err = linregress(x_nums, y_ef)
            if slope > 0.0000001:
                trend_msg = f"📈 Trend: Engine Improving (+{slope*1e6:.2f} EF/day)"
                trend_color = "#2CC985"
            elif slope < -0.0000001:
                trend_msg = f"📉 Trend: Fitness Declining ({slope*1e6:.2f} EF/day)"
                trend_color = "#ff4d4d"
            else:
                trend_msg = "➡️ Trend: Fitness Stable"
                trend_color = "silver"
        except:
            trend_msg = "Trend: Insufficient Data"
            trend_color = "silver"

        # --- 2. Color Logic for Durability ---
        ef_mean = self.df['efficiency_factor'].mean()
        marker_colors = []
        verdicts = []
        for _, row in self.df.iterrows():
            d = row['decoupling']
            e = row['efficiency_factor']
            if e >= ef_mean and d <= 5: 
                marker_colors.append('#2CC985') # Green
                verdicts.append("Race Ready 🟢")
            elif e >= ef_mean and d > 5: 
                marker_colors.append('#ff9900') # Orange
                verdicts.append("Expensive Speed 🟠")
            elif e < ef_mean and d <= 5: 
                marker_colors.append('#e6e600') # Yellow
                verdicts.append("Base Maintenance 🟡")
            else: 
                marker_colors.append('#ff0000') # Red
                verdicts.append("Struggling 🔴")

        # --- 3. Color Logic for Cadence ---
        cad_colors = []
        for c in self.df['avg_cadence']:
            if c >= 170: cad_colors.append('#2CC985') # Efficient
            elif c >= 160: cad_colors.append('#e6e600') # OK
            else: cad_colors.append('#ff4d4d') # Sloppy

        # --- 4. CREATE SUBPLOTS ---
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True,
            vertical_spacing=0.15,
            subplot_titles=("Aerobic Durability (Engine vs. Cost)", "Mechanics (Cadence Trend)"),
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # === TOP GRAPH: DURABILITY ===
        # Cost Area (Red/Teal)
        pos_d = self.df['decoupling'].copy()
        pos_d[pos_d < 0] = 0 
        neg_d = self.df['decoupling'].copy()
        neg_d[neg_d > 0] = 0 

        fig.add_trace(go.Scatter(x=self.df['date_obj'], y=neg_d, name="Stable Zone", fill='tozeroy', mode='lines', line=dict(width=0), fillcolor='rgba(0, 128, 128, 0.2)', hoverinfo='skip', showlegend=False), row=1, col=1, secondary_y=True)
        fig.add_trace(go.Scatter(x=self.df['date_obj'], y=pos_d, name="Cost Zone", fill='tozeroy', mode='lines', line=dict(color='rgba(255, 77, 77, 0.5)', width=1), fillcolor='rgba(255, 77, 77, 0.1)', hoverinfo='skip', showlegend=False), row=1, col=1, secondary_y=True)
        fig.add_hline(y=5, line_dash="dot", line_color="rgba(255, 77, 77, 0.5)", secondary_y=True, row=1, col=1)

        # Engine Line
        fig.add_trace(
            go.Scatter(
                x=self.df['date_obj'], y=self.df['efficiency_factor'], 
                name="Efficiency Factor", mode='lines+markers',
                line=dict(color='#2CC985', width=3, shape='spline'),
                marker=dict(size=12, color=marker_colors, line=dict(width=2, color='white')),
                customdata=list(zip(verdicts, self.df['decoupling'], self.df['pace'], self.df['distance_mi'], self.df['avg_hr'])),
                hovertemplate="<b>%{customdata[0]}</b><br>EF: <b>%{y:.2f}</b> | Cost: <b>%{customdata[1]:.1f}%</b><br><span style='color:#666'>──────────</span><br>Dist: %{customdata[3]} mi @ %{customdata[2]}<br>Avg HR: %{customdata[4]} bpm<extra></extra>"
            ), row=1, col=1, secondary_y=False
        )

        # === BOTTOM GRAPH: CADENCE ===
        fig.add_trace(
            go.Scatter(
                x=self.df['date_obj'], y=self.df['avg_cadence'],
                name="Cadence", mode='lines+markers',
                line=dict(color='#888', width=1, dash='dot'),
                marker=dict(size=8, color=cad_colors, line=dict(width=1, color='white')),
                hovertemplate="Cadence: <b>%{y} spm</b><extra></extra>"
            ), row=2, col=1
        )

        # --- 5. LAYOUT & LEGEND ---
        fig.update_layout(
            title_text=f"<b>Training Trends</b><br><span style='font-size: 14px; color: {trend_color};'>{trend_msg}</span>",
            template="plotly_dark",
            height=900, 
            showlegend=False,
            margin=dict(l=60, r=60, t=100, b=150), 
            hoverlabel=dict(bgcolor="#1F1F1F", bordercolor="#444", font_color="white")
        )

        # Axis Styling
        fig.update_yaxes(title_text="[Gains] Efficiency", color="#2CC985", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="[Cost] Decoupling %", color="#ff4d4d", row=1, col=1, secondary_y=True, range=[-5, max(20, self.df['decoupling'].max()+2)])
        fig.update_yaxes(title_text="Cadence (spm)", color="white", row=2, col=1)

        # EMBEDDED LEGEND (HTML Annotation)
        legend_y = -0.12
        fig.add_annotation(xref="paper", yref="paper", x=0, y=legend_y, text="<b>What do the dots mean?</b>", showarrow=False, font=dict(size=14, color="white"), xanchor="left")
        
        legend_text = (
            "<span style='color:#2CC985'>● Green:</span> Race Ready (Fast & Stable) &nbsp;&nbsp;&nbsp;" +
            "<span style='color:#e6e600'>● Yellow:</span> Base Maintenance (Slow & Stable) &nbsp;&nbsp;&nbsp;" +
            "<span style='color:#ff9900'>● Orange:</span> Expensive Speed (Fast but Drifted) &nbsp;&nbsp;&nbsp;" +
            "<span style='color:#ff4d4d'>● Red:</span> Struggling (Slow & Drifted)"
        )
        fig.add_annotation(xref="paper", yref="paper", x=0, y=legend_y-0.03, text=legend_text, showarrow=False, font=dict(size=12, color="#ccc"), xanchor="left")

        # Save and Open
        config = {'displayModeBar': True, 'displaylogo': False, 'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']}
        file_path = os.path.abspath("trends.html")
        fig.write_html(file_path, config=config)
        webbrowser.open('file://' + file_path)

    def save_csv(self):
        if self.df is None: return
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if filename:
            cols = ['date', 'filename', 'distance_mi', 'pace', 'gap_pace', 'efficiency_factor', 'decoupling', 'avg_hr', 'avg_resp', 'avg_temp', 'avg_power', 'avg_cadence', 'hrr_list', 'v_ratio', 'gct_balance', 'gct_change', 'elevation_ft', 'moving_time_min', 'rest_time_min']
            valid_cols = [c for c in cols if c in self.df.columns]
            self.df[valid_cols].to_csv(filename, index=False)
            try:
                with open(filename, "a", encoding="utf-8") as f:
                    f.write("\n\n")
                    f.write("# --- DATA DICTIONARY FOR AI ANALYSIS ---\n")
                    f.write("# 1. hrr_list (Heart Rate Recovery): A Python list of HR drops (bpm) measured 60s after each peak effort.\n")
                    f.write("#    Interpretation: [35, 30, 28] is stable/strong. [35, 15, 8] indicates autonomic failure (stop workout).\n")
                    f.write("# 2. efficiency_factor (EF): Normalized Graded Speed (m/min) / HR. Higher is better. Used to track fitness trends.\n")
                    f.write("# 3. decoupling: The % loss of efficiency from first half to second half. >5% = Fatigue/Drift.\n")
                    f.write("# 4. v_ratio (Vertical Ratio): Vertical Oscillation / Stride Length. Lower is more efficient.\n")
            except Exception as e:
                print(f"Could not append context: {e}")
            messagebox.showinfo("Success", "CSV Exported (w/ AI Context Included)!")

    def copy_to_clipboard(self):
        is_summary_mode = len(self.df) > 20
        if is_summary_mode:
            self.df['month'] = self.df['date_obj'].dt.to_period('M')
            summary = self.df.groupby('month').agg({'efficiency_factor': 'mean', 'decoupling': 'mean', 'distance_mi': 'sum', 'avg_hr': 'mean', 'date': 'count'}).rename(columns={'date': 'run_count'})
            text_data = "MONTHLY SUMMARY (Long-Term Trend):\n" + summary.to_string()
        else:
            text_data = self.textbox.get("0.0", "end")
            
        llm_context = """
*** CONTEXT FOR AI COACH ***
The metrics above are engineered from Garmin .FIT files. Use this dictionary to interpret them:

1. EFFICIENCY FACTOR (EF): 
   - Formula: Normalized Graded Speed (m/min) / Heart Rate. 
   - Meaning: The "Miles Per Gallon" of the runner. 
   - Trend: Higher is better. A rising EF at the same HR means fitness is improving.

2. AEROBIC DECOUPLING (Pw:Hr):
   - Meaning: The percentage loss of efficiency from the first half of the run to the second.
   - Thresholds: < 5% is Aerobic Stability (Good). > 5% indicates cardiac drift/fatigue.

3. HR RECOVERY (60s):
   - Data: A list of heart rate drops (bpm) measured 60 seconds after detected peak efforts (intervals or hills).
   - Interpretation: [30, 28, 29] is excellent/stable. [30, 15, 8] indicates the autonomic nervous system is failing (terminate workout).

4. FORM METRICS:
   - Vertical Ratio: Vertical oscillation / Stride length. Lower is more efficient.
   - GCT Balance: Ground Contact Time L/R. 50.0% is perfect symmetry.
"""
        final_text = text_data + "\n" + llm_context
        self.clipboard_clear()
        self.clipboard_append(final_text)
        self.btn_copy.configure(text="✅ Copied w/ Context!", fg_color="white")
        self.after(2000, lambda: self.btn_copy.configure(text="📋 Copy for LLM", fg_color="#2CC985"))
        
def main():
    app = GarminAnalyzerApp()
    app.mainloop()

if __name__ == "__main__":
    main()