import time

class FishingBot:
    def __init__(self, log_callback):
        self.is_running = False
        self.name = "Fishingbuddy"
        self.log = log_callback 

    def start(self):
        self.log(f"[{self.name}] Initializing...")
        self.is_running = True
        self.log(f"[{self.name}] Starting automation sequence...")
        self.fishing_loop()
        return True

    def stop(self):
        self.is_running = False
        self.log(f"[{self.name}] Stop command received. Halting after current action...")

    def fishing_loop(self):
        """Milestone 3: The core automation loop."""
        while self.is_running:
            self.log(f"[{self.name}] Casting line...")
            time.sleep(3) 
            
            if not self.is_running: break 
                
            self.log(f"[{self.name}] Waiting for bobber splash...")
            time.sleep(4)
            
            if not self.is_running: break
                
            self.log(f"[{self.name}] Looting fish!")
            time.sleep(2)