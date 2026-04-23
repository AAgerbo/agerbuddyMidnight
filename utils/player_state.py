"""
GameState - Real-time Player Memory Tracker
Runs a lightweight, independent thread to monitor player unit frames.
Uses unified 1D pixel arrays to calculate Health, Secondary Power, and Tertiary Power.
Features a 2x Zoom "Magnifying Glass" vision calibration tool.
"""

import time
import cv2
import numpy as np
import mss
import ctypes
import os
import json

class GameState:
    def __init__(self, log_callback):
        self.is_running = False
        self.name = "GameStateTracker"
        self.log = log_callback
        
        # --- RESOURCE VARIABLES (Live Data) ---
        self.health_pct = 100.0
        self.power_pct = 100.0
        self.tertiary_pct = 0.0 
        
        # --- STATE VARIABLES (Placeholders) ---
        self.in_combat = False
        self.is_dead = False
        self.is_mounted = False
        
        # --- VISION CONFIGURATION ---
        self.lower_health = np.array([40, 100, 100], dtype=np.uint8)
        self.upper_health = np.array([80, 255, 255], dtype=np.uint8)
        
        self.lower_power = np.array([100, 150, 100], dtype=np.uint8)
        self.upper_power = np.array([130, 255, 255], dtype=np.uint8)
        
        self.lower_tertiary = np.array([15, 150, 150], dtype=np.uint8)
        self.upper_tertiary = np.array([35, 255, 255], dtype=np.uint8)
        
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_config.json")
        self.load_config()

    def load_config(self):
        """Loads unified bounds and camera position."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.frame_cfg = config.get("frame_config", {
                    "w_scale": 150, "x_shift": 50, "health_y": 50, "power_y": 70, "tertiary_y": 90,
                    "cam_x": 0, "cam_y": 0 # Default camera to top-left
                })
                # Safety fallback for older config files
                if "cam_x" not in self.frame_cfg: self.frame_cfg["cam_x"] = 0
                if "cam_y" not in self.frame_cfg: self.frame_cfg["cam_y"] = 0
        else:
            self.frame_cfg = {
                "w_scale": 150, "x_shift": 50, "health_y": 50, "power_y": 70, "tertiary_y": 90,
                "cam_x": 0, "cam_y": 0
            }

    def save_config(self, new_cfg):
        self.frame_cfg = new_cfg
        with open(self.config_path, 'w') as f:
            json.dump({"frame_config": self.frame_cfg}, f, indent=4)

    def calculate_line_bounds(self, screen_w, screen_h, w_scale, x_shift, y_shift):
        """Calculates a tightly cropped 10-pixel high bounding box for 1D analysis."""
        w_scale = max(1, w_scale)
        box_width = int(screen_w * (w_scale / 1000.0))
        left_offset = int(screen_w * (x_shift / 1000.0))
        top_offset = int(screen_h * (y_shift / 1000.0))
        box_height = 10 
        
        left_offset = max(0, min(left_offset, screen_w - box_width))
        top_offset = max(0, min(top_offset, screen_h - box_height))
        
        return {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}

    def is_game_active(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "wow" in buf.value.lower() or "world of warcraft" in buf.value.lower()

    def get_bar_percentage(self, sct, monitor, lower_color, upper_color):
        """Isolates the exact middle horizontal line to calculate the fill percentage."""
        sct_img = sct.grab(monitor)
        img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
        hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        mask = cv2.inRange(hsv_img, lower_color, upper_color)
        
        # 1D OPTIMIZATION: Slice out the exact middle row
        middle_row_idx = mask.shape[0] // 2 
        middle_line = mask[middle_row_idx, :]
        
        active_pixels = np.count_nonzero(middle_line)
        total_pixels = len(middle_line)
        
        if total_pixels == 0:
            return 0.0
            
        return (active_pixels / total_pixels) * 100.0

    def start(self):
        self.log(f"[{self.name}] Thread initialized. Monitoring player vitals.")
        self.is_running = True
        self.monitor_loop()

    def stop(self):
        self.is_running = False

    def monitor_loop(self):
        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            while self.is_running:
                try:
                    if not self.is_game_active():
                        time.sleep(1)
                        continue

                    h_monitor = self.calculate_line_bounds(screen_w, screen_h, self.frame_cfg["w_scale"], self.frame_cfg["x_shift"], self.frame_cfg["health_y"])
                    p_monitor = self.calculate_line_bounds(screen_w, screen_h, self.frame_cfg["w_scale"], self.frame_cfg["x_shift"], self.frame_cfg["power_y"])
                    t_monitor = self.calculate_line_bounds(screen_w, screen_h, self.frame_cfg["w_scale"], self.frame_cfg["x_shift"], self.frame_cfg["tertiary_y"])

                    self.health_pct = self.get_bar_percentage(sct, h_monitor, self.lower_health, self.upper_health)
                    self.power_pct = self.get_bar_percentage(sct, p_monitor, self.lower_power, self.upper_power)
                    self.tertiary_pct = self.get_bar_percentage(sct, t_monitor, self.lower_tertiary, self.upper_tertiary)
                    
                    time.sleep(0.1)

                except Exception as e:
                    self.log(f"[{self.name}] Error tracking state: {e}")
                    time.sleep(2)

    def run_vision_test(self):
        """2x Zoom 'Magnifying Glass' tool for pinpoint 1D line calibration."""
        self.log(f"[{self.name}] Launching Player Frame Magnifier...")
        
        cv2.namedWindow("Player Frame Calibration")
        
        # Camera Panning Controls
        cv2.createTrackbar("Camera X", "Player Frame Calibration", self.frame_cfg["cam_x"], 1000, lambda x: None)
        cv2.createTrackbar("Camera Y", "Player Frame Calibration", self.frame_cfg["cam_y"], 1000, lambda x: None)
        
        # Unified Controls
        cv2.createTrackbar("Bar Width", "Player Frame Calibration", self.frame_cfg["w_scale"], 1000, lambda x: None)
        cv2.createTrackbar("Bar X Pos", "Player Frame Calibration", self.frame_cfg["x_shift"], 1000, lambda x: None)
        
        # Discrete Y Controls
        cv2.createTrackbar("Health Y", "Player Frame Calibration", self.frame_cfg["health_y"], 1000, lambda x: None)
        cv2.createTrackbar("Power Y", "Player Frame Calibration", self.frame_cfg["power_y"], 1000, lambda x: None)
        cv2.createTrackbar("Tertiary Y", "Player Frame Calibration", self.frame_cfg["tertiary_y"], 1000, lambda x: None)

        with mss.mss() as sct:
            primary_monitor = sct.monitors[1]
            screen_w = primary_monitor["width"]
            screen_h = primary_monitor["height"]
            
            # The base capture size (will be scaled up by 2x)
            capture_w = 400
            capture_h = 300
            zoom = 2

            while True:
                live_cfg = {
                    "w_scale": cv2.getTrackbarPos("Bar Width", "Player Frame Calibration"),
                    "x_shift": cv2.getTrackbarPos("Bar X Pos", "Player Frame Calibration"),
                    "health_y": cv2.getTrackbarPos("Health Y", "Player Frame Calibration"),
                    "power_y": cv2.getTrackbarPos("Power Y", "Player Frame Calibration"),
                    "tertiary_y": cv2.getTrackbarPos("Tertiary Y", "Player Frame Calibration"),
                    "cam_x": cv2.getTrackbarPos("Camera X", "Player Frame Calibration"),
                    "cam_y": cv2.getTrackbarPos("Camera Y", "Player Frame Calibration")
                }

                # Calculate the Camera's absolute position on the monitor
                cam_left = int((screen_w - capture_w) * (live_cfg["cam_x"] / 1000.0))
                cam_top = int((screen_h - capture_h) * (live_cfg["cam_y"] / 1000.0))
                preview_monitor = {"top": cam_top, "left": cam_left, "width": capture_w, "height": capture_h}

                # Grab the image and apply 2x Nearest Neighbor Zoom (keeps edges perfectly crisp)
                sct_img = sct.grab(preview_monitor)
                img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                img_zoomed = cv2.resize(img_bgr, (capture_w * zoom, capture_h * zoom), interpolation=cv2.INTER_NEAREST)
                
                # --- HELPER TO DRAW LINES ON THE ZOOMED IMAGE ---
                def draw_zoomed_line(y_shift, color, text, pct, text_offset_y):
                    b = self.calculate_line_bounds(screen_w, screen_h, live_cfg["w_scale"], live_cfg["x_shift"], y_shift)
                    
                    # Absolute global coordinates of the line
                    global_y = b["top"] + 5
                    global_x1 = b["left"]
                    global_x2 = b["left"] + b["width"]

                    # Convert to local Camera coordinates, then multiply by zoom factor
                    local_y = int((global_y - cam_top) * zoom)
                    local_x1 = int((global_x1 - cam_left) * zoom)
                    local_x2 = int((global_x2 - cam_left) * zoom)

                    # Draw the tracking line
                    cv2.line(img_zoomed, (local_x1, local_y), (local_x2, local_y), color, 2)
                    
                    # Draw the UI Readout
                    cv2.putText(img_zoomed, f"{text}: {pct:.1f}%", (10, text_offset_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                # Fetch true percentages natively from the monitor
                h_b = self.calculate_line_bounds(screen_w, screen_h, live_cfg["w_scale"], live_cfg["x_shift"], live_cfg["health_y"])
                p_b = self.calculate_line_bounds(screen_w, screen_h, live_cfg["w_scale"], live_cfg["x_shift"], live_cfg["power_y"])
                t_b = self.calculate_line_bounds(screen_w, screen_h, live_cfg["w_scale"], live_cfg["x_shift"], live_cfg["tertiary_y"])
                
                h_pct = self.get_bar_percentage(sct, h_b, self.lower_health, self.upper_health)
                p_pct = self.get_bar_percentage(sct, p_b, self.lower_power, self.upper_power)
                t_pct = self.get_bar_percentage(sct, t_b, self.lower_tertiary, self.upper_tertiary)

                # Render Lines and Data onto the zoomed image
                draw_zoomed_line(live_cfg["health_y"], (0, 255, 0), "Health", h_pct, (capture_h * zoom) - 75)
                draw_zoomed_line(live_cfg["power_y"], (255, 255, 0), "Power", p_pct, (capture_h * zoom) - 50)
                draw_zoomed_line(live_cfg["tertiary_y"], (0, 255, 255), "Tertiary", t_pct, (capture_h * zoom) - 25)

                cv2.putText(img_zoomed, "Press 'S' to Save | 'X' to Close", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                # Display the 800x600 window (guarantees sliders fit)
                cv2.imshow("Player Frame Calibration", img_zoomed)
                
                key = cv2.waitKey(25) & 0xFF
                if key == ord('x'):
                    self.log(f"[{self.name}] Calibration closed.")
                    break
                elif key == ord('s'):
                    self.save_config(live_cfg)
                    self.log(f"[{self.name}] SUCCESS: Player Frame dimensions saved!")
                    break

        cv2.destroyAllWindows()