#!/usr/bin/env python3
"""
Comprehensive VS Code Terminal Integration Test
"""
import os
import sys
import subprocess
import json
from datetime import datetime

def test_terminal_features():
    """Test various terminal integration features"""
    results = {
        "test_time": str(datetime.now()),
        "tests": {}
    }
    
    # Test 1: Basic system info
    results["tests"]["system_info"] = {
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "platform": sys.platform,
        "executable": sys.executable
    }
    
    # Test 2: Command execution
    try:
        # List directory contents
        dir_result = subprocess.run(['dir'], shell=True, capture_output=True, text=True)
        results["tests"]["directory_listing"] = {
            "success": dir_result.returncode == 0,
            "files_count": len(dir_result.stdout.splitlines())
        }
    except Exception as e:
        results["tests"]["directory_listing"] = {"error": str(e)}
    
    # Test 3: Python package check
    try:
        import pandas
        import requests
        results["tests"]["packages"] = {
            "pandas": pandas.__version__,
            "requests": requests.__version__
        }
    except ImportError as e:
        results["tests"]["packages"] = {"error": f"Some packages not installed: {e}"}
    
    # Test 4: File operations
    test_file = "terminal_test_temp.txt"
    try:
        with open(test_file, 'w') as f:
            f.write("Terminal test successful!")
        results["tests"]["file_operations"] = {
            "write": "success",
            "file_exists": os.path.exists(test_file)
        }
        os.remove(test_file)  # Clean up
    except Exception as e:
        results["tests"]["file_operations"] = {"error": str(e)}
    
    # Test 5: Environment variables
    important_vars = ['PATH', 'PYTHONPATH', 'GRID_MASTER', 'INFOBLOX_USERNAME']
    env_results = {}
    for var in important_vars:
        value = os.environ.get(var, 'Not Set')
        if var == 'PATH':
            # Just show if PATH exists and has content
            env_results[var] = 'Set' if value != 'Not Set' else 'Not Set'
        else:
            env_results[var] = value
    results["tests"]["environment_variables"] = env_results
    
    return results

# Run tests
print("=" * 60)
print("VS Code Terminal Integration Test")
print("=" * 60)

results = test_terminal_features()

# Display results
for test_name, test_result in results["tests"].items():
    print(f"\n{test_name.upper().replace('_', ' ')}:")
    if isinstance(test_result, dict):
        for key, value in test_result.items():
            print(f"  {key}: {value}")
    else:
        print(f"  {test_result}")

# Save detailed results
with open('terminal_test_detailed.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 60)
print("Test completed! Detailed results saved to terminal_test_detailed.json")
