Below, you will find the official Markdown documentation you can save as a `README.md` in your `CombatBot` folder, followed by the finalized, fully-commented `combat_bot.py` script complete with standard PEP 257 docstrings.

---

### **CombatBot: Official Documentation**

#### **Overview**
CombatBot is a Computer Vision-based, reactive DPS assistant designed for World of Warcraft. It acts as a digital eye, scanning the player's action bar for the game's native "Assisted Highlight" (or a custom addon color). When the activation key is held, it maps the highlighted UI element to one of 12 customizable virtual slots and executes the corresponding keystroke with mathematically randomized, human-like delays to bypass heuristic anti-cheat analysis.

#### **Prerequisites & Setup**
1. **Required Libraries:** Ensure your Python environment has the required dependencies installed:
   ```bash
   pip install mss opencv-python numpy pydirectinput
   ```
2. **Directory Structure:** This module must be placed inside the dynamic bot router directory to be picked up by the Master GUI:
   `agerbuddyMidnight/bots/CombatBot/combat_bot.py`
3. **In-Game Addons:** If utilizing the custom hex color feature instead of the default cyan glow, the WoW addon **ActionBarsEnhanced** (or similar) is required to forcefully change the game's highlight border color.

#### **Usage Guide**
1. **Selecting the Bot:** Launch the main Master GUI (`bot_gui.py`) and select "CombatBot" from the dropdown menu.
2. **Configuration:** Click **Settings & Tools** to open the Combat Matrix popup.
   * **Activation Key:** Select the physical hardware key you wish to hold down to engage the bot.
   * **Highlight Hex Color:** Input the specific Hex color of your UI's highlight border (Default: `#00FFFF`).
   * **Action Bar Keybinds:** Map the 12 virtual screen slots to your specific game keybinds. Set empty or passive slots to `Unbound` so the bot ignores them.
3. **Vision Calibration (Crucial):**
   * Click **Vision Test** in the settings menu.
   * Go into the game and observe the calibration overlay.
   * Adjust the Width, Height, X Shift, and Y Shift sliders until the green grid perfectly encapsulates your 12 action bar buttons.
   * Press **'S'** while focused on the calibration window to permanently save these dimensions to your `config.json`.
4. **Execution:** Click **Start** on the Master GUI. Enter combat in-game and hold your selected Activation Key to initiate the firing sequence.