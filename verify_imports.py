import sys
import os
sys.path.append(os.getcwd())

try:
    print("Importing app.app...")
    import app.app
    print(f"SUCCESS: app.app imported. App instance: {app.app.app}")
except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
