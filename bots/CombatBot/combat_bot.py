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
import sys
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(base_dir)
from utils.player_state import GameState

class CombatBot:
    """
    A reactive DPS assistant that utilizes OpenCV to monitor the UI for ability 
    highlights and executes keystrokes with randomized human-like variance.
    """

    def __init__(self, log_callback):
        """
        Initializes the CombatBot instance, sets default parameters, and loads user configuration.

        Args:
            log_callback (function): A reference to the GUI's logging function.
        """
        self.is_running = False
        self.name = "CombatBot"
        self.log = log_callback 

        # Initialize the state tracker
        self.state_tracker = GameState(self.log)
        
        # Hardware key map for the activation toggle
        self.KEY_MAP = {
            "Q": 0x51, "E": 0x45, "R": 0x52, "F": 0x46, "T": 0x54, 
            "C": 0x43, "V": 0x56, "Shift": 0x10, "Ctrl": 0x11, "Alt": 0x12
        }
        
        # Whitelist of valid inputs for pydirectinput, including the 'Unbound' ignore flag
        self.VALID_BINDS = [
            'Unbound', '1','2','3','4','5','6','7','8','9','0','-','=',
            'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12',
            'q','e','r','t','f','g','z','x','c','v','num0','num1','num2'
        ]
        
        self.default_slots = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=']
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        
        # Load persisted settings immediately upon instantiation
        self.load_config()

    def hex_to_hsv_bounds(self, hex_color):
        """
        Translates a standard HTML Hex color code into OpenCV HSV boundaries.
        
        Calculates a tight Hue bound to strictly target the specific color, while 
        providing a wide net for Saturation and Value to account for glowing UI effects.

        Args:
            hex_color (str): The hex string (e.g., '#00FFFF').

        Returns:
            tuple: A pair of numpy arrays representing the (lower_bound, upper_bound) in HSV format.
        """
        hex_color = hex_color.lstrip('#')
        
        # Fallback to pure Cyan if the user inputs an invalid string
        if len(hex_color) != 6:
            hex_color = "00FFFF"
            
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Create a 1-pixel RGB image and use OpenCV to translate it to HSV
            rgb_pixel = np.uint8([[[r, g, b]]])
            hsv_pixel = cv2.cvtColor(rgb_pixel, cv2.COLOR_RGB2HSV)[0][0]
            
            h = hsv_pixel[0]
            
            # Set boundaries: +/- 10 Hue variance, wide Saturation/Value variance
            lower_bound = np.array([max(0, h - 10), 100, 100])
            upper_bound = np.array([min(179, h + 10), 255, 255])
            
            return lower_bound, upper_bound
        except ValueError:
            # Absolute safety fallback for malformed conversions
            return np.array([85, 100, 100]), np.array([105, 255, 255])

    def load_config(self):
        """
        Reads the local config.json file and assigns values to instance variables.
        If no configuration exists, it establishes standard default values.
        """
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.activation_key_str = config.get("activation_key", "Q")
                self.slot_bindings = config.get("slot_bindings", self.default_slots)
                self.box_cfg = config.get("box_precision", {"w_scale": 250, "h_scale": 50, "x_shift": 500, "y_shift": 500})
                self.highlight_hex = config.get("highlight_hex", "#00FFFF")
        else:
            self.activation_key_str = "Q" 
            self.slot_bindings = self.default_slots.copy()
            self.box_cfg = {"w_scale": 250, "h_scale": 50, "x_shift": 500, "y_shift": 500}
            self.highlight_hex = "#00FFFF"
            
        # Register the physical hardware scan code
        self.VK_ACTIVATION = self.KEY_MAP.get(self.activation_key_str, 0x51)
        
        # Generate the live OpenCV color mask bounds
        self.lower_color, self.upper_color = self.hex_to_hsv_bounds(self.highlight_hex)

    def save_config(self, key_str=None, new_bindings=None, new_box_cfg=None, new_hex=None):
        """
        Writes the current settings to the local config.json file to persist across sessions.
        Allows for partial updates by defaulting to current instance variables if arguments are omitted.
        """
        key_str = key_str or self.activation_key_str
        new_bindings = new_bindings or self.slot_bindings
        new_box_cfg = new_box_cfg or self.box_cfg
        new_hex = new_hex or self.highlight_hex

        if not new_hex.startswith('#'):
            new_hex = '#' + new_hex

        with open(self.config_path, 'w') as f:
            json.dump({
                "activation_key": key_str,
                "slot_bindings": new_bindings,
                "box_precision": new_box_cfg,
                "highlight_hex": new_hex
            }, f, indent=4)
        
        # Immediately apply saved configurations to active memory
        self.activation_key_str = key_str
        self.VK_ACTIVATION = self.KEY_MAP.get(key_str, 0x51)
        self.slot_bindings = new_bindings
        self.box_cfg = new_box_cfg
        self.highlight_hex = new_hex
        self.lower_color, self.upper_color = self.hex_to_hsv_bounds(self.highlight_hex)

    def calculate_bounds(self, screen_w, screen_h, cfg):
        """
        Dynamically calculates absolute pixel coordinates for the screen capture bounding box 
        based on resolution-independent per-mille (1/1000) scaling factors.

        Args:
            screen_w (int): The absolute width of the primary monitor.
            screen_h (int): The absolute height of the primary monitor.
            cfg (dict): The dictionary containing precision tracking scale and shift parameters.

        Returns:
            dict: The dictionary of calculated offsets (top, left, width, height) required by `mss`.
        """
        w_scale = max(1, cfg["w_scale"])
        h_scale = max(1, cfg["h_scale"])
        
        # Calculate raw width and height based on the 1000-scale
        box_width = int(screen_w * (w_scale / 1000.0))
        box_height = int(screen_h * (h_scale / 1000.0))
        
        # Establish base centering at the absolute bottom of the screen
        base_left = (screen_w - box_width) // 2
        base_top = screen_h - box_height
        
        # Apply X/Y coordinate shifts (500 is considered structural dead-center)
        x_shift_pixels = int(screen_w * ((cfg["x_shift"] - 500) / 1000.0))
        y_shift_pixels = int(screen_h * ((cfg["y_shift"] - 500) / 1000.0))
        
        left_offset = base_left + x_shift_pixels
        top_offset = base_top + y_shift_pixels
        
        # Clamp values to ensure the capture box does not bleed off-screen
        left_offset = max(0, min(left_offset, screen_w - box_width))
        top_offset = max(0, min(top_offset, screen_h - box_height))
        
        return {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}

    def open_settings(self, parent_window):
        """
        Generates a bot-specific Tkinter modal window over the main GUI to handle 
        local configurations such as activation keys, custom colors, and keybind arrays.

        Args:
            parent_window (tk.Tk): The root window of the Master GUI to attach the Toplevel modal.
        """
        settings_win = tk.Toplevel(parent_window)
        settings_win.title(f"{self.name} - Configuration")
        settings_win.geometry("380x520") 
        settings_win.configure(bg="#333333")
        settings_win.transient(parent_window) 
        
        tk.Label(settings_win, text="Combat Matrix Settings", bg="#333333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        # --- Top UI: Activation Key & Target Color ---
        top_frame = tk.Frame(settings_win, bg="#333333")
        top_frame.pack(pady=5, fill=tk.X, padx=20)
        
        tk.Label(top_frame, text="Activation Key:", bg="#333333", fg="#aaaaaa").grid(row=0, column=0, sticky="w", pady=5)
        key_var = tk.StringVar(value=self.activation_key_str)
        ttk.Combobox(top_frame, textvariable=key_var, values=list(self.KEY_MAP.keys()), state="readonly", width=8).grid(row=0, column=1, sticky="w", padx=10)
        
        tk.Label(top_frame, text="Highlight Hex Color:", bg="#333333", fg="#aaaaaa").grid(row=1, column=0, sticky="w", pady=5)
        color_var = tk.StringVar(value=self.highlight_hex)
        tk.Entry(top_frame, textvariable=color_var, width=11).grid(row=1, column=1, sticky="w", padx=10)
        
        def reset_color():
            color_var.set("#00FFFF")
            
        tk.Button(top_frame, text="Reset Cyan", bg="#555555", fg="white", font=("Arial", 8), command=reset_color).grid(row=1, column=2, sticky="w")
        tk.Label(settings_win, text="*Custom colors require 'ActionBarsEnhanced' addon", bg="#333333", fg="#ffcc00", font=("Arial", 8, "italic")).pack()
        
        tk.Label(settings_win, text="Action Bar Keybinds (Left to Right)", bg="#333333", fg="white", font=("Arial", 10, "underline")).pack(pady=(15, 5))
        
        # --- 12-Slot Keybind Grid Generator ---
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
            """Gathers all Tkinter variables and delegates saving to the save_config method."""
            new_slots = [var.get() for var in self.slot_vars]
            self.save_config(key_str=key_var.get(), new_bindings=new_slots, new_hex=color_var.get())
            self.log(f"[{self.name}] Configuration saved! Targeting Color: {self.highlight_hex}")
            settings_win.destroy()
            
        # Action Buttons
        button_frame = tk.Frame(settings_win, bg="#333333")
        button_frame.pack(pady=10, fill=tk.X, padx=20)
        tk.Button(button_frame, text="Save & Close", bg="#4CAF50", fg="white", command=save_and_close).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        tk.Button(button_frame, text="Calibrate Action Bar", bg="#555555", fg="white", command=self.run_vision_test).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        
        # NEW: Game State Calibration Button
        tk.Button(settings_win, text="Calibrate Player Frames", bg="#555555", fg="white", command=self.state_tracker.run_vision_test).pack(pady=5, fill=tk.X, padx=25)

    def start(self):
        """
        Flags the bot as active and initiates the primary combat loop in the current thread.

        Returns:
            bool: True indicating successful sequence startup.
        """
        self.log(f"[{self.name}] Matrix Online. Hold '{self.activation_key_str}' in-game to activate.")
        self.is_running = True
        self.combat_loop()
        return True

    def stop(self):
        """Safely modifies the running state, allowing the loop to close elegantly."""
        self.is_running = False
        self.log(f"[{self.name}] Standing down...")

    def is_game_active(self):
        """
        Validates context by querying the OS for the active foreground window.
        Prevents the bot from spamming inputs if the user tabs out of the game.

        Returns:
            bool: True if 'wow' or 'world of warcraft' is found in the window title.
        """
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "wow" in buf.value.lower() or "world of warcraft" in buf.value.lower()

    def is_activation_key_held(self):
        """
        Checks the literal hardware state of the designated activation key via ctypes.

        Returns:
            bool: True if the specific virtual hardware key is actively depressed.
        """
        return ctypes.windll.user32.GetAsyncKeyState(self.VK_ACTIVATION) & 0x8000

    def combat_loop(self):
        """
        The central automation thread. Processes continuous screen captures, converts 
        them to HSV, masks the configured color, calculates positional deltas, and 
        issues hardware keystrokes augmented by randomized heuristic delays.
        """
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            # Fetch dynamic capture boundaries based on persistent config
            monitor = self.calculate_bounds(screen_w, screen_h, self.box_cfg)
            
            # Divide the capture box into equal virtual segments
            slot_width = monitor["width"] // len(self.slot_bindings)
            is_engaged = False

            while self.is_running:
                # 1. State Verification: Ensure the game is focused and key is held
                if not self.is_game_active() or not self.is_activation_key_held():
                    if is_engaged:
                        self.log(f"[{self.name}] Ceasefire. Matrix Online. Hold '{self.activation_key_str}' to activate.")
                        is_engaged = False
                    time.sleep(0.05)
                    continue

                if not is_engaged:
                    self.log(f"[{self.name}] Target engaged! Firing sequence initiated...")
                    is_engaged = True

                # 2. Vision Pipeline: Capture, Convert, Mask, and Map Contours
                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 3. Positional Processing
                if contours:
                    # Ignore minor pixel noise by ensuring the blob has mass (> 50 pixels)
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 50:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        center_x = x + (w // 2)
                        
                        # Determine the active slot by locating the X coordinate in our virtual grid
                        active_slot_index = center_x // slot_width
                        
                        if 0 <= active_slot_index < len(self.slot_bindings):
                            target_key = self.slot_bindings[active_slot_index]
                            
                            # 4. Humanized Input Execution
                            if target_key != 'Unbound':
                                # Human Visual Reaction Time Delay (First strike only)
                                if not is_engaged:
                                    reaction_delay = random.uniform(0.15, 0.25)
                                    time.sleep(reaction_delay)
                                
                                # Mechanical Keyboard Switch Travel Time
                                key_hold_time = random.uniform(0.03, 0.08)
                                
                                self.log(f"[{self.name}] Strike! Slot {active_slot_index + 1} -> Pressing '{target_key}'")
                                
                                # Break out keyDown and keyUp for explicit hold-time control
                                pydirectinput.keyDown(target_key)
                                time.sleep(key_hold_time)
                                pydirectinput.keyUp(target_key)
                                
                                # GCD Human Spam Rate Simulation
                                human_tap_delay = random.uniform(0.15, 0.35)
                                time.sleep(human_tap_delay) 
                            else:
                                # Minor variance delay if an 'Unbound' slot glows
                                time.sleep(random.uniform(0.04, 0.08))
                else:
                    # Randomize the base idle loop to prevent uniformly spaced screen captures
                    time.sleep(random.uniform(0.03, 0.07))

    def run_vision_test(self):
        """
        Initializes an independent, interactive OpenCV window. Uses live trackbars 
        to allow the user to visualize and manipulate the `mss` capture bounds 
        in real-time for precise pixel framing.
        """
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
                # Poll active state of trackbars
                live_cfg = {
                    "w_scale": cv2.getTrackbarPos("Width (0-1000)", "Action Bar Calibration"),
                    "h_scale": cv2.getTrackbarPos("Height (0-1000)", "Action Bar Calibration"),
                    "x_shift": cv2.getTrackbarPos("X Shift (500=Mid)", "Action Bar Calibration"),
                    "y_shift": cv2.getTrackbarPos("Y Shift (500=Mid)", "Action Bar Calibration")
                }
                
                # Recalculate physical pixel boundaries in real-time
                monitor = self.calculate_bounds(screen_w, screen_h, live_cfg)
                slot_width = monitor["width"] // len(self.slot_bindings)

                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                
                # Overlay the division grid representing virtual slots
                for i in range(1, len(self.slot_bindings)):
                    x_line = i * slot_width
                    cv2.line(img_bgr, (x_line, 0), (x_line, monitor["height"]), (0, 255, 0), 1)

                mask = cv2.inRange(hsv_img, self.lower_color, self.upper_color)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 50:
                        # Draw a bounding rectangle around detected target
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        
                        # Validate the logical slot mapping
                        center_x = x + (w // 2)
                        active_slot = (center_x // slot_width) + 1
                        cv2.putText(img_bgr, f"Target: Slot {active_slot}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Overlay UI instructions
                cv2.putText(img_bgr, "Press 'S' to Save", (10, monitor["height"] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(img_bgr, "Press 'X' to Close", (10, monitor["height"] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.imshow("Action Bar Calibration", img_bgr)
                cv2.imshow("Custom Color Mask", mask)
                
                # Handle user interaction (polling every 25ms)
                key = cv2.waitKey(25) & 0xFF
                if key == ord('x'):
                    self.log(f"[{self.name}] Calibration closed without saving.")
                    break
                elif key == ord('s'):
                    # Save the new live_cfg back to persistent storage via config.json
                    self.save_config(new_box_cfg=live_cfg)
                    self.log(f"[{self.name}] SUCCESS: Micro-precision dimensions saved!")
                    break

        cv2.destroyAllWindows()