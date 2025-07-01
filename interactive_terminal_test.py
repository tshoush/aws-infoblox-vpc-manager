#!/usr/bin/env python3
"""
Interactive terminal integration test with real-time output
"""
import os
import sys
import time
import subprocess
import platform

print("=== Interactive Terminal Integration Test ===")
print(f"Running on: {platform.system()} {platform.release()}")
print(f"Python: {sys.version.split()[0]}")
print()

# Test 1: Real-time output
print("Test 1: Real-time output demonstration")
for i in range(5):
    print(f"  Progress: {'█' * (i+1)}{'░' * (4-i)} {(i+1)*20}%", end='\r')
    time.sleep(0.5)
print("\n  ✓ Real-time output working!")
print()

# Test 2: Command execution
print("Test 2: Command execution")
try:
    if platform.system() == "Windows":
        result = subprocess.run(['echo', 'Hello from subprocess!'], 
                              capture_output=True, text=True, shell=True)
    else:
        result = subprocess.run(['echo', 'Hello from subprocess!'], 
                              capture_output=True, text=True)
    print(f"  Command output: {result.stdout.strip()}")
    print("  ✓ Subprocess execution working!")
except Exception as e:
    print(f"  ✗ Error: {e}")
print()

# Test 3: Directory operations
print("Test 3: Directory operations")
test_dir = "terminal_test_temp"
try:
    os.makedirs(test_dir, exist_ok=True)
    print(f"  Created directory: {test_dir}")
    
    # Create a test file
    test_file = os.path.join(test_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("Terminal test successful!")
    print(f"  Created file: {test_file}")
    
    # List directory contents
    contents = os.listdir(test_dir)
    print(f"  Directory contents: {contents}")
    
    # Clean up
    os.remove(test_file)
    os.rmdir(test_dir)
    print("  ✓ Directory operations working!")
except Exception as e:
    print(f"  ✗ Error: {e}")
print()

# Test 4: Environment variable access
print("Test 4: Environment variables")
important_vars = ['PATH', 'PYTHONPATH', 'VIRTUAL_ENV', 'COMSPEC', 'SHELL']
found_vars = 0
for var in important_vars:
    value = os.environ.get(var)
    if value:
        found_vars += 1
        print(f"  {var}: {value[:50]}{'...' if len(value) > 50 else ''}")
print(f"  ✓ Found {found_vars}/{len(important_vars)} environment variables!")
print()

# Test 5: System command output
print("Test 5: System command output")
try:
    if platform.system() == "Windows":
        cmd = "dir /b *.py | find /c \".py\""
        shell = True
    else:
        cmd = "ls -1 *.py | wc -l"
        shell = True
    
    result = subprocess.run(cmd, capture_output=True, text=True, shell=shell)
    py_count = result.stdout.strip()
    print(f"  Python files in current directory: {py_count}")
    print("  ✓ System commands working!")
except Exception as e:
    print(f"  ✗ Error: {e}")

print("\n=== All terminal integration tests complete! ===")
