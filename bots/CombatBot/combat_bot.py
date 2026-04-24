"""
CombatBot - Reactive DPS Assistant
Features 12-slot vision tracking, dynamic color profiles, heuristic evasion, 
and a Multi-Condition Logic Interceptor (Profile Engine).
"""

import time
import cv2
import numpy as np
import mss
import pydirectinput
import ctypes
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import random
import sys

# Import our new GameState tracker
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(base_dir)
from utils.player_state import GameState

class CombatBot:
    def __init__(self, log_callback):
        self.is_running = False
        self.name = "CombatBot"
        self.log = log_callback 
        
        # Initialize GameState (will be threaded during start)
        self.state_tracker = GameState(self.log)
        
        self.KEY_MAP = {
            "Q": 0x51, "E": 0x45, "R": 0x52, "F": 0x46, "T": 0x54, 
            "C": 0x43, "V": 0x56, "Shift": 0x10, "Ctrl": 0x11, "Alt": 0x12
        }
        
        self.VALID_BINDS = [
            'Unbound', '1','2','3','4','5','6','7','8','9','0','-','=',
            'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12',
            'q','e','r','t','f','g','z','x','c','v','num0','num1','num2'
        ]
        
        self.default_slots = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=']
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)
        
        self.active_profile_data = None
        self.load_config()

    def hex_to_hsv_bounds(self, hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6: hex_color = "00FFFF"
        try:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            rgb_pixel = np.uint8([[[r, g, b]]])
            hsv_pixel = cv2.cvtColor(rgb_pixel, cv2.COLOR_RGB2HSV)[0][0]
            h = hsv_pixel[0]
            return np.array([max(0, h - 10), 100, 100]), np.array([min(179, h + 10), 255, 255])
        except ValueError:
            return np.array([85, 100, 100]), np.array([105, 255, 255])

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.activation_key_str = config.get("activation_key", "Q")
                self.slot_bindings = config.get("slot_bindings", self.default_slots)
                self.box_cfg = config.get("box_precision", {"w_scale": 250, "h_scale": 50, "x_shift": 500, "y_shift": 500})
                self.highlight_hex = config.get("highlight_hex", "#00FFFF")
                self.active_profile_name = config.get("active_profile", "None")
        else:
            self.activation_key_str = "Q" 
            self.slot_bindings = self.default_slots.copy()
            self.box_cfg = {"w_scale": 250, "h_scale": 50, "x_shift": 500, "y_shift": 500}
            self.highlight_hex = "#00FFFF"
            self.active_profile_name = "None"
            
        self.VK_ACTIVATION = self.KEY_MAP.get(self.activation_key_str, 0x51)
        self.lower_color, self.upper_color = self.hex_to_hsv_bounds(self.highlight_hex)
        self.load_profile(self.active_profile_name)

    def load_profile(self, profile_name):
        if profile_name == "None":
            self.active_profile_data = None
            return
            
        path = os.path.join(self.profiles_dir, f"{profile_name}.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.active_profile_data = json.load(f)
        else:
            self.active_profile_data = None
            self.active_profile_name = "None"

    def save_config(self, key_str=None, new_bindings=None, new_box_cfg=None, new_hex=None, profile_name=None):
        self.activation_key_str = key_str or self.activation_key_str
        self.slot_bindings = new_bindings or self.slot_bindings
        self.box_cfg = new_box_cfg or self.box_cfg
        self.highlight_hex = new_hex or self.highlight_hex
        self.active_profile_name = profile_name or self.active_profile_name

        if not self.highlight_hex.startswith('#'): self.highlight_hex = '#' + self.highlight_hex

        with open(self.config_path, 'w') as f:
            json.dump({
                "activation_key": self.activation_key_str,
                "slot_bindings": self.slot_bindings,
                "box_precision": self.box_cfg,
                "highlight_hex": self.highlight_hex,
                "active_profile": self.active_profile_name
            }, f, indent=4)
        
        self.VK_ACTIVATION = self.KEY_MAP.get(self.activation_key_str, 0x51)
        self.lower_color, self.upper_color = self.hex_to_hsv_bounds(self.highlight_hex)
        self.load_profile(self.active_profile_name)

    # --- THE LOGIC INTERCEPTOR ---
    def evaluate_profile_rules(self, active_slot_index):
        """Scans the loaded JSON profile and checks GameState variables."""
        if not self.active_profile_data or not self.active_profile_data.get("rules"):
            return None
            
        for rule in self.active_profile_data["rules"]:
            match = True
            for cond in rule.get("conditions", []):
                var_name = cond["variable"]
                op = cond["operator"]
                val = float(cond["value"])
                
                # Fetch live data
                live_val = None
                if var_name == "Slot": live_val = (active_slot_index + 1) if active_slot_index is not None else -1
                elif var_name == "Health %": live_val = self.state_tracker.health_pct
                elif var_name == "Power %": live_val = self.state_tracker.power_pct
                elif var_name == "Tertiary %": live_val = self.state_tracker.tertiary_pct
                
                # Evaluate
                if live_val is None: match = False; break
                if op == "==" and not (live_val == val): match = False; break
                elif op == "<" and not (live_val < val): match = False; break
                elif op == ">" and not (live_val > val): match = False; break
                
            if match:
                return rule["override_key"]
                
        return None

    def calculate_bounds(self, screen_w, screen_h, cfg):
        w_scale = max(1, cfg["w_scale"])
        h_scale = max(1, cfg["h_scale"])
        box_width = int(screen_w * (w_scale / 1000.0))
        box_height = int(screen_h * (h_scale / 1000.0))
        base_left = (screen_w - box_width) // 2
        base_top = screen_h - box_height
        x_shift_pixels = int(screen_w * ((cfg["x_shift"] - 500) / 1000.0))
        y_shift_pixels = int(screen_h * ((cfg["y_shift"] - 500) / 1000.0))
        left_offset = max(0, min(base_left + x_shift_pixels, screen_w - box_width))
        top_offset = max(0, min(base_top + y_shift_pixels, screen_h - box_height))
        return {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}

    def open_settings(self, parent_window):
        settings_win = tk.Toplevel(parent_window)
        settings_win.title(f"{self.name} - Configuration")
        settings_win.geometry("380x630") # Made taller to fit the Profile dropdown
        settings_win.configure(bg="#333333")
        settings_win.transient(parent_window) 
        
        tk.Label(settings_win, text="Combat Matrix Settings", bg="#333333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        top_frame = tk.Frame(settings_win, bg="#333333")
        top_frame.pack(pady=5, fill=tk.X, padx=20)
        
        tk.Label(top_frame, text="Activation Key:", bg="#333333", fg="#aaaaaa").grid(row=0, column=0, sticky="w", pady=5)
        key_var = tk.StringVar(value=self.activation_key_str)
        ttk.Combobox(top_frame, textvariable=key_var, values=list(self.KEY_MAP.keys()), state="readonly", width=8).grid(row=0, column=1, sticky="w", padx=10)
        
        tk.Label(top_frame, text="Highlight Hex:", bg="#333333", fg="#aaaaaa").grid(row=1, column=0, sticky="w", pady=5)
        color_var = tk.StringVar(value=self.highlight_hex)
        tk.Entry(top_frame, textvariable=color_var, width=11).grid(row=1, column=1, sticky="w", padx=10)
        tk.Button(top_frame, text="Reset Cyan", bg="#555555", fg="white", font=("Arial", 8), command=lambda: color_var.set("#00FFFF")).grid(row=1, column=2, sticky="w")
        
        # --- NEW: Profile Selector ---
        tk.Label(top_frame, text="Active Profile:", bg="#333333", fg="#4CAF50", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", pady=10)
        profile_var = tk.StringVar(value=self.active_profile_name)
        available_profiles = ["None"] + [f.replace('.json', '') for f in os.listdir(self.profiles_dir) if f.endswith('.json')]
        ttk.Combobox(top_frame, textvariable=profile_var, values=available_profiles, state="readonly", width=15).grid(row=2, column=1, sticky="w", padx=10)
        tk.Button(top_frame, text="Builder", bg="#2196F3", fg="white", font=("Arial", 8, "bold"), command=lambda: self.open_profile_builder(settings_win)).grid(row=2, column=2, sticky="w")

        tk.Label(settings_win, text="Action Bar Keybinds (Left to Right)", bg="#333333", fg="white", font=("Arial", 10, "underline")).pack(pady=(15, 5))
        
        grid_frame = tk.Frame(settings_win, bg="#333333")
        grid_frame.pack()
        
        self.slot_vars = []
        for i in range(12):
            row = i % 6
            col = (i // 6) * 2 
            tk.Label(grid_frame, text=f"Slot {i+1}:", bg="#333333", fg="white").grid(row=row, column=col, padx=5, pady=5, sticky="e")
            var = tk.StringVar(value=self.slot_bindings[i])
            cb = ttk.Combobox(grid_frame, textvariable=var, values=self.VALID_BINDS, width=8)
            cb.grid(row=row, column=col+1, padx=5, pady=5)
            self.slot_vars.append(var)
        
        def save_and_close():
            new_slots = [var.get() for var in self.slot_vars]
            self.save_config(key_var.get(), new_slots, new_hex=color_var.get(), profile_name=profile_var.get())
            self.log(f"[{self.name}] Configuration saved! Profile: {self.active_profile_name}")
            settings_win.destroy()
            
        button_frame = tk.Frame(settings_win, bg="#333333")
        button_frame.pack(pady=15, fill=tk.X, padx=20)
        tk.Button(button_frame, text="Save & Close", bg="#4CAF50", fg="white", command=save_and_close).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        tk.Button(button_frame, text="Calibrate Action Bar", bg="#555555", fg="white", command=self.run_vision_test).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        tk.Button(settings_win, text="Calibrate Player Frames", bg="#555555", fg="white", command=self.state_tracker.run_vision_test).pack(pady=5, fill=tk.X, padx=25)

    def open_profile_builder(self, parent_window):
        """A GUI to draft, edit, and reorder Multi-Condition JSON Profiles."""
        b_win = tk.Toplevel(parent_window)
        b_win.title("Profile Builder")
        b_win.geometry("500x650") # Made taller and wider for the new controls
        b_win.configure(bg="#222222")
        
        tk.Label(b_win, text="Logic Rule Builder", bg="#222222", fg="#2196F3", font=("Arial", 14, "bold")).pack(pady=10)
        
        current_draft_conditions = []
        rules_list = []

        # --- 1. Load Existing Profile ---
        load_frame = tk.Frame(b_win, bg="#222222")
        load_frame.pack(pady=5)
        tk.Label(load_frame, text="Load Existing:", bg="#222222", fg="#aaaaaa").pack(side=tk.LEFT)
        available_profiles = [f.replace('.json', '') for f in os.listdir(self.profiles_dir) if f.endswith('.json')]
        load_var = tk.StringVar(value="")
        load_cb = ttk.Combobox(load_frame, textvariable=load_var, values=available_profiles, state="readonly", width=15)
        load_cb.pack(side=tk.LEFT, padx=10)

        # --- 2. Profile Name ---
        name_frame = tk.Frame(b_win, bg="#222222")
        name_frame.pack(pady=5)
        tk.Label(name_frame, text="Profile Name:", bg="#222222", fg="white").pack(side=tk.LEFT)
        name_var = tk.StringVar()
        tk.Entry(name_frame, textvariable=name_var, width=20).pack(side=tk.LEFT, padx=10)

        # Helper to redraw the listbox when loading or reordering rules
        def refresh_listbox():
            listbox.delete(0, tk.END)
            for i, rule in enumerate(rules_list):
                cond_str = " AND ".join([f"{c['variable']} {c['operator']} {c['value']}" for c in rule['conditions']])
                listbox.insert(tk.END, f"{i+1}. IF [ {cond_str} ] -> PRESS [ {rule['override_key']} ]")

        def load_profile(event):
            sel = load_var.get()
            if not sel: return
            path = os.path.join(self.profiles_dir, f"{sel}.json")
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    name_var.set(data.get("profile_name", sel))
                    rules_list.clear()
                    rules_list.extend(data.get("rules", []))
                    refresh_listbox()
        
        load_cb.bind("<<ComboboxSelected>>", load_profile)

        # --- 3. Draft Builder ---
        draft_lbl = tk.Label(b_win, text="Current Rule Draft: IF [ ] THEN PRESS [ ]", bg="#333333", fg="yellow", wraplength=450)
        draft_lbl.pack(fill=tk.X, padx=20, pady=10, ipady=10)

        cond_frame = tk.Frame(b_win, bg="#222222")
        cond_frame.pack(pady=5)
        
        var_cb = ttk.Combobox(cond_frame, values=["Slot", "Health %", "Power %", "Tertiary %"], state="readonly", width=10)
        var_cb.set("Health %")
        var_cb.pack(side=tk.LEFT, padx=2)
        
        op_cb = ttk.Combobox(cond_frame, values=["==", "<", ">"], state="readonly", width=3)
        op_cb.set("<")
        op_cb.pack(side=tk.LEFT, padx=2)
        
        val_entry = tk.Entry(cond_frame, width=5)
        val_entry.pack(side=tk.LEFT, padx=2)

        def update_draft_label():
            cond_str = " AND ".join([f"{c['variable']} {c['operator']} {c['value']}" for c in current_draft_conditions])
            k = key_entry.get() or "?"
            draft_lbl.config(text=f"IF [ {cond_str} ] THEN PRESS [ {k} ]")
            
        def add_condition():
            # Basic validation to ensure value is a number
            if not val_entry.get().replace('.','',1).isdigit(): return
            current_draft_conditions.append({
                "variable": var_cb.get(), "operator": op_cb.get(), "value": val_entry.get()
            })
            update_draft_label()

        def reset_draft():
            current_draft_conditions.clear()
            key_entry.delete(0, tk.END)
            update_draft_label()
            
        tk.Button(cond_frame, text="+ AND", bg="#555", fg="white", command=add_condition).pack(side=tk.LEFT, padx=5)
        tk.Button(cond_frame, text="Reset", bg="#f44336", fg="white", command=reset_draft).pack(side=tk.LEFT, padx=5)

        out_frame = tk.Frame(b_win, bg="#222222")
        out_frame.pack(pady=10)
        tk.Label(out_frame, text="THEN PRESS KEY:", bg="#222222", fg="white").pack(side=tk.LEFT)
        key_entry = tk.Entry(out_frame, width=5)
        key_entry.pack(side=tk.LEFT, padx=10)
        key_entry.bind("<KeyRelease>", lambda e: update_draft_label())

        def save_rule():
            if not current_draft_conditions or not key_entry.get(): return
            rules_list.append({"conditions": list(current_draft_conditions), "override_key": key_entry.get()})
            refresh_listbox()
            reset_draft() # Auto-reset the draft UI after saving

        tk.Button(b_win, text="Save Rule to Profile", bg="#2196F3", fg="white", command=save_rule).pack(pady=5)

        # --- 4. Saved Rules List & Reordering Controls ---
        list_frame = tk.Frame(b_win, bg="#222222")
        list_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)
        
        listbox = tk.Listbox(list_frame, bg="#111", fg="white", height=8)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ctrl_frame = tk.Frame(list_frame, bg="#222222")
        ctrl_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        def move_rule_up():
            idx = listbox.curselection()
            if not idx: return
            idx = idx[0]
            if idx == 0: return # Already at top
            rules_list[idx], rules_list[idx-1] = rules_list[idx-1], rules_list[idx]
            refresh_listbox()
            listbox.select_set(idx-1)

        def move_rule_down():
            idx = listbox.curselection()
            if not idx: return
            idx = idx[0]
            if idx == len(rules_list) - 1: return # Already at bottom
            rules_list[idx], rules_list[idx+1] = rules_list[idx+1], rules_list[idx]
            refresh_listbox()
            listbox.select_set(idx+1)

        def delete_rule():
            idx = listbox.curselection()
            if not idx: return
            del rules_list[idx[0]]
            refresh_listbox()

        tk.Button(ctrl_frame, text="▲", bg="#555", fg="white", command=move_rule_up).pack(fill=tk.X, pady=2)
        tk.Button(ctrl_frame, text="▼", bg="#555", fg="white", command=move_rule_down).pack(fill=tk.X, pady=2)
        tk.Button(ctrl_frame, text="Del", bg="#f44336", fg="white", command=delete_rule).pack(fill=tk.X, pady=10)

        def save_profile():
            if not name_var.get() or not rules_list: return
            with open(os.path.join(self.profiles_dir, f"{name_var.get()}.json"), 'w') as f:
                json.dump({"profile_name": name_var.get(), "rules": rules_list}, f, indent=4)
            messagebox.showinfo("Success", "Profile Saved! You can now select it in settings.")
            
            # Auto-update the parent window's combobox list if we created a new profile
            if hasattr(self, 'active_profile_name'):
                b_win.destroy()

        tk.Button(b_win, text="EXPORT PROFILE", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=save_profile).pack(pady=10)

    def start(self):
        self.log(f"[{self.name}] Matrix Online. Holding '{self.activation_key_str}'. Profile: {self.active_profile_name}")
        self.is_running = True
        
        # Spin up the GameState tracker in an isolated daemon thread
        self.state_thread = threading.Thread(target=self.state_tracker.start, daemon=True)
        self.state_thread.start()
        
        self.combat_loop()
        return True

    def stop(self):
        self.is_running = False
        self.state_tracker.stop() # Safe shutdown for GameState
        self.log(f"[{self.name}] Standing down...")

    def is_game_active(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "wow" in buf.value.lower() or "world of warcraft" in buf.value.lower()

    def is_activation_key_held(self):
        return ctypes.windll.user32.GetAsyncKeyState(self.VK_ACTIVATION) & 0x8000

    def combat_loop(self):
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            monitor = self.calculate_bounds(screen_w, screen_h, self.box_cfg)
            slot_width = monitor["width"] // len(self.slot_bindings)
            is_engaged = False

            while self.is_running:
                if not self.is_game_active() or not self.is_activation_key_held():
                    if is_engaged:
                        self.log(f"[{self.name}] Ceasefire. Matrix Online.")
                        is_engaged = False
                    time.sleep(0.05)
                    continue

                if not is_engaged:
                    self.log(f"[{self.name}] Target engaged! Firing sequence initiated...")
                    is_engaged = True

                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Default assume nothing is glowing
                active_slot_index = None
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 50:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        center_x = x + (w // 2)
                        active_slot_index = center_x // slot_width

                # --- INTERCEPTOR LOGIC ---
                override_key = self.evaluate_profile_rules(active_slot_index)
                target_key = None
                
                # Priority 1: Profile Override
                if override_key:
                    target_key = override_key
                    self.log(f"[{self.name}] Profile Override! -> Pressing '{target_key}'")
                
                # Priority 2: Standard Slot Highlight
                elif active_slot_index is not None and 0 <= active_slot_index < len(self.slot_bindings):
                    target_key = self.slot_bindings[active_slot_index]
                    if target_key != 'Unbound':
                        self.log(f"[{self.name}] Strike! Slot {active_slot_index + 1} -> Pressing '{target_key}'")

                # --- EXECUTION LOGIC ---
                if target_key and target_key != 'Unbound':
                    if not is_engaged:
                        time.sleep(random.uniform(0.15, 0.25)) # Human reaction delay
                    
                    key_hold_time = random.uniform(0.03, 0.08)
                    pydirectinput.keyDown(target_key)
                    time.sleep(key_hold_time)
                    pydirectinput.keyUp(target_key)
                    
                    time.sleep(random.uniform(0.15, 0.35)) # GCD spam variance
                else:
                    # If nothing triggered (no slot highlighted, no rules matched), idle briefly
                    time.sleep(random.uniform(0.04, 0.08))

    def run_vision_test(self):
        self.log(f"[{self.name}] Launching Vision Calibration...")
        cv2.namedWindow("Action Bar Calibration")
        cv2.createTrackbar("Width (0-1000)", "Action Bar Calibration", self.box_cfg["w_scale"], 1000, lambda x: None)
        cv2.createTrackbar("Height (0-1000)", "Action Bar Calibration", self.box_cfg["h_scale"], 1000, lambda x: None)
        cv2.createTrackbar("X Shift (500=Mid)", "Action Bar Calibration", self.box_cfg["x_shift"], 1000, lambda x: None)
        cv2.createTrackbar("Y Shift (500=Mid)", "Action Bar Calibration", self.box_cfg["y_shift"], 1000, lambda x: None)

        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            while True:
                live_cfg = {
                    "w_scale": cv2.getTrackbarPos("Width (0-1000)", "Action Bar Calibration"),
                    "h_scale": cv2.getTrackbarPos("Height (0-1000)", "Action Bar Calibration"),
                    "x_shift": cv2.getTrackbarPos("X Shift (500=Mid)", "Action Bar Calibration"),
                    "y_shift": cv2.getTrackbarPos("Y Shift (500=Mid)", "Action Bar Calibration")
                }
                
                monitor = self.calculate_bounds(screen_w, screen_h, live_cfg)
                slot_width = monitor["width"] // len(self.slot_bindings)
                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                for i in range(1, len(self.slot_bindings)):
                    cv2.line(img_bgr, (i * slot_width, 0), (i * slot_width, monitor["height"]), (0, 255, 0), 1)

                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 50:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        cv2.putText(img_bgr, f"Target: Slot {(x + (w // 2)) // slot_width + 1}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.putText(img_bgr, "Press 'S' to Save", (10, monitor["height"] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imshow("Action Bar Calibration", img_bgr)
                cv2.imshow("Custom Color Mask", mask)
                
                key = cv2.waitKey(25) & 0xFF
                if key == ord('x'): break
                elif key == ord('s'):
                    self.save_config(new_box_cfg=live_cfg)
                    self.log(f"[{self.name}] SUCCESS: Dimensions saved!")
                    break

        cv2.destroyAllWindows()