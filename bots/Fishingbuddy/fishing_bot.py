import time
import cv2
import numpy as np
import mss
import pydirectinput
import ctypes  # Built-in library to interact with Windows OS
import random

class FishingBot:
    """
    A Computer Vision-based automation bot for fishing in World of Warcraft.
    
    This bot uses OpenCV to detect the red feather of the fishing bobber and 
    monitors pixel deltas to determine when a fish has bitten. It uses 
    pydirectinput to send hardware-level keystrokes for casting and looting.
    """
    
    def __init__(self, log_callback):
        """
        Initializes the FishingBot instance and configures hardware keybinds.

        Args:
            log_callback (function): A reference to the GUI's logging function, 
                                     allowing the bot to print messages to the UI.
        """
        self.is_running = False
        self.name = "Fishingbuddy"
        self.log = log_callback 
        
        # --- NEW: Manually register DirectX scan codes for Numpad ---
        pydirectinput.KEYBOARD_MAPPING['num0'] = 0x52
        pydirectinput.KEYBOARD_MAPPING['num2'] = 0x50 # Numpad 2 (if you want to use it for looting!)
        
        # --- GAME KEYBINDS ---
        self.key_cast = 'num0'
        self.key_loot = 'num0'
        
        # OpenCV Color Mask bounds for Red
        self.lower_red = np.array([0, 120, 70])
        self.upper_red = np.array([10, 255, 255])

    def start(self):
        """
        Sets the running flag to True and initiates the main fishing loop.

        Returns:
            bool: True if the bot successfully started the automation sequence.
        """
        self.log(f"[{self.name}] Initializing Vision Engine...")
        self.is_running = True
        self.log(f"[{self.name}] Starting automation sequence...")
        self.fishing_loop()
        return True

    def stop(self):
        """
        Safely flags the bot to stop running. 
        
        Note: The bot will finish its current micro-action (like waiting for 
        a sleep timer) before fully exiting the loop to prevent game crashes.
        """
        self.is_running = False
        self.log(f"[{self.name}] Stop command received. Halting after current action...")

    def is_game_active(self):
        """
        Checks if World of Warcraft is the currently focused window.
        Queries the Windows OS to check if WoW is the active window.

        Returns:
            bool: True if 'wow' or 'world of warcraft' is in the title of the 
                  currently focused foreground window.
        """
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        active_title = buf.value.lower()
        
        # Check if "wow" or "world of warcraft" is in the active window's title
        return "wow" in active_title or "world of warcraft" in active_title

    def get_red_pixel_count(self, sct, monitor):
        """
        Helper function: Takes a screenshot and returns the number of red pixels.

        Args:
            sct (mss.mss): The active screen capture instance.
            monitor (dict): The coordinates and dimensions of the capture box.

        Returns:
            int: The total number of pixels matching the defined red HSV mask.
        """
        sct_img = sct.grab(monitor)
        img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
        hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_img, self.lower_red, self.upper_red)
        return cv2.countNonZero(mask)

    def fishing_loop(self):
        """
        The core automation loop.
        
        Handles dynamic screen scaling, dual-baseline verification (pre-cast 
        and post-cast), and continuous screenshot analysis to detect the 
        bobber's splash animation via pixel deltas.
        """
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_width = primary_monitor["width"]
            screen_height = primary_monitor["height"]
            
            box_width = screen_width // 6
            box_height = screen_height // 3
            left_offset = (screen_width - box_width) // 2
            top_offset = (screen_height - box_height) // 2
            top_offset -= screen_height // 5
            
            monitor = {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}

            while self.is_running:
                # --- NEW: Wait for Active Window ---
                if not self.is_game_active():
                    self.log(f"[{self.name}] Paused. Waiting for WoW to be the active window...")
                    while self.is_running and not self.is_game_active():
                        time.sleep(1)
                    if not self.is_running: break
                    self.log(f"[{self.name}] WoW focused! Resuming...")
                    time.sleep(1) # Give the user a second to settle

                # --- NEW: Baseline 1 (No Bobber) ---
                time.sleep(1.0)
                baseline_no_bobber = self.get_red_pixel_count(sct, monitor)
                self.log(f"[{self.name}] Water Baseline: {baseline_no_bobber} red pixels.")

                # 1. Cast the line
                self.log(f"[{self.name}] Casting line...")
                pydirectinput.press(self.key_cast)
                
                # 2. Wait for the bobber to land
                time.sleep(3.0) 
                if not self.is_running: break 
                
                # --- NEW: Baseline 2 (With Bobber) ---
                baseline_with_bobber = self.get_red_pixel_count(sct, monitor)
                
                # Verify the cast was actually successful! (Did we gain at least 40 red pixels?)
                if baseline_with_bobber < (baseline_no_bobber + 40):
                    self.log(f"[{self.name}] ERROR: Bobber not detected. Cast likely failed. Retrying...")
                    time.sleep(1)
                    continue # Skips the rest of the loop and starts over from the top!
                
                self.log(f"[{self.name}] Bobber Verified: {baseline_with_bobber} red pixels.")
                self.log(f"[{self.name}] Watching for splash...")
                
                timeout = time.time() + 20 
                splash_detected = False
                time.sleep(2.0)

                # 4. The Watch Loop 
                while time.time() < timeout and self.is_running:
                    # If user alt-tabs out during the wait, pause the loop safely
                    if not self.is_game_active(): break 

                    current_pixels = self.get_red_pixel_count(sct, monitor)
                    
                    # The Delta Check: Compare against the bobber baseline
                    if (baseline_with_bobber - current_pixels) > 80:
                        self.log(f"[{self.name}] SPLASH DETECTED! (Pixels dropped to {current_pixels})")
                        splash_detected = True
                        break
                        
                    time.sleep(0.1) 

                if not self.is_running: break

                # 6. Looting Logic
                if splash_detected:
                    self.log(f"[{self.name}] Looting fish...")
                    reaction_time = random.randint(60, 220)
                    time.sleep(reaction_time/1000) # Sleep random amount of milliseconds
                    pydirectinput.press(self.key_loot)
                    time.sleep(1.0) # Wait for loot window / character animation
                elif self.is_game_active():
                    self.log(f"[{self.name}] Cast timed out. Retrying...")
                    time.sleep(1.0)