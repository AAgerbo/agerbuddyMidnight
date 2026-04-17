"""
Agerbuddy Midnight - Master Bot Controller GUI
This script serves as the central hub for the Agerbuddy automation suite. 
It provides a Tkinter-based user interface to manage, configure, and monitor 
individual bot modules (e.g., Fishingbuddy, CombatBot) while safely tracking 
the target game process in the background.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys
import threading
import psutil

# Dynamically add bot subdirectories to the system path so we can import them
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "bots", "Fishingbuddy"))
sys.path.append(os.path.join(base_dir, "bots", "CombatBot"))
import fishing_bot 
import combat_bot

class BotApp:
    """
    The main application class that constructs the Tkinter GUI, handles 
    process monitoring, and routes commands to the specific bot modules.
    """

    def __init__(self, root):
        """
        Initializes the graphical user interface, sets up styling, and kicks off 
        the background process monitoring loop.

        Args:
            root (tk.Tk): The root Tkinter window instance.
        """
        self.root = root
        self.root.title("Agerbuddy Midnight - Process Manager")
        self.root.geometry("650x450")
        
        # --- UI Theme Colors ---
        self.bg_color = "#333333"
        self.fg_color = "#ffffff"
        self.btn_color = "#555555"
        self.root.configure(bg=self.bg_color)

        # --- Core Application State ---
        self.target_process = "Wow.exe"
        self.game_is_running = False
        self.active_bot = None
        self.bot_thread = None

        # --- Layout Construction ---
        self.main_frame = tk.Frame(root, bg=self.bg_color)
        self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.left_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.right_frame = tk.Frame(self.main_frame, bg=self.bg_color, width=200)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # --- Notebook (Tabs) Styling ---
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.btn_color, foreground=self.fg_color)
        style.map("TNotebook.Tab", background=[("selected", "#777777")])

        self.notebook = ttk.Notebook(self.left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Live Log
        self.log_tab = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.log_tab, text="Log")
        
        self.log_text = scrolledtext.ScrolledText(self.log_tab, bg="#222222", fg=self.fg_color, font=("Consolas", 10), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Tab 2: Info (Placeholder for future development)
        self.info_tab = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.info_tab, text="Info")
        
        # --- Right Panel Controls ---
        self.bot_var = tk.StringVar()
        self.bot_dropdown = ttk.Combobox(self.right_frame, textvariable=self.bot_var, state="readonly")
        
        # Dynamically populate the dropdown with available bots
        available_bots = self.get_available_bots()
        self.bot_dropdown['values'] = available_bots
        if available_bots: self.bot_dropdown.current(0) 
        self.bot_dropdown.pack(fill=tk.X, pady=(0, 10))

        self.btn_load = tk.Button(self.right_frame, text="Load Profile", bg=self.btn_color, fg=self.fg_color, relief=tk.FLAT)
        self.btn_load.pack(fill=tk.X, pady=2)
        
        self.btn_settings = tk.Button(self.right_frame, text="Settings & Tools", bg=self.btn_color, fg=self.fg_color, relief=tk.FLAT, command=self.open_active_settings)
        self.btn_settings.pack(fill=tk.X, pady=2)

        self.enhanced_var = tk.BooleanVar()
        self.chk_enhanced = tk.Checkbutton(self.right_frame, text="Enhanced Mode", variable=self.enhanced_var, bg=self.bg_color, fg=self.fg_color, selectcolor=self.bg_color, activebackground=self.bg_color, activeforeground=self.fg_color)
        self.chk_enhanced.pack(anchor=tk.W, pady=5)

        self.logo_placeholder = tk.Label(self.right_frame, text="[ Logo Space ]", bg="#444444", fg="#aaaaaa", height=8)
        self.logo_placeholder.pack(fill=tk.X, pady=10)

        # The Master Start/Stop Button (Starts disabled until game is detected)
        self.btn_start = tk.Button(self.right_frame, text="Start", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), relief=tk.FLAT, command=self.toggle_bot, state=tk.DISABLED)
        self.btn_start.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 0))

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_var.set("Initializing Application...")
        self.status_bar = tk.Label(root, textvariable=self.status_var, bg="#444444", fg=self.fg_color, anchor=tk.W, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind the window's X button to our safe shutdown sequence
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- Initialization Complete ---
        self.write_log("Agerbuddy Midnight started.")
        self.write_log("Checking for available bots...")
        self.write_log(f"Found: {', '.join(available_bots)}")
        
        # Kick off the background process monitoring loop
        self.monitor_process()

    def get_available_bots(self):
        """
        Scans the 'bots' directory and returns a list of valid folder names.
        Filters out hidden system folders (like .ipynb_checkpoints) automatically.

        Returns:
            list: A list of string folder names, or ["No bots installed"] if empty.
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        bots_dir = os.path.join(base_dir, "bots")
        
        if not os.path.exists(bots_dir):
            os.makedirs(bots_dir)
            return ["No bots installed"]
            
        # Extract folder names, explicitly ignoring any folder that starts with a period (.)
        bot_folders = [
            folder for folder in os.listdir(bots_dir) 
            if os.path.isdir(os.path.join(bots_dir, folder)) and not folder.startswith('.')
        ]
        
        if bot_folders:
            return bot_folders
        else:
            return ["No bots installed"]

    def write_log(self, message):
        """
        Safely appends a message to the GUI's log text widget and scrolls to the bottom.

        Args:
            message (str): The string message to display.
        """
        self.log_text.config(state=tk.NORMAL) 
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END) 
        self.log_text.config(state=tk.DISABLED) 

    def monitor_process(self):
        """
        A recursive background loop that queries the OS every 2 seconds to check 
        if the target game (Wow.exe) is currently running. It dynamically enables 
        or disables the 'Start' button based on the game's state.
        """
        process_found = False
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == self.target_process.lower():
                process_found = True
                break

        # State Transition: The game just opened
        if process_found and not self.game_is_running:
            self.game_is_running = True
            self.write_log(f"SUCCESS: Attached to {self.target_process}.")
            self.status_var.set("Ready - Process Detected")
            self.btn_start.config(state=tk.NORMAL) 

        # State Transition: The game just closed/crashed
        elif not process_found and self.game_is_running:
            self.game_is_running = False
            self.write_log(f"WARNING: {self.target_process} connection lost.")
            self.status_var.set(f"Waiting for {self.target_process}...")
            self.btn_start.config(state=tk.DISABLED) 
            
            # If a bot was actively running when the game closed, shut it down safely
            if self.active_bot and self.active_bot.is_running:
                self.toggle_bot() 

        # Initial Startup State: Waiting for the game to launch
        elif not process_found and self.status_var.get() == "Initializing Application...":
            self.write_log(f"Waiting for user to launch {self.target_process}...")
            self.status_var.set(f"Waiting for {self.target_process}...")

        # Schedule this function to run again in 2000 milliseconds (2 seconds)
        self.root.after(2000, self.monitor_process)

    def open_active_settings(self):
        """
        Reads the currently selected bot from the dropdown, instantiates it if necessary,
        and requests the bot to draw its specific settings UI over the main window.
        """
        selected = self.bot_var.get()
        
        # Ensure we instantiate the bot the user is currently looking at
        if not self.active_bot or self.active_bot.name.replace(" ", "") != selected.replace(" ", ""):
            if selected == "Fishingbuddy":
                self.active_bot = fishing_bot.FishingBot(self.write_log)
            elif selected == "CombatBot":
                self.active_bot = combat_bot.CombatBot(self.write_log)
            else:
                self.write_log(f"No settings implemented for {selected}.")
                return
                
        # Ask the bot to generate its own modal UI
        if hasattr(self.active_bot, "open_settings"):
            self.active_bot.open_settings(self.root)
        else:
            self.write_log(f"{selected} does not have a configurable settings menu.")
    
    def toggle_bot(self):
        """
        Handles the logic for clicking the Start/Stop button. Instantiates the 
        selected bot class, updates the UI state, and spins up a separate daemon 
        thread so the GUI doesn't freeze while the bot loops.
        """
        current_text = self.btn_start.cget("text")
        selected = self.bot_var.get()
        
        if current_text == "Start":
            # Dynamic Bot Routing
            if selected == "Fishingbuddy":
                self.active_bot = fishing_bot.FishingBot(self.write_log)
            elif selected == "CombatBot":
                self.active_bot = combat_bot.CombatBot(self.write_log)
            else:
                self.write_log(f"[{selected}] logic has not been implemented yet.")
                return

            # Update UI to reflect active state
            self.btn_start.config(text="Stop", bg="#f44336")
            self.status_var.set(f"{selected} is running...")
            
            # Launch the bot in a separate background thread
            self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
            self.bot_thread.start()
        else:
            # Update UI to reflect idle state
            self.btn_start.config(text="Start", bg="#4CAF50")
            self.status_var.set("Ready - Process Detected")
            
            # Send the stop signal to the active bot
            if self.active_bot:
                self.active_bot.stop() 

    def run_bot_thread(self):
        """Wrapper method to execute the bot's blocking start method inside a thread."""
        self.active_bot.start()

    def on_closing(self):
        """
        Triggered when the user clicks the 'X' button on the window. 
        Ensures the active bot is safely halted before destroying the Tkinter root.
        """
        self.write_log("Initiating clean shutdown sequence...")
        if self.active_bot:
            self.active_bot.stop() 
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BotApp(root)
    root.mainloop()