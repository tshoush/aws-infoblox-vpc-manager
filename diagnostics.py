#!/usr/bin/env python3
"""
InfoBlox Network View Diagnostics Script

This script helps troubleshoot network connectivity and view contents
to understand why networks might not be found in a specific view.
"""

import requests
import urllib3
import json
from dotenv import load_dotenv
import os
import getpass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_config():
    """Load configuration from environment or prompt user"""
    load_dotenv('config.env')
    
    grid_master = os.getenv('GRID_MASTER')
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')
    
    # Prompt for missing values
    if not grid_master:
        grid_master = input("Enter InfoBlox Grid Master IP/hostname: ").strip()
    
    if not username:
        username = input(f"Enter InfoBlox username (default: admin): ").strip() or 'admin'
    
    if not password:
        password = getpass.getpass("Enter InfoBlox password: ")
    
    return grid_master, username, password

def test_network_view_contents(grid_master, username, password, network_view):
    """Test what's actually in the network view"""
    
    session = requests.Session()
    session.auth = (username, password)
    session.verify = False
    
    print(f"\n🔍 Analyzing Network View: {network_view}")
    print("=" * 60)
    
    # 1. Test if we can get all networks in the view
    try:
        url = f"https://{grid_master}/wapi/v2.13.1/network"
        params = {
            'network_view': network_view,
            '_return_fields': 'network,comment,extattrs'
        }
        
        print(f"🔍 Querying all networks in view '{network_view}'...")
        response = session.get(url, params=params)
        
        if response.status_code == 200:
            networks = response.json()
            print(f"✅ Found {len(networks)} networks in view '{network_view}'")
            
            if networks:
                print("\n📋 Networks in this view:")
                for i, net in enumerate(networks[:10]):  # Show first 10
                    print(f"  {i+1}. {net.get('network', 'Unknown')}")
                    if net.get('comment'):
                        print(f"      Comment: {net['comment']}")
                
                if len(networks) > 10:
                    print(f"      ... and {len(networks) - 10} more networks")
            else:
                print("⚠️  No networks found in this view")
                
        else:
            print(f"❌ Error querying networks: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception querying networks: {e}")
    
    # 2. Test a specific network lookup (using one from our VPC data)
    test_networks = [
        "10.212.224.0/23",  # First VPC from the data
        "10.216.140.0/23",  # Second VPC from the data
    ]
    
    print(f"\n🔍 Testing specific network lookups...")
    for test_network in test_networks:
        try:
            url = f"https://{grid_master}/wapi/v2.13.1/network"
            params = {
                'network': test_network,
                'network_view': network_view,
                '_return_fields': 'network,comment,extattrs'
            }
            
            print(f"   Searching for: {test_network}")
            response = session.get(url, params=params)
            
            if response.status_code == 200:
                networks = response.json()
                if networks:
                    print(f"   ✅ Found: {networks[0].get('network')}")
                else:
                    print(f"   🔍 Not found (empty result - this is normal if network doesn't exist)")
            elif response.status_code == 400:
                print(f"   ⚠️  400 Bad Request - this suggests an API query issue")
                print(f"   Response: {response.text}")
            else:
                print(f"   ❌ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

def test_network_views(grid_master, username, password):
    """Test and display all available network views"""
    
    session = requests.Session()
    session.auth = (username, password)
    session.verify = False
    
    print(f"\n🔍 Available Network Views:")
    print("=" * 40)
    
    try:
        url = f"https://{grid_master}/wapi/v2.13.1/networkview"
        response = session.get(url)
        
        if response.status_code == 200:
            views = response.json()
            print(f"✅ Found {len(views)} network views:")
            
            for i, view in enumerate(views):
                view_name = view.get('name', 'Unknown')
                print(f"  {i+1}. {view_name}")
                
                # Test network count in this view
                try:
                    net_url = f"https://{grid_master}/wapi/v2.13.1/network"
                    net_params = {'network_view': view_name, '_return_fields': 'network'}
                    net_response = session.get(net_url, params=net_params)
                    
                    if net_response.status_code == 200:
                        network_count = len(net_response.json())
                        print(f"      Networks: {network_count}")
                    else:
                        print(f"      Networks: Error {net_response.status_code}")
                        
                except Exception as e:
                    print(f"      Networks: Error - {e}")
                    
        else:
            print(f"❌ Error getting views: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception getting views: {e}")

def suggest_solutions():
    """Provide suggestions based on common issues"""
    
    print(f"\n💡 Troubleshooting Suggestions:")
    print("=" * 40)
    print("1. **Empty Network View**: If the view has no networks, you'll need to:")
    print("   - Create the networks first, or")
    print("   - Use a different network view that contains your networks")
    print("")
    print("2. **400 Bad Request Errors**: This usually means:")
    print("   - The network view exists but the specific network doesn't")
    print("   - This is actually normal - it means 'network not found'")
    print("   - Our script should handle this better")
    print("")
    print("3. **Recommended Next Steps**:")
    print("   a) Try using the 'default' network view first")
    print("   b) If you need to use 'TarigFriday', create the networks first")
    print("   c) Use --create-missing to add the VPC networks to InfoBlox")

def main():
    """Main diagnostic function"""
    print("InfoBlox Network View Diagnostics")
    print("=" * 50)
    
    # Get configuration
    grid_master, username, password = get_config()
    
    print(f"🔗 Connecting to InfoBlox Grid Master: {grid_master}")
    
    # Test network views
    test_network_views(grid_master, username, password)
    
    # Ask which view to analyze
    network_view = input(f"\nEnter network view to analyze (default: TarigFriday): ").strip() or "TarigFriday"
    
    # Test the specific view
    test_network_view_contents(grid_master, username, password, network_view)
    
    # Provide suggestions
    suggest_solutions()
    
    print(f"\n🎯 Summary:")
    print("The 400 errors you're seeing are likely because the VPC networks")
    print("don't exist in the 'TarigFriday' network view yet.")
    print("This is normal - the script should create them with --create-missing")

if __name__ == "__main__":
    main()
