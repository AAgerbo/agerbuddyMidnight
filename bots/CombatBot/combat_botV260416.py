import time
import cv2
import numpy as np
import mss
import pydirectinput
import ctypes
import os
import json
import tkinter as tk
from tkinter import ttk
import random

class CombatBot:
    """
    A reactive DPS assistant for World of Warcraft.
    Features customizable slots, precision UI calibration, and custom dynamic color tracking.
    """

    def __init__(self, log_callback):
        self.is_running = False
        self.name = "CombatBot"
        self.log = log_callback 
        
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
        self.load_config()

    def hex_to_hsv_bounds(self, hex_color):
        """Converts a standard Hex color into OpenCV HSV boundaries for glowing UI elements."""
        hex_color = hex_color.lstrip('#')
        
        # Fallback to Cyan if the user types something invalid
        if len(hex_color) != 6:
            hex_color = "00FFFF"
            
        try:
            # Convert Hex to RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Create a 1-pixel image and use OpenCV to convert it to HSV
            rgb_pixel = np.uint8([[[r, g, b]]])
            hsv_pixel = cv2.cvtColor(rgb_pixel, cv2.COLOR_RGB2HSV)[0][0]
            
            h = hsv_pixel[0]
            
            # Create a wide net for Saturation and Value to capture the "glow"
            # Hue is tightly clamped (+/- 10) to only grab the specific color
            lower_bound = np.array([max(0, h - 10), 100, 100])
            upper_bound = np.array([min(179, h + 10), 255, 255])
            
            return lower_bound, upper_bound
        except ValueError:
            # Absolute safety fallback for bad inputs
            return np.array([85, 100, 100]), np.array([105, 255, 255])

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.activation_key_str = config.get("activation_key", "Q")
                self.slot_bindings = config.get("slot_bindings", self.default_slots)
                self.box_cfg = config.get("box_precision", {"w_scale": 250, "h_scale": 50, "x_shift": 500, "y_shift": 500})
                
                # NEW: Load custom hex color (Defaults to Cyan)
                self.highlight_hex = config.get("highlight_hex", "#00FFFF")
        else:
            self.activation_key_str = "Q" 
            self.slot_bindings = self.default_slots.copy()
            self.box_cfg = {"w_scale": 250, "h_scale": 50, "x_shift": 500, "y_shift": 500}
            self.highlight_hex = "#00FFFF"
            
        self.VK_ACTIVATION = self.KEY_MAP.get(self.activation_key_str, 0x51)
        self.lower_color, self.upper_color = self.hex_to_hsv_bounds(self.highlight_hex)

    def save_config(self, key_str=None, new_bindings=None, new_box_cfg=None, new_hex=None):
        key_str = key_str or self.activation_key_str
        new_bindings = new_bindings or self.slot_bindings
        new_box_cfg = new_box_cfg or self.box_cfg
        new_hex = new_hex or self.highlight_hex

        # Ensure hex always has the hashtag for clean UI presentation
        if not new_hex.startswith('#'):
            new_hex = '#' + new_hex

        with open(self.config_path, 'w') as f:
            json.dump({
                "activation_key": key_str,
                "slot_bindings": new_bindings,
                "box_precision": new_box_cfg,
                "highlight_hex": new_hex
            }, f, indent=4)
        
        self.activation_key_str = key_str
        self.VK_ACTIVATION = self.KEY_MAP.get(key_str, 0x51)
        self.slot_bindings = new_bindings
        self.box_cfg = new_box_cfg
        self.highlight_hex = new_hex
        
        # Update the live OpenCV color mask
        self.lower_color, self.upper_color = self.hex_to_hsv_bounds(self.highlight_hex)

    def calculate_bounds(self, screen_w, screen_h, cfg):
        w_scale = max(1, cfg["w_scale"])
        h_scale = max(1, cfg["h_scale"])
        
        box_width = int(screen_w * (w_scale / 1000.0))
        box_height = int(screen_h * (h_scale / 1000.0))
        
        base_left = (screen_w - box_width) // 2
        base_top = screen_h - box_height
        
        x_shift_pixels = int(screen_w * ((cfg["x_shift"] - 500) / 1000.0))
        y_shift_pixels = int(screen_h * ((cfg["y_shift"] - 500) / 1000.0))
        
        left_offset = base_left + x_shift_pixels
        top_offset = base_top + y_shift_pixels
        
        left_offset = max(0, min(left_offset, screen_w - box_width))
        top_offset = max(0, min(top_offset, screen_h - box_height))
        
        return {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}

    def open_settings(self, parent_window):
        settings_win = tk.Toplevel(parent_window)
        settings_win.title(f"{self.name} - Configuration")
        # Made taller to fit the color settings
        settings_win.geometry("380x520") 
        settings_win.configure(bg="#333333")
        settings_win.transient(parent_window) 
        
        tk.Label(settings_win, text="Combat Matrix Settings", bg="#333333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        # --- Top Section: Activation Key & Color ---
        top_frame = tk.Frame(settings_win, bg="#333333")
        top_frame.pack(pady=5, fill=tk.X, padx=20)
        
        # Activation Key
        tk.Label(top_frame, text="Activation Key:", bg="#333333", fg="#aaaaaa").grid(row=0, column=0, sticky="w", pady=5)
        key_var = tk.StringVar(value=self.activation_key_str)
        ttk.Combobox(top_frame, textvariable=key_var, values=list(self.KEY_MAP.keys()), state="readonly", width=8).grid(row=0, column=1, sticky="w", padx=10)
        
        # Custom Highlight Color
        tk.Label(top_frame, text="Highlight Hex Color:", bg="#333333", fg="#aaaaaa").grid(row=1, column=0, sticky="w", pady=5)
        color_var = tk.StringVar(value=self.highlight_hex)
        tk.Entry(top_frame, textvariable=color_var, width=11).grid(row=1, column=1, sticky="w", padx=10)
        
        def reset_color():
            color_var.set("#00FFFF")
            
        tk.Button(top_frame, text="Reset Cyan", bg="#555555", fg="white", font=("Arial", 8), command=reset_color).grid(row=1, column=2, sticky="w")
        
        # Addon Warning Note
        tk.Label(settings_win, text="*Custom colors require 'ActionBarsEnhanced' addon", bg="#333333", fg="#ffcc00", font=("Arial", 8, "italic")).pack()
        
        tk.Label(settings_win, text="Action Bar Keybinds (Left to Right)", bg="#333333", fg="white", font=("Arial", 10, "underline")).pack(pady=(15, 5))
        
        # --- 12-Slot Grid UI ---
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
            self.save_config(key_str=key_var.get(), new_bindings=new_slots, new_hex=color_var.get())
            self.log(f"[{self.name}] Configuration saved! Targeting Color: {self.highlight_hex}")
            settings_win.destroy()
            
        button_frame = tk.Frame(settings_win, bg="#333333")
        button_frame.pack(pady=15, fill=tk.X, padx=20)
        tk.Button(button_frame, text="Save & Close", bg="#4CAF50", fg="white", command=save_and_close).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        tk.Button(button_frame, text="Vision Test", bg="#555555", fg="white", command=self.run_vision_test).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)

    def start(self):
        self.log(f"[{self.name}] Matrix Online. Hold '{self.activation_key_str}' in-game to activate.")
        self.is_running = True
        self.combat_loop()
        return True

    def stop(self):
        self.is_running = False
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
                        self.log(f"[{self.name}] Ceasefire. Matrix Online. Hold '{self.activation_key_str}' to activate.")
                        is_engaged = False
                    time.sleep(0.05)
                    continue

                if not is_engaged:
                    self.log(f"[{self.name}] Target engaged! Firing sequence initiated...")
                    is_engaged = True

                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                # USING DYNAMIC COLOR MASKS
                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 200:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        center_x = x + (w // 2)
                        active_slot_index = center_x // slot_width
                        
                        if 0 <= active_slot_index < len(self.slot_bindings):
                            target_key = self.slot_bindings[active_slot_index]
                            if target_key != 'Unbound':
                                # 1. Human Visual Reaction Time Delay
                                if not is_engaged:
                                    reaction_delay = random.uniform(0.15, 0.25)
                                    time.sleep(reaction_delay)
                                
                                # 2. Mechanical Keyboard Hold Duration
                                key_hold_time = random.uniform(0.03, 0.08)
                                
                                self.log(f"[{self.name}] Strike! Slot {active_slot_index + 1} -> Pressing '{target_key}'")
                                
                                # --- THE FIX: Explicit Hardware State Control ---
                                pydirectinput.keyDown(target_key)
                                time.sleep(key_hold_time)
                                pydirectinput.keyUp(target_key)
                                
                                # 3. Human Spam Rate
                                human_tap_delay = random.uniform(0.15, 0.35)
                                time.sleep(human_tap_delay) 
                            else:
                                time.sleep(random.uniform(0.04, 0.08))
                else:
                    # Randomize the "looking" pulse so the screen captures aren't uniformly spaced
                    time.sleep(random.uniform(0.03, 0.07))

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
                    x_line = i * slot_width
                    cv2.line(img_bgr, (x_line, 0), (x_line, monitor["height"]), (0, 255, 0), 1)

                # USING DYNAMIC COLOR MASKS
                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 50:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        
                        center_x = x + (w // 2)
                        active_slot = (center_x // slot_width) + 1
                        cv2.putText(img_bgr, f"Target: Slot {active_slot}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.putText(img_bgr, "Press 'S' to Save", (10, monitor["height"] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(img_bgr, "Press 'X' to Close", (10, monitor["height"] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.imshow("Action Bar Calibration", img_bgr)
                cv2.imshow("Custom Color Mask", mask)
                
                key = cv2.waitKey(25) & 0xFF
                if key == ord('x'):
                    self.log(f"[{self.name}] Calibration closed without saving.")
                    break
                elif key == ord('s'):
                    self.save_config(new_box_cfg=live_cfg)
                    self.log(f"[{self.name}] SUCCESS: Micro-precision dimensions saved!")
                    break

        cv2.destroyAllWindows()