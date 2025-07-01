import os
import requests
import json
from dotenv import load_dotenv
import urllib3

# Disable SSL warnings (use with caution in production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_connectivity():
    """Tests connectivity to InfoBlox and checks the network view."""
    if not os.path.exists('config.env'):
        print("ERROR: config.env file not found. Please create it.")
        return

    load_dotenv('config.env')

    grid_master = os.getenv('GRID_MASTER')
    username = os.getenv('INFOBLOX_USERNAME')
    password = os.getenv('PASSWORD')
    network_view_name = os.getenv('NETWORK_VIEW')
    api_version = os.getenv('API_VERSION', 'v2.13.1') # Default if not in config.env

    print("--- Configuration from config.env ---")
    print(f"Grid Master: {grid_master}")
    print(f"Username: {username}")
    print(f"Password: {'***' if password else '(not set)'}")
    print(f"Network View: {network_view_name}")
    print(f"API Version: {api_version}")
    print("-------------------------------------\n")

    if not all([grid_master, username, password, network_view_name]):
        print("ERROR: Missing one or more required configurations in config.env:")
        print("- GRID_MASTER")
        print("- INFOBLOX_USERNAME")
        print("- PASSWORD")
        print("- NETWORK_VIEW")
        return

    base_url = f"https://{grid_master}/wapi/{api_version}"
    session = requests.Session()
    session.auth = (username, password)
    session.verify = False  # Disabling SSL verification as in the main script

    # Test 1: Basic connection - try to get a list of network views (limited to 1)
    # This helps confirm authentication without relying on a specific network view name yet.
    test_auth_url = f"{base_url}/networkview?_max_results=1"
    print(f"Attempting basic authentication test: GET {test_auth_url}")
    try:
        response_auth = session.get(test_auth_url)
        print(f"Auth Test Response Status: {response_auth.status_code}")
        if response_auth.status_code == 200:
            print("SUCCESS: Basic authentication successful.")
        else:
            print(f"FAILURE: Basic authentication failed. Status: {response_auth.status_code}")
            try:
                print(f"Response Content: {response_auth.json()}")
            except json.JSONDecodeError:
                print(f"Response Content (raw): {response_auth.text}")
            # Do not proceed if basic auth fails
            return

    except requests.exceptions.RequestException as e:
        print(f"FAILURE: Could not connect to InfoBlox Grid Master at {grid_master}.")
        print(f"Error: {e}")
        return
    
    print("-" * 30)

    # Test 2: Check the specific network view from config.env
    network_view_url = f"{base_url}/networkview?name={network_view_name}"
    print(f"Attempting to fetch Network View '{network_view_name}': GET {network_view_url}")

    try:
        response_nv = session.get(network_view_url)
        print(f"Network View Check Response Status: {response_nv.status_code}")

        if response_nv.status_code == 200:
            nv_data = response_nv.json()
            if nv_data and isinstance(nv_data, list) and len(nv_data) > 0:
                print(f"SUCCESS: Network View '{network_view_name}' found and accessible.")
                print(f"Details: {json.dumps(nv_data[0], indent=2)}")
            else:
                # This case should ideally not happen if status is 200 and view exists
                print(f"WARNING: Network View '{network_view_name}' query returned 200 OK, but no data or empty list.")
                print(f"Response Content: {nv_data}")
        elif response_nv.status_code == 401:
            print(f"FAILURE: Authentication failed for Network View check (Status 401).")
            print("Please check INFOBLOX_USERNAME and PASSWORD in config.env.")
            try:
                print(f"Response Content: {response_nv.json()}")
            except json.JSONDecodeError:
                print(f"Response Content (raw): {response_nv.text}")
        elif response_nv.status_code == 404:
            print(f"FAILURE: Network View '{network_view_name}' not found (Status 404).")
            print("Please verify the NETWORK_VIEW name in config.env and on the InfoBlox server (it's case-sensitive).")
            try:
                print(f"Response Content: {response_nv.json()}")
            except json.JSONDecodeError:
                print(f"Response Content (raw): {response_nv.text}")
        else:
            print(f"FAILURE: Could not retrieve Network View '{network_view_name}'. Status: {response_nv.status_code}")
            try:
                print(f"Response Content: {response_nv.json()}")
            except json.JSONDecodeError:
                print(f"Response Content (raw): {response_nv.text}")

    except requests.exceptions.RequestException as e:
        print(f"FAILURE: Error during request for Network View '{network_view_name}'.")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_connectivity()
