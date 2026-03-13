import os
import sys
import ctypes

torch_lib_path = r"C:\Users\karibiya\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\torch\lib"
os.add_dll_directory(torch_lib_path)

files = ["c10.dll", "torch_cpu.dll"]

for f in files:
    full_path = os.path.join(torch_lib_path, f)
    print(f"Attempting to load {f}...")
    try:
        ctypes.CDLL(full_path)
        print(f"SUCCESS: {f} loaded.")
    except Exception as e:
        print(f"FAILED: {f}. Error: {e}")
