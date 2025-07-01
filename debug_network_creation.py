#!/usr/bin/env python3
"""
Debug tool for InfoBlox network creation errors

This script helps diagnose why specific networks are failing to create in InfoBlox.
"""

import pandas as pd
import requests
import json
import urllib3
from dotenv import load_dotenv
import os
import sys

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_network_creation(cidr, network_view, grid_master, username, password):
    """Test creating a specific network with detailed error reporting"""
    
    print(f"\n{'='*60}")
    print(f"Testing network creation for: {cidr}")
    print(f"Network View: {network_view}")
    print(f"{'='*60}\n")
    
    base_url = f"https://{grid_master}/wapi/v2.13.1"
    session = requests.Session()
    session.auth = (username, password)
    session.verify = False
    
    # First, check if network already exists
    print("1. Checking if network already exists...")
    params = {
        'network': cidr,
        'network_view': network_view
    }
    
    try:
        response = session.get(f"{base_url}/network", params=params)
        if response.status_code == 200:
            networks = response.json()
            if networks:
                print(f"   ❌ Network already exists: {networks[0].get('_ref', 'Unknown ref')}")
                return
            else:
                print("   ✅ Network does not exist (can be created)")
        else:
            print(f"   ⚠️ Error checking network: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Check if it exists as a container
    print("\n2. Checking if network exists as container...")
    try:
        response = session.get(f"{base_url}/networkcontainer", params=params)
        if response.status_code == 200:
            containers = response.json()
            if containers:
                print(f"   ❌ Exists as network container: {containers[0].get('_ref', 'Unknown ref')}")
                return
            else:
                print("   ✅ Does not exist as container")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Check for parent networks
    print("\n3. Checking for parent networks that might cause overlap...")
    network_parts = cidr.split('/')
    network_ip = network_parts[0]
    prefix_len = int(network_parts[1])
    
    # Check broader prefixes
    for test_prefix in range(8, prefix_len):
        test_cidr = f"{network_ip}/{test_prefix}"
        params = {'network': test_cidr, 'network_view': network_view}
        
        try:
            response = session.get(f"{base_url}/network", params=params)
            if response.status_code == 200 and response.json():
                print(f"   ⚠️ Found parent network: {test_cidr}")
        except:
            pass
    
    # Try minimal network creation
    print("\n4. Testing minimal network creation (no EAs)...")
    data = {
        'network': cidr,
        'network_view': network_view
    }
    
    print(f"   Request data: {json.dumps(data, indent=2)}")
    
    try:
        response = session.post(f"{base_url}/network", json=data)
        print(f"   Response status: {response.status_code}")
        
        if response.status_code == 201:
            print("   ✅ Network created successfully!")
            print(f"   Reference: {response.json()}")
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"   Raw response: {response.text}")
                
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test with comment
    print("\n5. Testing with comment only...")
    data = {
        'network': cidr,
        'network_view': network_view,
        'comment': 'Test network creation'
    }
    
    try:
        response = session.post(f"{base_url}/network", json=data)
        if response.status_code == 201:
            print("   ✅ Works with comment")
        else:
            print(f"   ❌ Failed with comment: {response.status_code}")
    except:
        pass


def main():
    """Main function"""
    load_dotenv('config.env')
    
    # Get configuration
    grid_master = os.getenv('GRID_MASTER')
    username = os.getenv('INFOBLOX_USERNAME')
    password = os.getenv('PASSWORD')
    network_view = os.getenv('NETWORK_VIEW', 'default')
    
    if not all([grid_master, username, password]):
        print("❌ Missing configuration. Please check config.env")
        return 1
    
    # Test specific network or read from rejected CSV
    if len(sys.argv) > 1:
        # Test specific CIDR
        cidr = sys.argv[1]
        if len(sys.argv) > 2:
            network_view = sys.argv[2]
        
        test_network_creation(cidr, network_view, grid_master, username, password)
    else:
        # Look for most recent rejected networks CSV
        import glob
        csv_files = sorted(glob.glob('rejected_networks_*.csv'), reverse=True)
        
        if not csv_files:
            print("No rejected networks CSV found.")
            print("\nUsage:")
            print("  python debug_network_creation.py <CIDR> [network_view]")
            print("  python debug_network_creation.py  # to test from rejected CSV")
            return 1
        
        print(f"Reading from: {csv_files[0]}")
        df = pd.read_csv(csv_files[0])
        
        # Test first few rejected networks
        for idx, row in df.head(3).iterrows():
            cidr = row['CIDR']
            test_network_creation(cidr, network_view, grid_master, username, password)
            print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    sys.exit(main())
