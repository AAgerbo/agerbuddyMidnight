import tkinter as tk

class BotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Automation Bot - v0.1")
        self.root.geometry("400x300")  # Sets the window size to 400x300 pixels

        # 1. Add a simple text label
        self.label = tk.Label(root, text="Bot Control Panel Status: Idle", font=("Arial", 14))
        self.label.pack(pady=30)

        # 2. Add an explicit "Shutdown" button
        self.exit_button = tk.Button(root, text="Shutdown Bot", command=self.on_closing)
        self.exit_button.pack(side=tk.BOTTOM, pady=20)

        # 3. Handle the standard window close button (the 'X' in the top right corner)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """This function ensures a clean shutdown of the application."""
        print("Initiating clean shutdown sequence...")
        # Future Session: This is where we will write code to stop background bot tasks safely!
        
        print("Closing window and terminating process. Goodbye!")
        self.root.destroy() # Destroys the window and stops the mainloop

if __name__ == "__main__":
    # Initialize the main Tkinter window
    root = tk.Tk()
    
    # Pass the window into our BotApp class
    app = BotApp(root)
    
    # Start the Event Loop
    root.mainloop()