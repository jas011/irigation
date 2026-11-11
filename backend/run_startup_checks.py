import sys
import asyncio
import os
import importlib.util

BASE = os.path.dirname(__file__)

# Load external_status module by file to avoid package import path issues
spec = importlib.util.spec_from_file_location("external_status", os.path.join(BASE, "app", "services", "external_status.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

if __name__ == "__main__":
    try:
        result = asyncio.run(mod.run_startup_checks())
        print("Startup checks completed.")
        print(result)
    except Exception as e:
        print(f"Startup checks error: {e}")