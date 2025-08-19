#Launches front-end and back-end. Ensure correct working directory 

import subprocess
import time
import os
import sys
import webbrowser

def start():
    # Start backend
    print("Starting FastAPI backend...")    
    backend = subprocess.Popen(
        ["uvicorn", "main:app"]
    )

    # Wait a little to let backend start
    time.sleep(2)

    # Start frontend
    # Start frontend
    print("Starting React frontend...")
    frontend_path = os.path.join(os.getcwd(), "dashboard")
    frontend = subprocess.Popen(
        "npm run dev",
        cwd=frontend_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
    )

    # Open browser tab
    webbrowser.open("http://localhost:5173")

    print("Both frontend and backend are running.")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\n Stopping processes...")
        backend.terminate()
        frontend.terminate()

if __name__ == "__main__":
    start()
