"""
Fishingbuddy - Automated WoW Fishing Assistant
Utilizes OpenCV computer vision to detect bobber splashes via pixel deltas.
Features customizable keybinds, dynamic color profiles, and UI calibration.
"""

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

class FishingBot:
    def __init__(self, log_callback):
        self.is_running = False
        self.name = "Fishingbuddy"
        self.log = log_callback 
        
        self.VALID_BINDS = [
            '1','2','3','4','5','6','7','8','9','0','-','=',
            'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12',
            'q','e','r','t','f','g','z','x','c','v','num0','num1','num2'
        ]
        
        # Define HSV color boundaries for the two unique features of the bobber
        self.COLOR_PROFILES = {
            "Red Feather": (np.array([0, 120, 70]), np.array([10, 255, 255])),
            "Blue Feather": (np.array([100, 100, 50]), np.array([130, 255, 255]))
        }
        
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.load_config()

    def load_config(self):
        """Loads settings and vision calibration from JSON."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.key_cast = config.get("key_cast", "num0")
                self.key_loot = config.get("key_loot", "num0")
                self.target_color = config.get("target_color", "Red Feather")
                self.box_cfg = config.get("box_precision", {"w_scale": 166, "h_scale": 333, "x_shift": 500, "y_shift": 300})
        else:
            self.key_cast = "num0"
            self.key_loot = "num0"
            self.target_color = "Red Feather"
            self.box_cfg = {"w_scale": 166, "h_scale": 333, "x_shift": 500, "y_shift": 300}
            
        self.lower_color, self.upper_color = self.COLOR_PROFILES.get(self.target_color, self.COLOR_PROFILES["Red Feather"])

    def save_config(self, key_cast=None, key_loot=None, target_color=None, new_box_cfg=None):
        """Saves settings to JSON."""
        self.key_cast = key_cast or self.key_cast
        self.key_loot = key_loot or self.key_loot
        self.target_color = target_color or self.target_color
        self.box_cfg = new_box_cfg or self.box_cfg

        with open(self.config_path, 'w') as f:
            json.dump({
                "key_cast": self.key_cast,
                "key_loot": self.key_loot,
                "target_color": self.target_color,
                "box_precision": self.box_cfg
            }, f, indent=4)
            
        self.lower_color, self.upper_color = self.COLOR_PROFILES.get(self.target_color, self.COLOR_PROFILES["Red Feather"])

    def calculate_bounds(self, screen_w, screen_h, cfg):
        """Calculates absolute pixel coordinates based on 1000-scale precision sliders."""
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
        """Generates the configuration UI."""
        settings_win = tk.Toplevel(parent_window)
        settings_win.title(f"{self.name} - Configuration")
        settings_win.geometry("300x350") 
        settings_win.configure(bg="#333333")
        settings_win.transient(parent_window) 
        
        tk.Label(settings_win, text="Fishingbuddy Settings", bg="#333333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Cast Key
        frame_cast = tk.Frame(settings_win, bg="#333333")
        frame_cast.pack(pady=5)
        tk.Label(frame_cast, text="Cast Key:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        cast_var = tk.StringVar(value=self.key_cast)
        ttk.Combobox(frame_cast, textvariable=cast_var, values=self.VALID_BINDS, state="readonly", width=8).pack(side=tk.LEFT)
        
        # Loot Key
        frame_loot = tk.Frame(settings_win, bg="#333333")
        frame_loot.pack(pady=5)
        tk.Label(frame_loot, text="Loot/Interact Key:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        loot_var = tk.StringVar(value=self.key_loot)
        ttk.Combobox(frame_loot, textvariable=loot_var, values=self.VALID_BINDS, state="readonly", width=8).pack(side=tk.LEFT)
        
        # Color Profile
        frame_color = tk.Frame(settings_win, bg="#333333")
        frame_color.pack(pady=15)
        tk.Label(frame_color, text="Track Feature:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        color_var = tk.StringVar(value=self.target_color)
        ttk.Combobox(frame_color, textvariable=color_var, values=list(self.COLOR_PROFILES.keys()), state="readonly", width=12).pack(side=tk.LEFT)
        
        def save_and_close():
            self.save_config(key_cast=cast_var.get(), key_loot=loot_var.get(), target_color=color_var.get())
            self.log(f"[{self.name}] Configuration saved. Tracking: {self.target_color}")
            settings_win.destroy()
            
        tk.Button(settings_win, text="Save & Close", bg="#4CAF50", fg="white", command=save_and_close).pack(pady=10, fill=tk.X, padx=40)
        tk.Button(settings_win, text="Vision Calibration Test", bg="#555555", fg="white", command=self.run_vision_test).pack(pady=5, fill=tk.X, padx=40)

    def is_game_active(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "wow" in buf.value.lower() or "world of warcraft" in buf.value.lower()

    def get_target_pixel_count(self, sct, monitor):
        sct_img = sct.grab(monitor)
        img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
        hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
        return cv2.countNonZero(mask)

    def start(self):
        self.log(f"[{self.name}] Vision Engine initialized. Tracking {self.target_color}.")
        self.is_running = True
        self.fishing_loop()
        return True

    def stop(self):
        self.is_running = False
        self.log(f"[{self.name}] Halting after current action...")

    def fishing_loop(self):
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            # Fetch dynamic bounds configured by user
            monitor = self.calculate_bounds(screen_w, screen_h, self.box_cfg)

            while self.is_running:
                if not self.is_game_active():
                    self.log(f"[{self.name}] Paused. Waiting for WoW focus...")
                    while self.is_running and not self.is_game_active():
                        time.sleep(1)
                    if not self.is_running: break
                    self.log(f"[{self.name}] Resuming...")
                    time.sleep(1) 

                time.sleep(1.0)
                baseline_no_bobber = self.get_target_pixel_count(sct, monitor)
                self.log(f"[{self.name}] Water Baseline: {baseline_no_bobber} pixels.")

                self.log(f"[{self.name}] Casting line...")
                pydirectinput.press(self.key_cast)
                
                time.sleep(3.0) 
                if not self.is_running: break 
                
                baseline_with_bobber = self.get_target_pixel_count(sct, monitor)
                
                # Verify cast success (Reduced threshold slightly since Blue feather is smaller than Red)
                if baseline_with_bobber < (baseline_no_bobber + 25):
                    self.log(f"[{self.name}] ERROR: Bobber not detected. Retrying...")
                    time.sleep(1)
                    continue 
                
                self.log(f"[{self.name}] Bobber Verified: {baseline_with_bobber} pixels.")
                self.log(f"[{self.name}] Watching for splash...")
                
                timeout = time.time() + 20 
                splash_detected = False
                time.sleep(2.0)

                while time.time() < timeout and self.is_running:
                    if not self.is_game_active(): break 

                    current_pixels = self.get_target_pixel_count(sct, monitor)
                    
                    # The Delta Check
                    if (baseline_with_bobber - current_pixels) > 50:
                        self.log(f"[{self.name}] SPLASH DETECTED! (Pixels dropped to {current_pixels})")
                        splash_detected = True
                        break
                        
                    time.sleep(0.1) 

                if not self.is_running: break

                if splash_detected:
                    self.log(f"[{self.name}] Looting fish...")
                    time.sleep(random.uniform(0.15, 0.25)) 
                    pydirectinput.press(self.key_loot)
                    time.sleep(1.0) 
                elif self.is_game_active():
                    self.log(f"[{self.name}] Cast timed out. Retrying...")
                    time.sleep(1.0)

    def run_vision_test(self):
        """Interactive tool to shrink the tracking box and test the color mask."""
        self.log(f"[{self.name}] Launching Vision Calibration...")
        
        cv2.namedWindow("Fishing Calibration")
        cv2.createTrackbar("Width (0-1000)", "Fishing Calibration", self.box_cfg["w_scale"], 1000, lambda x: None)
        cv2.createTrackbar("Height (0-1000)", "Fishing Calibration", self.box_cfg["h_scale"], 1000, lambda x: None)
        cv2.createTrackbar("X Shift (500=Mid)", "Fishing Calibration", self.box_cfg["x_shift"], 1000, lambda x: None)
        cv2.createTrackbar("Y Shift (500=Mid)", "Fishing Calibration", self.box_cfg["y_shift"], 1000, lambda x: None)

        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            while True:
                live_cfg = {
                    "w_scale": cv2.getTrackbarPos("Width (0-1000)", "Fishing Calibration"),
                    "h_scale": cv2.getTrackbarPos("Height (0-1000)", "Fishing Calibration"),
                    "x_shift": cv2.getTrackbarPos("X Shift (500=Mid)", "Fishing Calibration"),
                    "y_shift": cv2.getTrackbarPos("Y Shift (500=Mid)", "Fishing Calibration")
                }
                
                monitor = self.calculate_bounds(screen_w, screen_h, live_cfg)
                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                pixels = cv2.countNonZero(mask)

                cv2.putText(img_bgr, f"Tracking: {self.target_color}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(img_bgr, f"Pixels Found: {pixels}", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(img_bgr, "Press 'S' to Save", (10, monitor["height"] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(img_bgr, "Press 'X' to Close", (10, monitor["height"] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.imshow("Fishing Calibration", img_bgr)
                cv2.imshow("Color Mask", mask)
                
                key = cv2.waitKey(25) & 0xFF
                if key == ord('x'):
                    self.log(f"[{self.name}] Calibration closed.")
                    break
                elif key == ord('s'):
                    self.save_config(new_box_cfg=live_cfg)
                    self.log(f"[{self.name}] SUCCESS: Fishing dimensions saved!")
                    break

        cv2.destroyAllWindows()