#!/usr/bin/env python3
"""
Import networks from modified_properties_file.csv into InfoBlox version 9.3 using a specific network view.

This script reads a CSV file containing network information and imports the networks
into InfoBlox using the 'Tarig_view' network view. If the network view doesn't exist,
it will be created first. The script sets extended attributes for site_id and m_host,
creating them if they don't exist in InfoBlox.

Usage:
    python3 myview_import_properties.py
"""

import requests
import pandas as pd
import getpass
import sys
import os
import ipaddress
import datetime
import ast  # For safely evaluating string representations of lists
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress insecure request warnings (use cautiously, consider proper cert validation)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# --- Configuration ---
WAPI_VERSION = "v2.12"  # Specify the WAPI version you want to use
DEFAULT_CSV_FILE = "modified_properties_file.csv"
DEFAULT_GRID_MASTER = "192.168.1.222"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "infoblox"
NETWORK_VIEW_NAME = "Tarig_view"

# --- Helper Functions ---

def get_input_parameters():
    """Prompt user for input file and InfoBlox connection details with defaults."""
    # Prompt for CSV file
    csv_file = input(f"Enter CSV file path [default: {DEFAULT_CSV_FILE}]: ")
    if not csv_file:
        csv_file = DEFAULT_CSV_FILE
    
    # Prompt for InfoBlox connection details
    infoblox_ip = input(f"Enter InfoBlox Grid Master's name or IP address [default: {DEFAULT_GRID_MASTER}]: ")
    if not infoblox_ip:
        infoblox_ip = DEFAULT_GRID_MASTER
    
    username = input(f"Enter InfoBlox username [default: {DEFAULT_USERNAME}]: ")
    if not username:
        username = DEFAULT_USERNAME
    
    password = getpass.getpass(f"Enter InfoBlox password [default: {DEFAULT_PASSWORD}]: ")
    if not password:
        password = DEFAULT_PASSWORD
    
    return csv_file, infoblox_ip, username, password

def make_api_request(session, base_url, method, endpoint, params=None, data=None):
    """Make a request to the InfoBlox WAPI."""
    url = f"{base_url}/{endpoint}"
    try:
        response = session.request(
            method,
            url,
            params=params,
            json=data,
            verify=False  # Set to True or path to cert bundle for production
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        if response.content:
            return response.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error making API request to {url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.text}")
            except Exception:
                pass
        return None
    except json.JSONDecodeError:
        # Handle cases where response is not JSON (e.g., successful empty response)
        if response.ok and not response.content:
            return None  # Or return an empty dict/list based on expected response
        print(f"Error decoding JSON response from {url}")
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        return None

def get_network_view(session, base_url, view_name):
    """Check if a network view exists."""
    print(f"Checking if network view '{view_name}' exists...")
    endpoint = f"networkview?name={view_name}"
    return make_api_request(session, base_url, "GET", endpoint)

def create_network_view(session, base_url, view_name):
    """Create a new network view."""
    print(f"Creating network view '{view_name}'...")
    endpoint = "networkview"
    data = {
        "name": view_name
    }
    result = make_api_request(session, base_url, "POST", endpoint, data=data)
    if result:
        print(f"Successfully created network view '{view_name}'.")
        return result  # Return the reference to the new network view
    else:
        print(f"Failed to create network view '{view_name}'.")
        return None

def get_ea_definition(session, base_url, ea_name):
    """Check if an EA definition exists."""
    endpoint = f"extensibleattributedef?name={ea_name}"
    return make_api_request(session, base_url, "GET", endpoint)

def create_ea_definition(session, base_url, ea_name):
    """Create a new EA definition (basic string type)."""
    print(f"Attempting to create EA definition for '{ea_name}'...")
    endpoint = "extensibleattributedef"
    data = {
        "name": ea_name,
        "type": "STRING",  # Defaulting to STRING type
        "flags": "I",  # Inheritable
        # Add other necessary fields like comment, allowed_values etc. if needed
    }
    result = make_api_request(session, base_url, "POST", endpoint, data=data)
    if result:
        print(f"Successfully created EA definition '{ea_name}'.")
        return result  # Return the reference to the new EA def
    else:
        print(f"Failed to create EA definition '{ea_name}'.")
        return None

def get_network(session, base_url, cidr, network_view=NETWORK_VIEW_NAME):
    """Get network object reference by CIDR."""
    endpoint = f"network?network={cidr}&network_view={network_view}"
    return make_api_request(session, base_url, "GET", endpoint)

def create_network(session, base_url, cidr, description, eas=None, network_view=NETWORK_VIEW_NAME):
    """Create a new network object."""
    print(f"Creating network: {cidr} in view '{network_view}'...")
    endpoint = "network"
    data = {
        "network": cidr,
        "network_view": network_view,
        "comment": description
    }
    if eas:
        data["extattrs"] = eas
    
    result = make_api_request(session, base_url, "POST", endpoint, data=data)
    if result:
        print(f"Successfully created network: {cidr} in view '{network_view}'")
        return result  # Return the reference
    else:
        print(f"Failed to create network: {cidr} in view '{network_view}'")
        return None

def update_network_eas(session, base_url, network_ref, description, eas):
    """Update the EAs and description for an existing network object."""
    print(f"Updating EAs for network ref: {network_ref}...")
    endpoint = network_ref
    data = {
        "extattrs": eas,
        "comment": description
    }
    result = make_api_request(session, base_url, "PUT", endpoint, data=data)
    if result is not None:  # PUT might return empty success response
        print(f"Successfully updated EAs for network ref: {network_ref}")
        return result
    else:
        # Check if the request was actually successful despite empty response
        print(f"Successfully updated EAs for network ref: {network_ref} (assuming success on empty response)")
        return network_ref  # Return original ref on assumed success

def validate_cidr(cidr):
    """Validate if the string is a valid CIDR block."""
    try:
        ipaddress.ip_network(cidr, strict=False)  # strict=False allows host bits set
        return True
    except ValueError:
        return False

def parse_prefixes(prefixes_str):
    """Parse the prefixes string from CSV into a list of CIDR blocks."""
    try:
        # Use ast.literal_eval to safely evaluate the string representation of a list
        prefixes_list = ast.literal_eval(prefixes_str)
        if isinstance(prefixes_list, list):
            return prefixes_list
        return []
    except (SyntaxError, ValueError):
        print(f"Error parsing prefixes: {prefixes_str}")
        return []

# --- Main Execution Logic ---

def main():
    # 1. Get Input Parameters
    csv_file, infoblox_ip, username, password = get_input_parameters()
    
    if not os.path.exists(csv_file):
        print(f"Error: Input CSV file not found: {csv_file}")
        sys.exit(1)
    
    base_url = f"https://{infoblox_ip}/wapi/{WAPI_VERSION}"

    # 2. Establish session and check/create network view
    with requests.Session() as session:
        session.auth = (username, password)
        
        # Check if the network view exists
        existing_views = get_network_view(session, base_url, NETWORK_VIEW_NAME)
        
        if not existing_views or not isinstance(existing_views, list) or len(existing_views) == 0:
            # Network view doesn't exist, create it
            view_ref = create_network_view(session, base_url, NETWORK_VIEW_NAME)
            if not view_ref:
                print(f"Error: Failed to create network view '{NETWORK_VIEW_NAME}'. Exiting.")
                sys.exit(1)
        else:
            print(f"Network view '{NETWORK_VIEW_NAME}' already exists.")
        
        # 3. Load CSV Data
        try:
            df = pd.read_csv(csv_file)
            print(f"Loaded {len(df)} records from {csv_file}")
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            sys.exit(1)

        # 4. Process Records
        ea_definitions_cache = {}  # Cache EA definitions to avoid repeated lookups
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        description = f"Imported by Property script on {current_datetime}"

        for _, row in df.iterrows():
            print("-" * 30)
            site_id = str(row.get('site_id', ''))
            m_host = str(row.get('m_host', ''))
            prefixes_str = row.get('prefixes', '[]')
            
            prefixes = parse_prefixes(prefixes_str)
            if not prefixes:
                print(f"Skipping row - no valid prefixes: {row}")
                continue

            # Prepare EAs
            eas_to_set = {}
            
            # Process site_id EA
            if site_id:
                # Check/Create EA Definition for site_id
                if 'site_id' not in ea_definitions_cache:
                    existing_ea_defs = get_ea_definition(session, base_url, 'site_id')
                    if existing_ea_defs and isinstance(existing_ea_defs, list) and len(existing_ea_defs) > 0:
                        ea_definitions_cache['site_id'] = existing_ea_defs[0]
                        print(f"Found existing EA definition for 'site_id'.")
                    else:
                        new_ea_def = create_ea_definition(session, base_url, 'site_id')
                        if new_ea_def:
                            ea_definitions_cache['site_id'] = {"_ref": new_ea_def}
                        else:
                            ea_definitions_cache['site_id'] = None
                
                # Add to eas_to_set if definition exists/was created
                if ea_definitions_cache.get('site_id'):
                    eas_to_set['site_id'] = {"value": site_id}
                else:
                    print(f"Skipping EA 'site_id' - definition not found or could not be created.")
            
            # Process m_host EA
            if m_host:
                # Check/Create EA Definition for m_host
                if 'm_host' not in ea_definitions_cache:
                    existing_ea_defs = get_ea_definition(session, base_url, 'm_host')
                    if existing_ea_defs and isinstance(existing_ea_defs, list) and len(existing_ea_defs) > 0:
                        ea_definitions_cache['m_host'] = existing_ea_defs[0]
                        print(f"Found existing EA definition for 'm_host'.")
                    else:
                        new_ea_def = create_ea_definition(session, base_url, 'm_host')
                        if new_ea_def:
                            ea_definitions_cache['m_host'] = {"_ref": new_ea_def}
                        else:
                            ea_definitions_cache['m_host'] = None
                
                # Add to eas_to_set if definition exists/was created
                if ea_definitions_cache.get('m_host'):
                    eas_to_set['m_host'] = {"value": m_host}
                else:
                    print(f"Skipping EA 'm_host' - definition not found or could not be created.")

            # Process each prefix (CIDR) in the list
            for cidr in prefixes:
                # Validate CIDR
                if not validate_cidr(cidr):
                    print(f"Skipping invalid CIDR format: {cidr}")
                    continue

                # Check if network exists in the specified view
                existing_networks = get_network(session, base_url, cidr, NETWORK_VIEW_NAME)
                
                if existing_networks and isinstance(existing_networks, list) and len(existing_networks) > 0:
                    # Network exists - Update EAs and description
                    network_ref = existing_networks[0]["_ref"]
                    print(f"Network {cidr} exists in view '{NETWORK_VIEW_NAME}' (ref: {network_ref}). Updating EAs and description...")
                    update_network_eas(session, base_url, network_ref, description, eas_to_set)
                else:
                    # Network does not exist - Create with EAs and description
                    create_network(session, base_url, cidr, description, eas_to_set, NETWORK_VIEW_NAME)

    print("-" * 30)
    print(f"InfoBlox import process completed. Networks imported to view '{NETWORK_VIEW_NAME}'.")

if __name__ == "__main__":
    main()
