import soundcard as sc
import numpy as np
import traceback

def run_calibration():
    print("Initializing Audio Loopback...")
    
    # 1. Identify your default speaker
    speaker = sc.default_speaker()
    print(f"Targeting speaker: {speaker.name}")
    
    # 2. Ask Windows for the "Loopback Microphone" attached to that speaker
    mic = sc.get_microphone(speaker.id, include_loopback=True)
    print(f"Successfully hooked loopback: {mic.name}")
    
    print("-" * 40)
    print("Waiting for loud sounds... (Press Ctrl+C to stop)")
    print("-" * 40)
    
    # 3. Record using the loopback microphone
    with mic.recorder(samplerate=44100) as recorder:
        while True:
            # Capture a tiny fraction of a second of audio
            data = recorder.record(numframes=1024)
            
            # Safety check to ensure we actually received audio data
            if data is not None and len(data) > 0:
                # Calculate the maximum volume in this tiny chunk
                volume = np.max(np.abs(data))
                
                # Print the volume if it's higher than ambient noise
                if volume > 0.05:
                    print(f"Volume Spike: {volume:.4f}")

if __name__ == "__main__":
    try:
        run_calibration()
    except KeyboardInterrupt:
        print("\nCalibration stopped safely by user.")
    except Exception as e:
        print("\n" + "!"*40)
        print("CRITICAL ERROR ENCOUNTERED:")
        print("!"*40)
        traceback.print_exc() 
    finally:
        # Forces the window to stay open
        input("\nPress ENTER to close this window...")