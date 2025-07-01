#!/usr/bin/env python3
"""
Immediate terminal test with timestamped output
"""
import datetime
import os
import sys

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"terminal_test_{timestamp}.txt"

print(f"Creating test file: {filename}")

with open(filename, 'w') as f:
    f.write(f"Terminal Test Results\n")
    f.write(f"Timestamp: {datetime.datetime.now()}\n")
    f.write(f"Python: {sys.version}\n")
    f.write(f"Working Dir: {os.getcwd()}\n")
    f.write(f"File created successfully\n")

print(f"Test complete! Check for file: {filename}")
print(f"File exists: {os.path.exists(filename)}")
