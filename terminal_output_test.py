#!/usr/bin/env python3
"""
Simple terminal output test that writes results to a file
"""
import sys
import os
import datetime

output = []
output.append("=== Terminal Output Test ===")
output.append(f"Test Time: {datetime.datetime.now()}")
output.append(f"Python Version: {sys.version}")
output.append(f"Working Directory: {os.getcwd()}")
output.append(f"Script Location: {os.path.abspath(__file__)}")
output.append("Terminal integration is working!")

# Write to file
with open('terminal_output_test_results.txt', 'w') as f:
    for line in output:
        f.write(line + '\n')
        print(line)

print("\nResults saved to: terminal_output_test_results.txt")
