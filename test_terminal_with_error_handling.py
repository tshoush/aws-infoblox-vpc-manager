#!/usr/bin/env python3
"""
Terminal test with explicit error handling
"""
import os
import sys
import datetime
import traceback

try:
    print("Starting terminal test...")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    
    # Create a unique filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"python_terminal_test_{timestamp}.txt"
    
    print(f"\nAttempting to create file: {filename}")
    
    # Write the file
    with open(filename, 'w') as f:
        f.write(f"Python Terminal Test Success!\n")
        f.write(f"Timestamp: {datetime.datetime.now()}\n")
        f.write(f"Python Version: {sys.version}\n")
        f.write(f"Working Directory: {os.getcwd()}\n")
    
    # Verify file exists
    if os.path.exists(filename):
        print(f"✓ File created successfully: {filename}")
        print(f"  File size: {os.path.getsize(filename)} bytes")
    else:
        print(f"✗ File was not created!")
        
except Exception as e:
    print(f"\nERROR occurred: {type(e).__name__}: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    
print("\nTest complete.")
