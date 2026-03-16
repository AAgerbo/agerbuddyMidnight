import cv2
import numpy as np
import mss

def run_vision_test():
    print("Initializing Splash Detection...")
    print("Looking for the red bobber. Press 'q' to stop.")
    
    with mss.mss() as sct:
        primary_monitor = sct.monitors[1]
        screen_width = primary_monitor["width"]
        screen_height = primary_monitor["height"]
        
        # Your dynamic box math
        box_width = screen_width // 6
        box_height = screen_height // 3
        left_offset = (screen_width - box_width) // 2
        top_offset = (screen_height - box_height) // 2
        top_offset -= screen_height // 5
        
        monitor = {"top": top_offset, "left": left_offset, "width": box_width, "height": box_height}

        while True:
            # 1. Grab the screenshot
            sct_img = sct.grab(monitor)
            
            # 2. OpenCV uses BGR (Blue-Green-Red). We drop the Alpha (transparency) channel.
            img = np.array(sct_img)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # 3. Convert to HSV (Hue, Saturation, Value) for accurate color tracking
            hsv_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            
            # 4. Define the color range for the Red bobber feather
            # (Note: In OpenCV, Hue for Red is around 0-10)
            lower_red = np.array([0, 120, 70])
            upper_red = np.array([10, 255, 255])
            
            # 5. Create the Mask: Red becomes White, everything else is Black
            mask = cv2.inRange(hsv_img, lower_red, upper_red)
            
            # 6. Count the visible white (bobber) pixels
            red_pixel_count = cv2.countNonZero(mask)
            
            # Draw the count on the normal image for us to read
            cv2.putText(img_bgr, f"Red Pixels: {red_pixel_count}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Show TWO windows: The normal view, and the Bot's "Mask" view
            cv2.imshow("Normal Vision", img_bgr)
            cv2.imshow("Bot Color Mask", mask)
            
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        run_vision_test()
    except KeyboardInterrupt:
        print("\nVision test stopped safely by user.")
        cv2.destroyAllWindows()