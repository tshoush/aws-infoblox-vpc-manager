#!/usr/bin/env python3
"""Test the improved network view selection"""

import os
import sys
from dotenv import load_dotenv

# Import the updated module
from aws_infoblox_vpc_manager_complete import show_and_edit_config, InfoBloxClient

def test_network_view_fetch():
    """Test if we can fetch network views"""
    load_dotenv('config.env')
    
    grid_master = os.getenv('GRID_MASTER', '')
    username = os.getenv('INFOBLOX_USERNAME', '')
    password = os.getenv('PASSWORD', '')
    
    if not all([grid_master, username, password]):
        print("❌ Missing InfoBlox credentials in config.env")
        return
    
    try:
        print(f"🔗 Connecting to InfoBlox at {grid_master}...")
        ib_client = InfoBloxClient(grid_master, username, password)
        
        print("📋 Fetching network views...")
        views = ib_client.get_network_views()
        
        if views:
            print(f"\n✅ Found {len(views)} network views:")
            for i, view in enumerate(views, 1):
                view_name = view.get('name', 'Unknown')
                print(f"   {i}. {view_name}")
        else:
            print("❌ No network views found")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Testing Network View Selection Enhancement")
    print("=" * 50)
    
    # Test fetching network views
    test_network_view_fetch()
    
    print("\n" + "=" * 50)
    print("To test the interactive selection, run:")
    print("python aws_infoblox_vpc_manager_complete.py")
