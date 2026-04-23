"""
Fishingbuddy - Automated WoW Fishing Assistant
Utilizes OpenCV computer vision to detect bobber splashes.
Features customizable keybinds, dynamic screen scaling, humanized inputs, 
an adjustable color strictness algorithm, and crash-proof thread handling.
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
        
        # --- CRITICAL FIX 1: Disable the invisible mouse corner Fail-Safe ---
        pydirectinput.FAILSAFE = False 
        
        pydirectinput.KEYBOARD_MAPPING['num0'] = 0x52
        pydirectinput.KEYBOARD_MAPPING['num1'] = 0x4F
        pydirectinput.KEYBOARD_MAPPING['num2'] = 0x50
        
        self.VALID_BINDS = [
            '1','2','3','4','5','6','7','8','9','0','-','=',
            'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12',
            'q','e','r','t','f','g','z','x','c','v','num0','num1','num2'
        ]
        
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.load_config()

    def calculate_red_bounds(self, strictness):
        strictness = max(0, min(100, strictness))
        
        max_hue = int(15 - (strictness / 100.0 * 7))     
        min_sat = int(50 + (strictness / 100.0 * 110))   
        min_val = int(50 + (strictness / 100.0 * 100))   
        
        # --- CRITICAL FIX 2: Explicitly type arrays as 8-bit to prevent OpenCV crashes ---
        lower_red = np.array([0, min_sat, min_val], dtype=np.uint8)
        upper_red = np.array([max_hue, 255, 255], dtype=np.uint8)
        
        return lower_red, upper_red

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.key_cast = config.get("key_cast", "num0")
                self.key_loot = config.get("key_loot", "num0")
                self.red_strictness = config.get("red_strictness", 100)
        else:
            self.key_cast = "num0"
            self.key_loot = "num0"
            self.red_strictness = 100 
            
        self.lower_red, self.upper_red = self.calculate_red_bounds(self.red_strictness)

    def save_config(self, key_cast, key_loot, strictness):
        self.key_cast = key_cast
        self.key_loot = key_loot
        self.red_strictness = strictness

        with open(self.config_path, 'w') as f:
            json.dump({
                "key_cast": self.key_cast,
                "key_loot": self.key_loot,
                "red_strictness": self.red_strictness
            }, f, indent=4)
            
        self.lower_red, self.upper_red = self.calculate_red_bounds(self.red_strictness)

    def open_settings(self, parent_window):
        settings_win = tk.Toplevel(parent_window)
        settings_win.title(f"{self.name} - Configuration")
        settings_win.geometry("320x300") 
        settings_win.configure(bg="#333333")
        settings_win.transient(parent_window) 
        
        tk.Label(settings_win, text="Fishingbuddy Settings", bg="#333333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        frame_cast = tk.Frame(settings_win, bg="#333333")
        frame_cast.pack(pady=5)
        tk.Label(frame_cast, text="Cast Key:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        cast_var = tk.StringVar(value=self.key_cast)
        ttk.Combobox(frame_cast, textvariable=cast_var, values=self.VALID_BINDS, state="readonly", width=8).pack(side=tk.LEFT)
        
        frame_loot = tk.Frame(settings_win, bg="#333333")
        frame_loot.pack(pady=5)
        tk.Label(frame_loot, text="Loot Key:", bg="#333333", fg="#aaaaaa", width=12, anchor="e").pack(side=tk.LEFT, padx=5)
        loot_var = tk.StringVar(value=self.key_loot)
        ttk.Combobox(frame_loot, textvariable=loot_var, values=self.VALID_BINDS, state="readonly", width=8).pack(side=tk.LEFT)
        
        frame_strict = tk.Frame(settings_win, bg="#333333")
        frame_strict.pack(pady=10)
        tk.Label(frame_strict, text="Red Filter Strictness (0 = Loose, 100 = Strict):", bg="#333333", fg="#aaaaaa").pack()
        strict_var = tk.IntVar(value=self.red_strictness)
        scale = tk.Scale(frame_strict, variable=strict_var, from_=0, to=100, orient=tk.HORIZONTAL, bg="#333333", fg="white", highlightthickness=0, length=200)
        scale.pack()
        
        def save_and_close():
            self.save_config(cast_var.get(), loot_var.get(), strict_var.get())
            self.log(f"[{self.name}] Config saved. Strictness set to {self.red_strictness}%.")
            settings_win.destroy()
            
        tk.Button(settings_win, text="Save & Close", bg="#4CAF50", fg="white", command=save_and_close).pack(pady=5, fill=tk.X, padx=40)
        tk.Button(settings_win, text="Run Vision Test", bg="#555555", fg="white", command=self.run_vision_test).pack(pady=5, fill=tk.X, padx=40)

    def is_game_active(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "wow" in buf.value.lower() or "world of warcraft" in buf.value.lower()

    def get_red_pixel_count(self, sct, monitor, custom_lower=None, custom_upper=None):
        lower = custom_lower if custom_lower is not None else self.lower_red
        upper = custom_upper if custom_upper is not None else self.upper_red
        
        sct_img = sct.grab(monitor)
        img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
        hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_img, lower, upper)
        return cv2.countNonZero(mask)

    def start(self):
        self.log(f"[{self.name}] Vision Engine initialized. Mask strictness: {self.red_strictness}%")
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
                # --- CRITICAL FIX 3: Try/Except Wrapper to catch silent thread deaths ---
                try:
                    if not self.is_game_active():
                        self.log(f"[{self.name}] Paused. Waiting for WoW focus...")
                        while self.is_running and not self.is_game_active():
                            time.sleep(1)
                        if not self.is_running: break
                        self.log(f"[{self.name}] Resuming...")
                        time.sleep(1) 
                        continue # Safely restart the loop from the top rather than plunging forward

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
                    # If anything fails, print the exact error to the GUI instead of dying silently!
                    self.log(f"[{self.name}] CRITICAL ERROR: {str(e)}")
                    time.sleep(2) # Sleep to prevent spamming the error log

    def run_vision_test(self):
        self.log(f"[{self.name}] Launching Vision Test...")
        
        cv2.namedWindow("Fishingbuddy - Vision Test")
        cv2.createTrackbar("Strictness %", "Fishingbuddy - Vision Test", self.red_strictness, 100, lambda x: None)

        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_width = primary_monitor["width"]
            screen_height = primary_monitor["height"]
            
            box_width = screen_width // 6
            box_height = screen_height // 3
            left_offset = (screen_width - box_width) // 2
            top_offset = (screen_height - box_height) // 2
            top_offset -= screen_height // 5
            
            monitor = {"top": int(max(0, top_offset)), "left": int(max(0, left_offset)), "width": int(box_width), "height": int(box_height)}

            while True:
                live_strictness = cv2.getTrackbarPos("Strictness %", "Fishingbuddy - Vision Test")
                live_lower, live_upper = self.calculate_red_bounds(live_strictness)
                
                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                mask = cv2.inRange(hsv_img, live_lower, live_upper)
                pixels = cv2.countNonZero(mask)

                cv2.putText(img_bgr, f"Red Pixels: {pixels}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(img_bgr, "Press 'S' to Save", (10, box_height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(img_bgr, "Press 'X' to Close", (10, box_height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.imshow("Fishingbuddy - Vision Test", img_bgr)
                cv2.imshow("Fishingbuddy - Live Mask", mask)
                
                key = cv2.waitKey(25) & 0xFF
                if key == ord('x'):
                    self.log(f"[{self.name}] Calibration closed.")
                    break
                elif key == ord('s'):
                    self.save_config(self.key_cast, self.key_loot, live_strictness)
                    self.log(f"[{self.name}] SUCCESS: Strictness saved at {live_strictness}%!")
                    break

        cv2.destroyAllWindows()