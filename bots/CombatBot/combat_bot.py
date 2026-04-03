import time
import cv2
import numpy as np
import mss
import pydirectinput
import ctypes

class CombatBot:
    """
    A reactive DPS assistant for World of Warcraft.
    
    This bot scans the action bar for the cyan 'Assisted highlight' glow.
    It only executes actions while the user is actively holding down the 'Q' key.
    """

    def __init__(self, log_callback):
        self.is_running = False
        self.name = "CombatBot"
        self.log = log_callback 
        
        # Action Bar Keybinds
        self.action_keys = ['1', '2', '3', '4', '5', '6', '7']
        self.lower_cyan = np.array([85, 150, 150])
        self.upper_cyan = np.array([105, 255, 255])
        
        # Hardware Virtual Key Code for the 'Q' key (0x51)
        self.VK_Q = 0x51

    def start(self):
        self.log(f"[{self.name}] Matrix Online. Hold 'Q' in-game to activate.")
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
        """Checks if the hardware 'Q' key is currently pressed down."""
        # 0x8000 is the bitmask that checks the "currently pressed" state
        return ctypes.windll.user32.GetAsyncKeyState(self.VK_Q) & 0x8000

    def combat_loop(self):
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_width = primary_monitor["width"]
            screen_height = primary_monitor["height"]
            
            # --- UPDATED: Half-size dimensions ---
            box_width = screen_width // 6       
            box_height = screen_height // 20    
            
            # --- UPDATED: Absolute bottom alignment ---
            left_offset = (screen_width - box_width) // 2
            top_offset = screen_height - box_height
            
            monitor = {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}
            slot_width = box_width // len(self.action_keys)

            while self.is_running:
                # 1. Are we in the game?
                if not self.is_game_active():
                    time.sleep(1)
                    continue

                # 2. Is the user holding 'Q'?
                if not self.is_activation_key_held():
                    time.sleep(0.05) # Sleep briefly to save CPU, then check again
                    continue

                # 3. Vision Analysis
                sct_img = sct.grab(monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv_img, self.lower_cyan, self.upper_cyan)
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    
                    if cv2.contourArea(largest_contour) > 100:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        center_x = x + (w // 2)
                        active_slot_index = center_x // slot_width
                        
                        if 0 <= active_slot_index < len(self.action_keys):
                            target_key = self.action_keys[active_slot_index]
                            
                            self.log(f"[{self.name}] Strike! Slot {active_slot_index + 1} -> Pressing '{target_key}'")
                            pydirectinput.press(target_key)
                            
                            # The game's GCD will cap our speed, but we sleep to prevent 1000 presses a second
                            time.sleep(0.1) 
                else:
                    time.sleep(0.05)