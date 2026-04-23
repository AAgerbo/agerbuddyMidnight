"""
Fishingbuddy - Automated WoW Fishing Assistant
Utilizes OpenCV computer vision to detect bobber splashes.
Features customizable keybinds, dynamic screen scaling, humanized inputs, 
and crash-proof thread handling with pre-determined color boundaries.
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
        
        # Disable the invisible mouse corner Fail-Safe
        pydirectinput.FAILSAFE = False 
        
        # Map DirectX hardware scan codes for the Numpad
        pydirectinput.KEYBOARD_MAPPING['num0'] = 0x52
        pydirectinput.KEYBOARD_MAPPING['num1'] = 0x4F
        pydirectinput.KEYBOARD_MAPPING['num2'] = 0x50
        
        self.VALID_BINDS = [
            '1','2','3','4','5','6','7','8','9','0','-','=',
            'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12',
            'q','e','r','t','f','g','z','x','c','v','num0','num1','num2'
        ]
        
        # --- PRE-DETERMINED COLOR BOUNDARIES ---
        # Explicitly typed as 8-bit integers (uint8) to prevent OpenCV thread crashes
        self.lower_red = np.array([0, 120, 70], dtype=np.uint8)
        self.upper_red = np.array([10, 255, 255], dtype=np.uint8)
        
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.load_config()

    def load_config(self):
        """Loads keybind settings from JSON."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.key_cast = config.get("key_cast", "num0")
                self.key_loot = config.get("key_loot", "num0")
        else:
            self.key_cast = "num0"
            self.key_loot = "num0"

    def save_config(self, key_cast, key_loot):
        """Saves keybind settings to JSON."""
        self.key_cast = key_cast
        self.key_loot = key_loot

        with open(self.config_path, 'w') as f:
            json.dump({
                "key_cast": self.key_cast,
                "key_loot": self.key_loot
            }, f, indent=4)

    def open_settings(self, parent_window):
        """Generates the configuration UI."""
        settings_win = tk.Toplevel(parent_window)
        settings_win.title(f"{self.name} - Configuration")
        settings_win.geometry("300x220") 
        settings_win.configure(bg="#333333")
        settings_win.transient(parent_window) 
        
        tk.Label(settings_win, text="Fishingbuddy Settings", bg="#333333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Cast Key UI
        frame_cast = tk.Frame(settings_win, bg="#333333")
        frame_cast.pack(pady=5)
        tk.Label(frame_cast, text="Cast Key:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        cast_var = tk.StringVar(value=self.key_cast)
        ttk.Combobox(frame_cast, textvariable=cast_var, values=self.VALID_BINDS, state="readonly", width=8).pack(side=tk.LEFT)
        
        # Loot Key UI
        frame_loot = tk.Frame(settings_win, bg="#333333")
        frame_loot.pack(pady=5)
        tk.Label(frame_loot, text="Loot Key:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        loot_var = tk.StringVar(value=self.key_loot)
        ttk.Combobox(frame_loot, textvariable=loot_var, values=self.VALID_BINDS, state="readonly", width=8).pack(side=tk.LEFT)
        
        def save_and_close():
            self.save_config(cast_var.get(), loot_var.get())
            self.log(f"[{self.name}] Configuration saved.")
            settings_win.destroy()
            
        tk.Button(settings_win, text="Save & Close", bg="#4CAF50", fg="white", command=save_and_close).pack(pady=10, fill=tk.X, padx=40)
        tk.Button(settings_win, text="Run Vision Test", bg="#555555", fg="white", command=self.run_vision_test).pack(pady=0, fill=tk.X, padx=40)

    def is_game_active(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "wow" in buf.value.lower() or "world of warcraft" in buf.value.lower()

    def get_red_pixel_count(self, sct, monitor):
        """Captures the specified monitor region and counts pixels matching the red bounds."""
        sct_img = sct.grab(monitor)
        img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
        hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_img, self.lower_red, self.upper_red)
        return cv2.countNonZero(mask)

    def start(self):
        self.log(f"[{self.name}] Vision Engine initialized.")
        self.is_running = True
        self.fishing_loop()
        return True

    def stop(self):
        self.is_running = False
        self.log(f"[{self.name}] Halting after current action...")

    def fishing_loop(self):
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_width = primary_monitor["width"]
            screen_height = primary_monitor["height"]
            
            box_width = screen_width // 6
            box_height = screen_height // 3
            left_offset = (screen_width - box_width) // 2
            top_offset = (screen_height - box_height) // 2
            top_offset -= screen_height // 5
            
            # Use max(0, offset) to guarantee positive dimensions to prevent MSS crashes
            monitor = {"top": int(max(0, top_offset)), "left": int(max(0, left_offset)), "width": int(box_width), "height": int(box_height)}

            while self.is_running:
                # Try/Except Wrapper to catch silent thread deaths
                try:
                    if not self.is_game_active():
                        self.log(f"[{self.name}] Paused. Waiting for WoW focus...")
                        while self.is_running and not self.is_game_active():
                            time.sleep(1)
                        if not self.is_running: break
                        self.log(f"[{self.name}] Resuming...")
                        time.sleep(1) 
                        continue 

                    time.sleep(1.0)
                    baseline_no_bobber = self.get_red_pixel_count(sct, monitor)
                    self.log(f"[{self.name}] Water Baseline: {baseline_no_bobber} pixels.")

                    self.log(f"[{self.name}] Casting line...")
                    cast_hold_time = random.uniform(0.03, 0.08)
                    pydirectinput.keyDown(self.key_cast)
                    time.sleep(cast_hold_time)
                    pydirectinput.keyUp(self.key_cast)
                    
                    time.sleep(3.0) 
                    if not self.is_running: break 
                    
                    baseline_with_bobber = self.get_red_pixel_count(sct, monitor)
                    
                    if baseline_with_bobber < (baseline_no_bobber + 40):
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

                        current_pixels = self.get_red_pixel_count(sct, monitor)
                        
                        if (baseline_with_bobber - current_pixels) > 80:
                            self.log(f"[{self.name}] SPLASH DETECTED! (Pixels dropped to {current_pixels})")
                            splash_detected = True
                            break
                            
                        time.sleep(0.1) 

                    if not self.is_running: break

                    if splash_detected:
                        self.log(f"[{self.name}] Looting fish...")
                        reaction_time = random.uniform(0.15, 0.25)
                        time.sleep(reaction_time) 
                        
                        loot_hold_time = random.uniform(0.03, 0.08)
                        pydirectinput.keyDown(self.key_loot)
                        time.sleep(loot_hold_time)
                        pydirectinput.keyUp(self.key_loot)
                        
                        time.sleep(1.0) 
                    elif self.is_game_active():
                        self.log(f"[{self.name}] Cast timed out. Retrying...")
                        time.sleep(1.0)
                        
                except Exception as e:
                    self.log(f"[{self.name}] CRITICAL ERROR: {str(e)}")
                    time.sleep(2) 

    def run_vision_test(self):
        """Displays the OpenCV vision mask using the pre-determined red bounds."""
        self.log(f"[{self.name}] Launching Vision Test...")
        
        cv2.namedWindow("Fishingbuddy - Vision Test")

        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_width = primary_monitor["width"]
            screen_height = primary_monitor["height"]
            
            box_width = screen_width // 6
            box_height = screen_height // 4 
            left_offset = (screen_width - box_width) // 2
            top_offset = (screen_height - box_height) // 2
            top_offset -= screen_height // 5
            
            monitor = {"top": int(max(0, top_offset)), "left": int(max(0, left_offset)), "width": int(box_width), "height": int(box_height)}

            while True:
                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                mask = cv2.inRange(hsv_img, self.lower_red, self.upper_red)
                pixels = cv2.countNonZero(mask)

                cv2.putText(img_bgr, f"Red Pixels: {pixels}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(img_bgr, "Press 'X' to Close", (10, box_height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.imshow("Fishingbuddy - Vision Test", img_bgr)
                cv2.imshow("Fishingbuddy - Live Mask", mask)
                
                if cv2.waitKey(25) & 0xFF == ord('x'):
                    self.log(f"[{self.name}] Vision Test closed.")
                    break

        cv2.destroyAllWindows()