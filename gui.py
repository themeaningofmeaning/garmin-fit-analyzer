import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import pandas as pd
import webbrowser  # 🆕 To open the dashboard
import plotly.graph_objects as go  # 🆕 Plotly
from plotly.subplots import make_subplots
# NOTE: Absolute import for the root folder structure
from analyzer import FitAnalyzer

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class InfoModal(ctk.CTkToplevel):
    """Pop-up window to explain the graph metrics."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("How to Read This Graph")
        self.geometry("600x650") 
        self.attributes("-topmost", True) 

        # Title
        title = ctk.CTkLabel(self, text="What do the dots mean?", font=("Arial", 22, "bold"), text_color="#2CC985")
        title.pack(pady=(20, 10))

        # Content
        text = """
1. 🟢 Green: High Quality (Fast & Stable)
   • High Efficiency + Low Decoupling.
   • You were fast and your heart rate was stable.
   • Verdict: Race Ready.

2. 🟡 Yellow: Maintenance Quality (Slow & Stable for RECOVERY / BASE)
   • Lower Efficiency + Low Decoupling.
   • You ran slower/easier, and your heart rate stayed calm.
   • Verdict: Good aerobic maintenance run.

3. 🔴 Red: "Expensive" Quality (Fast but Unstable)
   • High Efficiency + High Decoupling.
   • You ran fast, but your heart rate drifted up significantly (>5%).
   • Verdict: Good speed, but lacks endurance (or dehydrated).

4. ⚫ Black: The Bonk (Slow & Struggling)
   • Low Efficiency + High Decoupling.
   • You were slow AND your heart rate skyrocketed.
   • Verdict: Fatigue, illness, or bad day. Rest up.

--------------------------------------------------

👣 CADENCE (Steps Per Minute)
   • 170-180 spm (Green Band): The efficient goal zone.
   • < 160 spm: Braking forces are higher. Try to shorten stride.
"""
        textbox = ctk.CTkTextbox(self, font=("Consolas", 14), width=500, height=500)
        textbox.pack(padx=20, pady=10)
        textbox.insert("0.0", text)
        textbox.configure(state="disabled") 
        
        btn = ctk.CTkButton(self, text="Got it!", command=self.destroy, fg_color="#2CC985", text_color="black")
        btn.pack(pady=20)

class GarminAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Garmin FIT Analyzer v2.4 (Pro)")
        self.geometry("1100x900") # Made slightly taller for new buttons
        
        self.lift()
        self.focus_force()
        self.attributes('-topmost', True)
        self.after_idle(self.attributes, '-topmost', False)

        self.run_data = []
        self.df = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="Garmin\nAnalyzer 🏃‍♂️", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_load = ctk.CTkButton(self.sidebar, text="📂 Select Folder", command=self.select_folder)
        self.btn_load.grid(row=1, column=0, padx=20, pady=10)

        self.btn_csv = ctk.CTkButton(self.sidebar, text="💾 Export CSV", command=self.save_csv, state="disabled")
        self.btn_csv.grid(row=2, column=0, padx=20, pady=10)

        self.btn_dashboard = ctk.CTkButton(self.sidebar, text="🌍 Launch Dashboard", command=self.generate_dashboard, state="disabled", fg_color="#4d94ff") # 🆕 New Button
        self.btn_dashboard.grid(row=3, column=0, padx=20, pady=10)

        self.btn_copy = ctk.CTkButton(self.sidebar, text="📋 Copy for LLM", command=self.copy_to_clipboard, state="disabled", fg_color="#2CC985", text_color="black")
        self.btn_copy.grid(row=4, column=0, padx=20, pady=10)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Ready", text_color="gray")
        self.status_label.grid(row=7, column=0, padx=20, pady=20)
        
        # --- LOADING HUD ---
        self.progress_frame = ctk.CTkFrame(self, fg_color="#1F1F1F", border_width=2, border_color="#2CC985", corner_radius=15, width=350, height=80)
        self.progress_frame.grid_propagate(False) 
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="ANALYZING FIT FILES...", font=("Arial", 14, "bold"), text_color="white")
        self.progress_label.place(relx=0.5, rely=0.3, anchor="center")
        
        self.progress = ctk.CTkProgressBar(self.progress_frame, mode="determinate", width=250, height=12, progress_color="#2CC985")
        self.progress.set(0)
        self.progress.place(relx=0.5, rely=0.7, anchor="center")

        # 2. Main Area
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # Tab 1: Report
        self.tab_report = self.tabview.add("📄 Report")
        self.textbox = ctk.CTkTextbox(self.tab_report, font=("Consolas", 14))
        self.textbox.pack(fill="both", expand=True)

        # Welcome
        self.textbox.tag_config("center", justify="center")
        welcome_text = "\n\n\n👋 Welcome to Garmin Analyzer!\n\n1. Click '📂 Select Folder' on the left.\n2. Choose your folder of .FIT files.\n3. Watch the magic happen."
        self.textbox.insert("0.0", welcome_text, "center")

        # Tab 2: Graphs
        self.tab_graph = self.tabview.add("📈 Quick Preview")
        
        self.graph_controls = ctk.CTkFrame(self.tab_graph, fg_color="transparent", height=30)
        self.graph_controls.pack(fill="x", padx=5, pady=5)
        self.btn_info = ctk.CTkButton(self.graph_controls, text="❓ What do the dots mean?", command=self.open_guide, width=180, height=24, fg_color="#444", hover_color="#555")
        self.btn_info.pack(side="right")

        self.graph_frame = ctk.CTkFrame(self.tab_graph)
        self.graph_frame.pack(fill="both", expand=True)

    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.btn_load.configure(state="disabled")
            self.progress_frame.place(relx=0.6, rely=0.5, anchor="center")
            self.progress_frame.lift()
            self.progress.set(0)
            threading.Thread(target=self.run_analysis, args=(folder_selected,), daemon=True).start()

    def run_analysis(self, folder):
        analyzer = FitAnalyzer(output_callback=self.update_log, progress_callback=self.update_progress)
        results = analyzer.analyze_folder(folder)
        self.after(0, lambda: self.display_results(results))

    def update_progress(self, current, total):
        if total > 0:
            val = current / total
            self.progress.set(val)
            self.progress_label.configure(text=f"ANALYZING... ({current}/{total})")

    def update_log(self, text):
        print(text)

    def display_results(self, results):
        self.progress_frame.place_forget()

        self.run_data = results
        self.df = pd.DataFrame(results)
        
        avg_ef = 0
        if not self.df.empty:
            self.df['date_obj'] = pd.to_datetime(self.df['date'])
            self.df = self.df.sort_values('date_obj')
            avg_ef = self.df['efficiency_factor'].mean()

        report_text = ""
        for data in results:
            report_text += self.format_run_data(data, avg_ef)
            report_text += "\n" + "="*40 + "\n"

        self.textbox.delete("0.0", "end")
        self.textbox.insert("0.0", report_text)
        
        self.plot_trends() # Keep the Matplotlib preview

        self.status_label.configure(text=f"Analyzed {len(results)} files")
        self.btn_load.configure(state="normal")
        self.btn_csv.configure(state="normal")
        self.btn_copy.configure(state="normal")
        self.btn_dashboard.configure(state="normal") # Enable dashboard button

    def format_run_data(self, d, folder_avg_ef=0):
        def safe_fmt(val, unit=""):
            if val is None or str(val).lower() == "nan" or val == 0:
                return "-- (Requires Device w/ Sensor)"
            return f"{val}{unit}"

        decoupling = d.get('decoupling')
        d_status = ""
        if decoupling < 5: d_status = " (✅ Excellent)"
        elif decoupling <= 10: d_status = " (⚠️ Moderate Drift)"
        else: d_status = " (🛑 High Fatigue)"

        cadence = d.get('avg_cadence')
        c_status = ""
        if cadence and cadence > 170: c_status = " (✅ Efficient)"
        elif cadence and cadence >= 160: c_status = " (👌 Good)"
        elif cadence: c_status = " (⚠️ Overstriding)"

        ef = d.get('efficiency_factor')
        e_status = ""
        if folder_avg_ef > 0 and ef > folder_avg_ef: e_status = " (📈 Building Fitness)"
        elif folder_avg_ef > 0: e_status = " (📉 Below Average)"

        hrr_list = d.get('hrr_list', [])
        hrr_str = "--"
        if hrr_list:
            hrr_str = f"{hrr_list} bpm"
            if len(hrr_list) > 2 and hrr_list[-1] < hrr_list[0] * 0.7:
                hrr_str += " ⚠️ (Decaying recovery)"

        return f"""
RUN: {d.get('date')} ({d.get('filename')})
--------------------------------------------------
[1] PRIMARY STATS
    Distance:   {d.get('distance_mi')} mi
    Pace:       {d.get('pace')} /mi
    GAP:        {d.get('gap_pace')} /mi (Grade Adjusted)
    Elevation:  {d.get('elevation_ft')} ft gain

[2] EFFICIENCY & ENGINE
    Efficiency Factor (EF): {ef}{e_status} (Target: > 1.3)
    Aerobic Decoupling:     {decoupling}%{d_status}
    HR Recovery (60s):      {hrr_str}
    Avg Power:              {safe_fmt(d.get('avg_power'), " W")}

[3] INTERNAL LOAD (CONTEXT)
    Avg Heart Rate:   {d.get('avg_hr')} bpm
    Respiration Rate: {safe_fmt(d.get('avg_resp'), " brpm")}
    Avg Temperature:  {safe_fmt(d.get('avg_temp'), "°C")}

[4] FORM MECHANICS
    Cadence:         {cadence} spm{c_status}
    Vertical Ratio:  {safe_fmt(d.get('v_ratio'), "%")}
    GCT Balance:     {safe_fmt(d.get('gct_balance'), "% L/R")}
    GCT Drift:       {d.get('gct_change')} ms
"""

    def generate_dashboard(self):
        """Creates an Interactive Plotly Dashboard (V11: The Scoreboard Edition)."""
        if self.df is None or self.df.empty: return

        # --- 1. Smart Trend Detection ---
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

        # --- 2. Data Prep & Color Logic ---
        ef_mean = self.df['efficiency_factor'].mean()
        marker_colors = []
        verdicts = []
        
        for _, row in self.df.iterrows():
            d = row['decoupling']
            e = row['efficiency_factor']
            
            # Spectrum: Green -> Yellow -> Orange -> Red
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

        # Create dual-axis plot
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # --- 3. Layer 1: The Cost Landscape ---
        pos_d = self.df['decoupling'].copy()
        pos_d[pos_d < 0] = 0 
        neg_d = self.df['decoupling'].copy()
        neg_d[neg_d > 0] = 0 

        # Negative Decoupling (Teal)
        fig.add_trace(
            go.Scatter(
                x=self.df['date_obj'], y=neg_d,
                name="Stable Zone",
                fill='tozeroy',
                mode='lines', line=dict(width=0),
                fillcolor='rgba(0, 128, 128, 0.2)',
                hoverinfo='skip', showlegend=False
            ), secondary_y=True,
        )

        # Positive Decoupling (Red)
        fig.add_trace(
            go.Scatter(
                x=self.df['date_obj'], y=pos_d,
                name="Cost Zone",
                fill='tozeroy',
                mode='lines', line=dict(color='rgba(255, 77, 77, 0.5)', width=1),
                fillcolor='rgba(255, 77, 77, 0.1)',
                hoverinfo='skip', showlegend=False
            ), secondary_y=True,
        )
        
        # 5% Threshold Line
        fig.add_hline(y=5, line_dash="dot", line_color="rgba(255, 77, 77, 0.5)", secondary_y=True, annotation_text="5% Drift Limit", annotation_position="top right")

        # --- 4. Layer 2: The Gains Line ---
        fig.add_trace(
            go.Scatter(
                x=self.df['date_obj'], 
                y=self.df['efficiency_factor'], 
                name="Efficiency Factor",
                mode='lines+markers',
                line=dict(color='#2CC985', width=4, shape='spline'),
                marker=dict(
                    size=14, 
                    color=marker_colors, 
                    line=dict(width=2, color='white')
                ),
                customdata=list(zip(verdicts, self.df['decoupling'], self.df['pace'], self.df['distance_mi'], self.df['avg_hr'])),
                
                # HTML Tooltip
                hovertemplate="<b>%{customdata[0]}</b><br>" +
                              "EF: <b>%{y:.2f}</b> | Cost: <b>%{customdata[1]:.1f}%</b><br>" +
                              "<span style='color:#666'>──────────────────</span><br>" +
                              "Dist: %{customdata[3]} mi @ %{customdata[2]}<br>" +
                              "Avg HR: %{customdata[4]} bpm<extra></extra>"
            ),
            secondary_y=False,
        )

        # --- 5. Layout & Scoreboard Labels ---
        fig.update_layout(
            title_text=f"<b>Aerobic Durability Trend</b><br><span style='font-size: 16px; color: {trend_color};'>{trend_msg}</span>",
            template="plotly_dark",
            height=650,
            hovermode="closest",
            showlegend=False,
            margin=dict(l=60, r=60, t=100, b=60),
            
            hoverlabel=dict(
                bgcolor="#1F1F1F",
                bordercolor="#444444",
                font_size=14,
                font_family="Arial",
                font_color="white"
            )
        )

        # THE FINAL AXIS LABELS 🏆
        fig.update_yaxes(title_text="<b>Gains - Efficiency Factor (Green Line)</b>", secondary_y=False, color="#2CC985", showgrid=False)
        fig.update_yaxes(title_text="<b>Cost - Decoupling % (Red Area)</b>", secondary_y=True, color="#ff4d4d", showgrid=True, gridcolor='rgba(255,255,255,0.1)', range=[-5, max(20, self.df['decoupling'].max()+2)])

        # Config
        config = {
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': [
                'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 
                'autoScale2d', 'resetScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian'
            ]
        }

        # Save and Open
        file_path = os.path.abspath("dashboard.html")
        fig.write_html(file_path, config=config)
        webbrowser.open('file://' + file_path)
        messagebox.showinfo("Dashboard Launched", "Opened interactive dashboard in your browser! 🌍")


    def plot_trends(self):
        # Keeps the Matplotlib preview for the GUI window (Lightweight)
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        if self.df is None or self.df.empty:
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 8), sharex=True)
        fig.patch.set_facecolor('#2b2b2b')
        
        dates = self.df['date_obj']
        
        ax1.axhspan(-5, 5, color='#2CC985', alpha=0.15)
        ax1.text(dates.iloc[0], 0, " OPTIMAL STABILITY ZONE", color='#2CC985', fontsize=8, va='center')
        line1, = ax1.plot(dates, self.df['decoupling'], color='#ff4d4d', alpha=0.5)
        ax1b = ax1.twinx()
        line2, = ax1b.plot(dates, self.df['efficiency_factor'], color='#2CC985', alpha=0.3, linestyle='--')
        
        # Color dots
        ef_mean = self.df['efficiency_factor'].mean()
        dot_colors = []
        for _, row in self.df.iterrows():
            if row['efficiency_factor'] >= ef_mean and row['decoupling'] <= 5: dot_colors.append('#2CC985')
            elif row['efficiency_factor'] >= ef_mean and row['decoupling'] > 5: dot_colors.append('#ff4d4d')
            elif row['efficiency_factor'] < ef_mean and row['decoupling'] <= 5: dot_colors.append('#e6e600')
            else: dot_colors.append('black')

        ax1.scatter(dates, self.df['decoupling'], c=dot_colors, s=50, edgecolors='white', zorder=5)

        ax1.set_ylabel('Decoupling (%)', color='white')
        ax1b.set_ylabel('Efficiency', color='#2CC985')
        ax1b.tick_params(axis='y', colors='#2CC985')
        ax1.tick_params(colors='white')
        ax1.grid(True, alpha=0.3)
        
        ax2.plot(dates, self.df['avg_cadence'], marker='o', color='#ffa31a')
        ax2.set_ylabel('Cadence', color='white')
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(colors='white')
        plt.xticks(rotation=45)

        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def save_csv(self):
        if self.df is None: return
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if filename:
            cols = [
                'date', 'filename', 'distance_mi', 'pace', 'gap_pace', 
                'efficiency_factor', 'decoupling', 
                'avg_hr', 'avg_resp', 'avg_temp', 
                'avg_power', 'avg_cadence', 
                'hrr_list', 
                'v_ratio', 'gct_balance', 'gct_change', 
                'elevation_ft', 'moving_time_min', 'rest_time_min'
            ]
            valid_cols = [c for c in cols if c in self.df.columns]
            
            # 1. Write the data
            self.df[valid_cols].to_csv(filename, index=False)

            # 2. Append the "Decoder Ring" for the LLM
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
        text = self.textbox.get("0.0", "end")
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
        final_text = text + "\n" + llm_context
        self.clipboard_clear()
        self.clipboard_append(final_text)
        self.btn_copy.configure(text="✅ Copied w/ Context!", fg_color="white")
        self.after(2000, lambda: self.btn_copy.configure(text="📋 Copy for LLM", fg_color="#2CC985"))
        
    def open_guide(self):
        InfoModal(self)

def main():
    app = GarminAnalyzerApp()
    app.mainloop()

if __name__ == "__main__":
    main()