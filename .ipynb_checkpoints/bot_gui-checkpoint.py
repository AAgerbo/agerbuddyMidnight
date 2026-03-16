import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys
import threading
import psutil # <-- NEW: Moved to the GUI

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "bots", "Fishingbuddy"))
import fishing_bot 

class BotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Agerbuddy Midnight - Process Manager")
        self.root.geometry("650x450")
        
        self.bg_color = "#333333"
        self.fg_color = "#ffffff"
        self.btn_color = "#555555"
        self.root.configure(bg=self.bg_color)

        self.target_process = "Wow.exe"
        self.game_is_running = False

        self.main_frame = tk.Frame(root, bg=self.bg_color)
        self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.left_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.right_frame = tk.Frame(self.main_frame, bg=self.bg_color, width=200)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.btn_color, foreground=self.fg_color)
        style.map("TNotebook.Tab", background=[("selected", "#777777")])

        self.notebook = ttk.Notebook(self.left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.log_tab = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.log_tab, text="Log")
        
        self.log_text = scrolledtext.ScrolledText(self.log_tab, bg="#222222", fg=self.fg_color, font=("Consolas", 10), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.info_tab = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.info_tab, text="Info")
        
        self.bot_var = tk.StringVar()
        self.bot_dropdown = ttk.Combobox(self.right_frame, textvariable=self.bot_var, state="readonly")
        available_bots = self.get_available_bots()
        self.bot_dropdown['values'] = available_bots
        if available_bots: self.bot_dropdown.current(0) 
        self.bot_dropdown.pack(fill=tk.X, pady=(0, 10))

        self.btn_load = tk.Button(self.right_frame, text="Load Profile", bg=self.btn_color, fg=self.fg_color, relief=tk.FLAT)
        self.btn_load.pack(fill=tk.X, pady=2)
        
        self.btn_settings = tk.Button(self.right_frame, text="Settings & Tools", bg=self.btn_color, fg=self.fg_color, relief=tk.FLAT)
        self.btn_settings.pack(fill=tk.X, pady=2)

        self.enhanced_var = tk.BooleanVar()
        self.chk_enhanced = tk.Checkbutton(self.right_frame, text="Enhanced Mode", variable=self.enhanced_var, bg=self.bg_color, fg=self.fg_color, selectcolor=self.bg_color, activebackground=self.bg_color, activeforeground=self.fg_color)
        self.chk_enhanced.pack(anchor=tk.W, pady=5)

        self.logo_placeholder = tk.Label(self.right_frame, text="[ Logo Space ]", bg="#444444", fg="#aaaaaa", height=8)
        self.logo_placeholder.pack(fill=tk.X, pady=10)

        # Start Button is initially DISABLED
        self.btn_start = tk.Button(self.right_frame, text="Start", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), relief=tk.FLAT, command=self.toggle_bot, state=tk.DISABLED)
        self.btn_start.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 0))

        self.status_var = tk.StringVar()
        self.status_var.set("Initializing Application...")
        self.status_bar = tk.Label(root, textvariable=self.status_var, bg="#444444", fg=self.fg_color, anchor=tk.W, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.active_bot = fishing_bot.FishingBot(self.write_log)
        self.bot_thread = None

        self.write_log("Agerbuddy Midnight started.")
        self.write_log("Checking for available bots...")
        self.write_log(f"Found: {', '.join(available_bots)}")
        
        # <-- NEW: Kick off the monitoring loop
        self.monitor_process()

    def get_available_bots(self):
        """Scans the 'bots' directory and returns a list of folder names."""
        # 1. Get the exact folder path where bot_gui.py is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Safely join that path with "bots"
        bots_dir = os.path.join(base_dir, "bots")
        
        if not os.path.exists(bots_dir):
            os.makedirs(bots_dir)
            return ["No bots installed"]
            
        bot_folders = [folder for folder in os.listdir(bots_dir) if os.path.isdir(os.path.join(bots_dir, folder))]
        
        if bot_folders:
            return bot_folders
        else:
            return ["No bots installed"]

    def write_log(self, message):
        self.log_text.config(state=tk.NORMAL) 
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END) 
        self.log_text.config(state=tk.DISABLED) 

    def monitor_process(self):
        """Runs every 2 seconds to check if the target process is open."""
        process_found = False
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == self.target_process.lower():
                process_found = True
                break

        # If the game just opened
        if process_found and not self.game_is_running:
            self.game_is_running = True
            self.write_log(f"SUCCESS: Attached to {self.target_process}.")
            self.status_var.set("Ready - Process Detected")
            self.btn_start.config(state=tk.NORMAL) # Enable the Start button

        # If the game just closed
        elif not process_found and self.game_is_running:
            self.game_is_running = False
            self.write_log(f"WARNING: {self.target_process} connection lost.")
            self.status_var.set(f"Waiting for {self.target_process}...")
            self.btn_start.config(state=tk.DISABLED) # Disable the Start button
            
            # If the bot was running when the game closed, stop it safely
            if self.active_bot.is_running:
                self.toggle_bot() 

        # If starting up for the very first time and game isn't open
        elif not process_found and self.status_var.get() == "Initializing Application...":
            self.write_log(f"Waiting for user to launch {self.target_process}...")
            self.status_var.set(f"Waiting for {self.target_process}...")

        # Schedule this function to run again in 2000 milliseconds (2 seconds)
        self.root.after(2000, self.monitor_process)

    def toggle_bot(self):
        current_text = self.btn_start.cget("text")
        selected = self.bot_var.get()
        
        if current_text == "Start":
            if selected != "Fishingbuddy":
                self.write_log("Only Fishingbuddy is implemented right now.")
                return

            self.btn_start.config(text="Stop", bg="#f44336")
            self.status_var.set("Bot is running...")
            self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
            self.bot_thread.start()
        else:
            self.btn_start.config(text="Start", bg="#4CAF50")
            self.status_var.set("Ready - Process Detected")
            self.active_bot.stop() 

    def run_bot_thread(self):
        self.active_bot.start()

    def on_closing(self):
        self.write_log("Initiating clean shutdown sequence...")
        self.active_bot.stop() 
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BotApp(root)
    root.mainloop()