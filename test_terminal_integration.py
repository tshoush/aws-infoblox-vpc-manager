#!/usr/bin/env python3
"""
Test script for VS Code terminal integration
"""
import os
import sys
import platform
import datetime

# Write test results to a file
with open('terminal_test_results.txt', 'w') as f:
    f.write("VS Code Terminal Integration Test Results\n")
    f.write("=" * 50 + "\n")
    f.write(f"Test Date: {datetime.datetime.now()}\n")
    f.write(f"Python Version: {sys.version}\n")
    f.write(f"Platform: {platform.platform()}\n")
    f.write(f"Current Directory: {os.getcwd()}\n")
    f.write(f"Shell Environment: {os.environ.get('SHELL', 'Not Set')}\n")
    f.write(f"COMSPEC: {os.environ.get('COMSPEC', 'Not Set')}\n")
    f.write("\nEnvironment Variables:\n")
    for key, value in sorted(os.environ.items())[:10]:  # First 10 env vars
        f.write(f"  {key}: {value}\n")

print("Terminal integration test completed!")
print(f"Results written to: {os.path.abspath('terminal_test_results.txt')}")
