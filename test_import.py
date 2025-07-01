#!/usr/bin/env python3
import os
import subprocess
import sys

# Change to parent directory
os.chdir('/Users/tshoush/Desktop/Marriot')

# Run the import script
cmd = [
    sys.executable,
    'aws_infoblox_vpc_manager_complete.py',
    '--csv-file', 'vpc_data3.csv',
    '--network-view', 'default',
    '--dry-run'
]

print(f"Running from: {os.getcwd()}")
print(f"Config file exists: {os.path.exists('config.env')}")
print(f"Command: {' '.join(cmd)}")
print("-" * 50)

result = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")