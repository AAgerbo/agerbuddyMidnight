import cv2
import numpy as np
import mss
import ctypes

def run_actionbar_test():
    print("Initializing Action Bar Vision Test...")
    print("Press 'x' while the video window is selected to stop.")
    print("-" * 40)

    VK_Q = 0x51
    lower_cyan = np.array([85, 150, 150])
    upper_cyan = np.array([105, 255, 255])

    with mss.mss() as sct:
        primary_monitor = sct.monitors[1]
        screen_width = primary_monitor["width"]
        screen_height = primary_monitor["height"]
        
        # The exact same math from our CombatBot
        # --- UPDATED: Half-size dimensions ---
        box_width = screen_width // 6       
        box_height = screen_height // 20    
            
        # --- UPDATED: Absolute bottom alignment ---
        left_offset = (screen_width - box_width) // 2
        top_offset = screen_height - box_height
        
        monitor = {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}
        slot_width = box_width // 7

        while True:
            # 1. Grab the screenshot
            sct_img = sct.grab(monitor)
            img_bgr = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
            hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            
            # 2. Draw the 7 virtual slots as green lines so we can see the grid
            for i in range(1, 7):
                x_line = i * slot_width
                cv2.line(img_bgr, (x_line, 0), (x_line, box_height), (0, 255, 0), 1)

            # 3. Create the Cyan Mask
            mask = cv2.inRange(hsv_img, lower_cyan, upper_cyan)
            
            # 4. Check for detections
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest_contour) > 100:
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    
                    # Draw a red box around the detected glow!
                    cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    
                    # Calculate and display which slot it thinks it is in
                    center_x = x + (w // 2)
                    active_slot = (center_x // slot_width) + 1
                    cv2.putText(img_bgr, f"Target: Slot {active_slot}", (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # 5. Live test the 'Q' Key hardware state
            q_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_Q) & 0x8000
            q_text = "Q is PRESSED (Bot would fire!)" if q_pressed else "Q is Released"
            q_color = (0, 255, 0) if q_pressed else (0, 0, 255)
            cv2.putText(img_bgr, q_text, (10, box_height - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, q_color, 2)

            # 6. Show the windows
            cv2.imshow("Action Bar View", img_bgr)
            cv2.imshow("Cyan Mask", mask)
            
            # Press 'x' to quit (since 'q' is our test key)
            if cv2.waitKey(25) & 0xFF == ord('x'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        run_actionbar_test()
    except KeyboardInterrupt:
        cv2.destroyAllWindows()