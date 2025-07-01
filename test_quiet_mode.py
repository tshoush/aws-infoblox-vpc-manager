#!/usr/bin/env python3
"""Test script to demonstrate quiet vs interactive modes"""

import subprocess
import sys

def test_modes():
    """Test different modes of the script"""
    
    print("AWS InfoBlox VPC Manager - Mode Testing")
    print("=" * 50)
    
    print("\n1. Testing QUIET mode (default):")
    print("   Command: python aws_infoblox_vpc_manager_complete.py")
    print("   This should run without any configuration prompts")
    print("   (reads all settings from config.env)")
    
    print("\n2. Testing INTERACTIVE mode:")
    print("   Command: python aws_infoblox_vpc_manager_complete.py -i")
    print("   This should show the configuration menu")
    
    print("\n3. Testing with arguments in quiet mode:")
    print("   Command: python aws_infoblox_vpc_manager_complete.py --dry-run")
    print("   This should run in quiet mode with dry-run enabled")
    
    print("\n4. Testing help:")
    print("   Command: python aws_infoblox_vpc_manager_complete.py --help")
    print("\n" + "=" * 50)
    
    # Show help
    try:
        result = subprocess.run(
            [sys.executable, "aws_infoblox_vpc_manager_complete.py", "--help"],
            capture_output=True,
            text=True
        )
        print("\nHELP OUTPUT:")
        print(result.stdout)
    except Exception as e:
        print(f"Error showing help: {e}")

if __name__ == "__main__":
    test_modes()
