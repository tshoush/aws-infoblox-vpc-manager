#!/usr/bin/env python3
"""
Properties File to InfoBlox Network Import Tool - Enhanced with Overlap Detection

Enhanced version that detects overlapping networks and automatically
creates network containers for larger networks when overlaps are found.

Features:
1. All original features preserved
2. Automatic overlap detection between networks
3. Container creation for larger overlapping networks
4. Hierarchical network creation (containers -> networks)
5. Detailed dry-run reporting of overlap actions

Author: Enhanced from original prop_infoblox_import.py
Date: June 5, 2025
"""

import pandas as pd
import requests
import json
import urllib3
import ast
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import argparse
import os
from dotenv import load_dotenv
import getpass
import sys
import ipaddress

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Using an absolute path for the log file
ABS_LOG_FILE_PATH = os.path.abspath('prop_infoblox_import.log')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ABS_LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_network_overlap(cidr1: str, cidr2: str) -> str:
    """
    Check if two networks overlap.
    Returns: 'contains' if cidr1 contains cidr2
             'contained' if cidr1 is contained by cidr2
             'overlap' if they partially overlap
             'none' if no overlap
    """
    try:
        net1 = ipaddress.ip_network(cidr1, strict=False)
        net2 = ipaddress.ip_network(cidr2, strict=False)
        
        # Check if one contains the other
        if net1.supernet_of(net2):
            return 'contains'
        elif net1.subnet_of(net2):
            return 'contained'
        elif net1.overlaps(net2):
            return 'overlap'
        else:
            return 'none'
    except Exception as e:
        logger.error(f"Error checking overlap between {cidr1} and {cidr2}: {e}")
        return 'error'


def analyze_network_overlaps(networks: List[Dict]) -> Dict:
    """
    Analyze all networks for overlaps and determine which should be containers.
    Returns a dict with:
    - containers: set of CIDRs that should be containers
    - relationships: dict mapping container CIDR to list of contained networks
    - overlaps: list of overlapping network pairs that can't be hierarchical
    """
    result = {
        'containers': set(),
        'relationships': {},
        'overlaps': []
    }
    
    # Sort networks by prefix length (smaller number = larger network)
    sorted_networks = sorted(networks, key=lambda x: int(x['cidr'].split('/')[1]))
    
    # Check each pair of networks
    for i, net1 in enumerate(sorted_networks):
        cidr1 = net1['cidr']
        
        for j, net2 in enumerate(sorted_networks[i+1:], i+1):
            cidr2 = net2['cidr']
            
            overlap_type = check_network_overlap(cidr1, cidr2)
            
            if overlap_type == 'contains':
                # net1 contains net2 - net1 should be a container
                result['containers'].add(cidr1)
                if cidr1 not in result['relationships']:
                    result['relationships'][cidr1] = []
                result['relationships'][cidr1].append(net2)
                logger.info(f"Network {cidr1} contains {cidr2} - marking as container")
                
            elif overlap_type == 'overlap':
                # Partial overlap - this is problematic
                result['overlaps'].append({
                    'network1': net1,
                    'network2': net2,
                    'message': f"Networks {cidr1} and {cidr2} partially overlap"
                })
                logger.warning(f"Partial overlap detected between {cidr1} and {cidr2}")
    
    return result


# Copy all the necessary functions from the original file
def select_from_list(items: List[str], prompt: str, allow_custom: bool = False) -> str:
    """Present a numbered list and let user select by number"""
    if not items:
        if allow_custom:
            return input(f"{prompt} (no options available, enter manually): ").strip()
        else:
            raise ValueError("No items available to select from")
    
    print(f"\n{prompt}")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item}")
    
    if allow_custom:
        print(f"  {len(items) + 1}. Enter custom value")
    
    while True:
        try:
            choice = input(f"\nSelect option (1-{len(items) + (1 if allow_custom else 0)}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(items):
                return items[choice_num - 1]
            elif allow_custom and choice_num == len(items) + 1:
                return input("Enter custom value: ").strip()
            else:
                print(f"Invalid choice. Please select 1-{len(items) + (1 if allow_custom else 0)}")
        except ValueError:
            print("Please enter a number")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Properties File to InfoBlox Network Import Tool with Overlap Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comparison (quiet mode - uses config defaults)
  python %(prog)s
  
  # Interactive mode - configure settings interactively
  python %(prog)s -i
  python %(prog)s --interactive
  
  # Create missing networks (quiet mode)
  python %(prog)s --create-missing
  
  # Dry run mode with interactive config
  python %(prog)s -i --create-missing --dry-run
  
  # Specify CSV file
  python %(prog)s --csv-file custom_properties.csv
  
  # Specify network view
  python %(prog)s --network-view "Property Networks"
"""
    )
    
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Run in interactive mode to configure settings (default: quiet mode using config.env)'
    )
    
    parser.add_argument(
        '--create-missing',
        action='store_true',
        help='Create missing networks in InfoBlox'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate operations without making actual changes'
    )
    
    parser.add_argument(
        '--csv-file',
        default='modified_properties_file.csv',
        help='CSV file containing property data (default: modified_properties_file.csv)'
    )
    
    parser.add_argument(
        '--network-view',
        help='InfoBlox network view to use (overrides config)'
    )
    
    return parser.parse_args()


def show_and_edit_config():
    """Display current configuration and allow interactive editing"""
    load_dotenv('config.env')
    
    # Initialize configuration
    config = {
        'GRID_MASTER': os.getenv('GRID_MASTER', ''),
        'NETWORK_VIEW': os.getenv('NETWORK_VIEW', 'default'),
        'INFOBLOX_USERNAME': os.getenv('INFOBLOX_USERNAME', ''),
        'PASSWORD': os.getenv('PASSWORD', ''),
        'CSV_FILE': os.getenv('PROP_CSV_FILE', 'modified_properties_file.csv'),
        'PARENT_CONTAINER_PREFIXES': os.getenv('PARENT_CONTAINER_PREFIXES', ''),
        'CONTAINER_HIERARCHY_MODE': os.getenv('CONTAINER_HIERARCHY_MODE', 'strict')
    }
    
    # Initialize InfoBlox client for fetching network views if credentials are available
    ib_client = None
    if config['GRID_MASTER'] and config['INFOBLOX_USERNAME'] and config['PASSWORD']:
        try:
            ib_client = InfoBloxClient(config['GRID_MASTER'], config['INFOBLOX_USERNAME'], config['PASSWORD'])
        except Exception as e:
            logger.warning(f"Could not connect to InfoBlox for fetching network views: {e}")
    
    while True:
        print("\n" + "=" * 60)
        print("📋 CONFIGURATION SETTINGS")
        print("=" * 60)
        print("\nSelect the number to modify (or press Enter to continue):")
        print(f"\n  1. Network View [{config['NETWORK_VIEW']}]")
        print(f"  2. InfoBlox Grid Master [{config['GRID_MASTER'] or 'not set'}]")
        print(f"  3. Username [{config['INFOBLOX_USERNAME'] or 'not set'}]")
        print(f"  4. Password [{'***' if config['PASSWORD'] else 'not set'}]")
        print(f"  5. CSV File [{config['CSV_FILE']}]")
        print(f"  6. Container Prefixes [{config['PARENT_CONTAINER_PREFIXES'] or 'auto-detect'}]")
        print(f"  7. Container Mode [{config['CONTAINER_HIERARCHY_MODE']}]")
        print("\n  0. Continue with current settings")
        
        choice = input("\nYour choice (0-7): ").strip()
        
        if choice == '0' or choice == '':
            break
        elif choice == '1':
            # Network View selection with list
            if ib_client:
                try:
                    print("\nFetching available network views...")
                    views = ib_client.get_network_views()
                    if views:
                        view_names = [view.get('name', 'Unknown') for view in views]
                        print("\nAvailable Network Views:")
                        for i, view_name in enumerate(view_names, 1):
                            current_marker = " (current)" if view_name == config['NETWORK_VIEW'] else ""
                            print(f"  {i}. {view_name}{current_marker}")
                        print(f"  {len(view_names) + 1}. Enter custom value")
                        
                        view_choice = input(f"\nSelect network view (1-{len(view_names) + 1}) [{config['NETWORK_VIEW']}]: ").strip()
                        if view_choice.isdigit():
                            choice_num = int(view_choice)
                            if 1 <= choice_num <= len(view_names):
                                config['NETWORK_VIEW'] = view_names[choice_num - 1]
                                print(f"✓ Selected: {config['NETWORK_VIEW']}")
                            elif choice_num == len(view_names) + 1:
                                custom_view = input("Enter custom network view name: ").strip()
                                if custom_view:
                                    config['NETWORK_VIEW'] = custom_view
                    else:
                        print("No network views found. Please enter manually.")
                        new_value = input(f"Enter Network View [{config['NETWORK_VIEW']}]: ").strip()
                        if new_value:
                            config['NETWORK_VIEW'] = new_value
                except Exception as e:
                    print(f"Could not fetch network views: {e}")
                    new_value = input(f"Enter Network View [{config['NETWORK_VIEW']}]: ").strip()
                    if new_value:
                        config['NETWORK_VIEW'] = new_value
            else:
                print("\nInfoBlox connection not available. Please configure Grid Master, Username, and Password first.")
                new_value = input(f"Enter Network View [{config['NETWORK_VIEW']}]: ").strip()
                if new_value:
                    config['NETWORK_VIEW'] = new_value
                    
        elif choice == '2':
            new_value = input(f"Enter InfoBlox Grid Master IP/hostname [{config['GRID_MASTER']}]: ").strip()
            if new_value:
                config['GRID_MASTER'] = new_value
                # Try to reinitialize client with new grid master
                if config['INFOBLOX_USERNAME'] and config['PASSWORD']:
                    try:
                        ib_client = InfoBloxClient(config['GRID_MASTER'], config['INFOBLOX_USERNAME'], config['PASSWORD'])
                    except Exception as e:
                        logger.warning(f"Could not connect with new Grid Master: {e}")
                        
        elif choice == '3':
            new_value = input(f"Enter Username [{config['INFOBLOX_USERNAME']}]: ").strip()
            if new_value:
                config['INFOBLOX_USERNAME'] = new_value
                # Try to reinitialize client with new username
                if config['GRID_MASTER'] and config['PASSWORD']:
                    try:
                        ib_client = InfoBloxClient(config['GRID_MASTER'], config['INFOBLOX_USERNAME'], config['PASSWORD'])
                    except Exception as e:
                        logger.warning(f"Could not connect with new username: {e}")
                        
        elif choice == '4':
            new_value = getpass.getpass("Enter Password (press Enter to keep current): ")
            if new_value:
                config['PASSWORD'] = new_value
                # Try to reinitialize client with new password
                if config['GRID_MASTER'] and config['INFOBLOX_USERNAME']:
                    try:
                        ib_client = InfoBloxClient(config['GRID_MASTER'], config['INFOBLOX_USERNAME'], config['PASSWORD'])
                    except Exception as e:
                        logger.warning(f"Could not connect with new password: {e}")
                        
        elif choice == '5':
            # Show available CSV files
            csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
            if csv_files:
                print("\nAvailable CSV files:")
                for i, f in enumerate(csv_files, 1):
                    print(f"  {i}. {f}")
                csv_choice = input(f"Select CSV file number or enter custom path [{config['CSV_FILE']}]: ").strip()
                if csv_choice.isdigit() and 1 <= int(csv_choice) <= len(csv_files):
                    config['CSV_FILE'] = csv_files[int(csv_choice) - 1]
                elif csv_choice:
                    config['CSV_FILE'] = csv_choice
            else:
                new_value = input(f"Enter CSV file path [{config['CSV_FILE']}]: ").strip()
                if new_value:
                    config['CSV_FILE'] = new_value
                    
        elif choice == '6':
            print("\nContainer Prefixes (comma-separated, e.g., '16,17' for /16 and /17)")
            new_value = input(f"Enter prefixes [{config['PARENT_CONTAINER_PREFIXES'] or 'auto-detect'}]: ").strip()
            if new_value:
                config['PARENT_CONTAINER_PREFIXES'] = new_value
                
        elif choice == '7':
            print("\nContainer Mode options: 'strict' or 'flexible'")
            new_value = input(f"Enter mode [{config['CONTAINER_HIERARCHY_MODE']}]: ").strip()
            if new_value in ['strict', 'flexible']:
                config['CONTAINER_HIERARCHY_MODE'] = new_value
        else:
            print("Invalid choice. Please select 0-7.")
    
    # Save configuration if modified
    save_choice = input("\nSave these settings to config.env? (y/n) [n]: ").strip().lower()
    if save_choice == 'y':
        save_config_to_env(config)
        print("✅ Configuration saved to config.env")
    
    return config


def save_config_to_env(config: Dict[str, str]):
    """Save configuration to .env file"""
    lines = []
    
    # Read existing file to preserve comments and structure
    if os.path.exists('config.env'):
        with open('config.env', 'r') as f:
            for line in f:
                line = line.rstrip()
                if line.startswith('#') or not line:
                    lines.append(line)
                elif line.startswith('PROP_CSV_FILE='):
                    lines.append(f"PROP_CSV_FILE={config.get('CSV_FILE', 'modified_properties_file.csv')}")
                else:
                    # Parse key from line
                    if '=' in line:
                        key = line.split('=')[0].strip()
                        if key in config:
                            lines.append(f"{key}={config[key]}")
                        else:
                            lines.append(line)
        
        # Add PROP_CSV_FILE if it doesn't exist
        if not any('PROP_CSV_FILE=' in line for line in lines):
            lines.append(f"PROP_CSV_FILE={config.get('CSV_FILE', 'modified_properties_file.csv')}")
    else:
        # Create new file with all settings
        lines = [
            "# InfoBlox Configuration",
            f"GRID_MASTER={config.get('GRID_MASTER', '')}",
            f"NETWORK_VIEW={config.get('NETWORK_VIEW', 'default')}",
            f"INFOBLOX_USERNAME={config.get('INFOBLOX_USERNAME', '')}",
            f"PASSWORD={config.get('PASSWORD', '')}",
            "",
            "# CSV File Configuration",
            f"CSV_FILE={config.get('CSV_FILE', 'vpc_data.csv')}",
            f"PROP_CSV_FILE={config.get('CSV_FILE', 'modified_properties_file.csv')}",
            "",
            "# Container Detection Configuration",
            f"PARENT_CONTAINER_PREFIXES={config.get('PARENT_CONTAINER_PREFIXES', '')}",
            f"CONTAINER_HIERARCHY_MODE={config.get('CONTAINER_HIERARCHY_MODE', 'strict')}"
        ]
    
    # Write the file
    with open('config.env', 'w') as f:
        f.write('\n'.join(lines) + '\n')


def get_config(skip_network_view_prompt: bool = False, config_override: Optional[Dict] = None):
    """Get configuration from environment variables or config override"""
    if config_override is None:
        load_dotenv('config.env')
        config_override = {}
    
    # Get values from override or environment
    grid_master = config_override.get('GRID_MASTER') or os.getenv('GRID_MASTER', '')
    network_view = config_override.get('NETWORK_VIEW') or os.getenv('NETWORK_VIEW', 'default')
    username = config_override.get('INFOBLOX_USERNAME') or os.getenv('INFOBLOX_USERNAME', '')
    password = config_override.get('PASSWORD') or os.getenv('PASSWORD', '')
    csv_file = config_override.get('CSV_FILE') or os.getenv('PROP_CSV_FILE', 'modified_properties_file.csv')
    
    # Container configuration
    container_prefixes_str = config_override.get('PARENT_CONTAINER_PREFIXES') or os.getenv('PARENT_CONTAINER_PREFIXES', '')
    container_prefixes = [int(p.strip()) for p in container_prefixes_str.split(',') if p.strip()] if container_prefixes_str else []
    
    container_mode = config_override.get('CONTAINER_HIERARCHY_MODE') or os.getenv('CONTAINER_HIERARCHY_MODE', 'strict')
    
    # Validate required fields
    if not grid_master:
        raise ValueError("Grid Master not configured. Please run configuration setup.")
    if not username:
        raise ValueError("Username not configured. Please run configuration setup.")
    if not password:
        raise ValueError("Password not configured. Please run configuration setup.")
    
    return grid_master, network_view, username, password, csv_file, container_prefixes, container_mode


# Copy the InfoBloxClient class from the original file
from prop_infoblox_import import InfoBloxClient


# Enhanced PropertyManager with overlap detection
class PropertyManager:
    """Enhanced Property Manager with overlap detection and container creation"""
    
    def __init__(self, infoblox_client):
        self.ib_client = infoblox_client
        # Add the create_network_container method to the client
        self.ib_client.create_network_container = lambda *args, **kwargs: self._create_network_container(*args, **kwargs)
        
    def _create_network_container(self, cidr: str, network_view: str = "default", 
                                comment: str = "", extattrs: Optional[Dict[str, str]] = None) -> Dict:
        """Create a new network container in InfoBlox"""
        data = {
            'network': cidr,
            'network_view': network_view
        }
        
        if comment:
            data['comment'] = comment
            
        if extattrs:
            # Ensure all EA values are strings and not empty
            cleaned_extattrs = {}
            for k, v in extattrs.items():
                if v is not None and str(v).strip():
                    cleaned_extattrs[k] = str(v)
            if cleaned_extattrs:
                data['extattrs'] = {k: {'value': v} for k, v in cleaned_extattrs.items()}
        
        # Log the request data for debugging
        logger.debug(f"Creating network container with data: {json.dumps(data, indent=2)}")
        
        try:
            response = self.ib_client._make_request('POST', 'networkcontainer', data=data)
            logger.info(f"Created network container {cidr} in view {network_view}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Extract more detailed error information
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    if 'text' in error_details:
                        error_msg = error_details['text']
                    elif 'Error' in error_details:
                        error_msg = error_details['Error']
                except:
                    error_msg = e.response.text
            
            # Log full error details
            logger.error(f"Failed to create network container {cidr}: {error_msg}")
            logger.debug(f"Request data was: {json.dumps(data, indent=2)}")
            
            # Re-raise with more specific error message
            raise Exception(f"{error_msg}")
    
    def load_property_data(self, csv_file_path: str) -> pd.DataFrame:
        """Load property data from CSV file"""
        try:
            df = pd.read_csv(csv_file_path)
            logger.info(f"Loaded {len(df)} property records from {csv_file_path}")
            return df
        except Exception as e:
            logger.error(f"Error loading property data: {e}")
            raise
    
    def parse_prefixes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse prefixes column and expand rows for multiple prefixes"""
        df = df.copy()
        expanded_rows = []
        
        for _, row in df.iterrows():
            prefixes_str = row['prefixes']
            try:
                if isinstance(prefixes_str, str):
                    prefixes_list = ast.literal_eval(prefixes_str)
                else:
                    prefixes_list = [prefixes_str] if prefixes_str else []
                    
                for prefix in prefixes_list:
                    new_row = row.copy()
                    new_row['cidr'] = prefix
                    expanded_rows.append(new_row)
                    
            except Exception as e:
                logger.warning(f"Error parsing prefixes for site_id {row['site_id']}: {e}")
                continue
        
        expanded_df = pd.DataFrame(expanded_rows)
        logger.info(f"Expanded {len(df)} property records to {len(expanded_df)} network records")
        return expanded_df
    
    def map_properties_to_infoblox_eas(self, site_id: str, m_host: str) -> Dict[str, str]:
        """Map property fields to InfoBlox Extended Attributes"""
        mapped_eas = {
            'site_id': str(site_id),
            'm_host': str(m_host),
            'source': 'properties_file',
            'import_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return mapped_eas
    
    def compare_properties_with_infoblox(self, property_df: pd.DataFrame, network_view: str = "default") -> Dict:
        """Compare property networks with InfoBlox networks"""
        results = {
            'matches': [],
            'missing': [], 
            'discrepancies': [],
            'containers': [],
            'errors': []
        }
        
        for _, prop in property_df.iterrows():
            cidr = prop['cidr']
            site_id = prop['site_id']
            m_host = prop['m_host']
            
            try:
                mapped_eas = self.map_properties_to_infoblox_eas(site_id, m_host)
                
                # Check if network exists
                existence_check = self.ib_client.check_network_or_container_exists(cidr, network_view)
                
                if not existence_check['exists']:
                    logger.debug(f"Network {cidr} (site_id: {site_id}) not found in InfoBlox")
                    results['missing'].append({
                        'property': prop.to_dict(),
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'mapped_eas': mapped_eas
                    })
                elif existence_check['type'] == 'container':
                    logger.info(f"CIDR {cidr} (site_id: {site_id}) exists as network container in InfoBlox")
                    ib_container = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_container.get('extattrs', {}).items()}
                    
                    results['containers'].append({
                        'property': prop.to_dict(),
                        'cidr': cidr,
                        'ib_container': ib_container,
                        'site_id': site_id,
                        'm_host': m_host,
                        'ib_eas': ib_eas,
                        'mapped_eas': mapped_eas,
                        'note': 'Exists as network container - contains subnets'
                    })
                else:
                    # Network exists as regular network
                    logger.debug(f"Network {cidr} (site_id: {site_id}) found in InfoBlox")
                    ib_network = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_network.get('extattrs', {}).items()}
                    
                    # Compare EAs
                    ea_match = self._compare_eas(mapped_eas, ib_eas)
                    
                    if ea_match:
                        logger.debug(f"Network {cidr} (site_id: {site_id}) has matching EAs")
                        results['matches'].append({
                            'property': prop.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'site_id': site_id,
                            'm_host': m_host,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                    else:
                        logger.info(f"Network {cidr} (site_id: {site_id}) has EA discrepancies")
                        results['discrepancies'].append({
                            'property': prop.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'site_id': site_id,
                            'm_host': m_host,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                        
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing property site_id {site_id} ({cidr}): {error_msg}")
                
                # Try to provide more context about the error
                if "not found" in error_msg.lower() or "404" in error_msg:
                    logger.info(f"Network {cidr} (site_id: {site_id}) appears to not exist in InfoBlox")
                    results['missing'].append({
                        'property': prop.to_dict(),
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'mapped_eas': self.map_properties_to_infoblox_eas(site_id, m_host)
                    })
                else:
                    # Only true errors go here (network issues, parsing errors, etc.)
                    results['errors'].append({
                        'property': prop.to_dict(),
                        'cidr': cidr,
                        'error': error_msg
                    })
        
        return results
    
    def _compare_eas(self, mapped_eas: Dict[str, str], ib_eas: Dict[str, str]) -> bool:
        """Compare mapped property EAs with InfoBlox EAs - returns True only if they match exactly"""
        # Check all keys from both sides
        all_keys = set(mapped_eas.keys()) | set(ib_eas.keys())
        
        for key in all_keys:
            mapped_value = mapped_eas.get(key, None)
            ib_value = ib_eas.get(key, None)
            
            # If key exists in only one side, it's a discrepancy
            if mapped_value is None or ib_value is None:
                return False
            
            # If values don't match, it's a discrepancy
            if str(mapped_value) != str(ib_value):
                return False
        
        return True
    
    def ensure_required_eas(self, property_df: pd.DataFrame, dry_run: bool = False) -> Dict:
        """Ensure all required Extended Attributes exist in InfoBlox"""
        # The property file only needs these specific EAs
        required_eas = ['site_id', 'm_host', 'source', 'import_date']
        
        logger.info(f"Ensuring {len(required_eas)} Extended Attributes exist in InfoBlox")
        
        if dry_run:
            # In dry run, just check what would be created
            existing_eas = self.ib_client.get_extensible_attributes()
            existing_names = {ea['name'] for ea in existing_eas}
            missing_eas = [ea for ea in required_eas if ea not in existing_names]
            
            return {
                'missing_eas': missing_eas,
                'existing_count': len(set(required_eas) & existing_names)
            }
        
        # Actually create missing EAs
        created_eas = []
        existing_eas = self.ib_client.get_extensible_attributes()
        existing_names = {ea['name'] for ea in existing_eas}
        
        for ea_name in required_eas:
            if ea_name not in existing_names:
                logger.info(f"Creating Extended Attribute: {ea_name}")
                try:
                    self.ib_client.create_extensible_attribute(ea_name, 'STRING')
                    created_eas.append(ea_name)
                except Exception as e:
                    logger.error(f"Failed to create EA {ea_name}: {e}")
        
        return {
            'created_eas': created_eas,
            'existing_count': len(set(required_eas) & existing_names)
        }
    
    def create_missing_networks_with_overlap_check(self, missing_networks: List[Dict], 
                                                   network_view: str = "default", 
                                                   dry_run: bool = False) -> Dict:
        """Create missing networks with overlap detection and container creation"""
        results = {
            'created_networks': [],
            'created_containers': [],
            'failed': [],
            'skipped_due_to_overlap': []
        }
        
        # Analyze overlaps among missing networks
        overlap_analysis = analyze_network_overlaps(missing_networks)
        
        # Create containers first
        for container_cidr in overlap_analysis['containers']:
            container_info = next((n for n in missing_networks if n['cidr'] == container_cidr), None)
            if container_info:
                if dry_run:
                    logger.info(f"DRY RUN: Would create network container {container_cidr}")
                    results['created_containers'].append({
                        'cidr': container_cidr,
                        'site_id': container_info['site_id'],
                        'action': 'would_create_container'
                    })
                else:
                    try:
                        comment = f"Property site_id: {container_info['site_id']}, m_host: {container_info['m_host']}"
                        self.ib_client.create_network_container(
                            container_cidr,
                            network_view,
                            comment,
                            container_info['mapped_eas']
                        )
                        results['created_containers'].append({
                            'cidr': container_cidr,
                            'site_id': container_info['site_id'],
                            'action': 'created_container'
                        })
                        logger.info(f"Created network container {container_cidr}")
                    except Exception as e:
                        logger.error(f"Failed to create container {container_cidr}: {e}")
                        results['failed'].append({
                            'cidr': container_cidr,
                            'site_id': container_info['site_id'],
                            'error': str(e),
                            'type': 'container'
                        })
        
        # Create regular networks (skip those that were created as containers)
        for network in missing_networks:
            cidr = network['cidr']
            
            # Skip if this was created as a container
            if cidr in overlap_analysis['containers']:
                continue
            
            # Check for problematic overlaps
            has_problematic_overlap = False
            for overlap in overlap_analysis['overlaps']:
                if (network == overlap['network1'] or network == overlap['network2']):
                    has_problematic_overlap = True
                    logger.warning(f"Skipping {cidr} due to partial overlap: {overlap['message']}")
                    results['skipped_due_to_overlap'].append({
                        'cidr': cidr,
                        'site_id': network['site_id'],
                        'reason': overlap['message']
                    })
                    break
            
            if has_problematic_overlap:
                continue
            
            # Create the network
            if dry_run:
                logger.info(f"DRY RUN: Would create network {cidr} (site_id: {network['site_id']})")
                results['created_networks'].append({
                    'cidr': cidr,
                    'site_id': network['site_id'],
                    'action': 'would_create'
                })
            else:
                try:
                    comment = f"Property site_id: {network['site_id']}, m_host: {network['m_host']}"
                    self.ib_client.create_network(
                        cidr,
                        network_view,
                        comment,
                        network['mapped_eas']
                    )
                    results['created_networks'].append({
                        'cidr': cidr,
                        'site_id': network['site_id'],
                        'action': 'created'
                    })
                    logger.info(f"Created network {cidr}")
                except Exception as e:
                    logger.error(f"Failed to create network {cidr}: {e}")
                    results['failed'].append({
                        'cidr': cidr,
                        'site_id': network['site_id'],
                        'error': str(e),
                        'type': 'network'
                    })
        
        return results


def generate_report(results: Dict, dry_run: bool = False) -> str:
    """Generate a detailed report of the import operation"""
    report = []
    report.append("=" * 80)
    report.append("PROPERTY TO INFOBLOX NETWORK IMPORT REPORT - ENHANCED")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    report.append("")
    
    # Summary
    report.append("SUMMARY")
    report.append("-" * 40)
    report.append(f"Total Matching Networks: {len(results['matches'])}")
    report.append(f"Total Missing Networks: {len(results['missing'])}")
    report.append(f"Total Networks with EA Discrepancies: {len(results['discrepancies'])}")
    report.append(f"Total Networks Existing as Containers: {len(results['containers'])}")
    report.append(f"Total Errors: {len(results['errors'])}")
    report.append("")
    
    # Missing Networks Detail
    if results['missing']:
        report.append("MISSING NETWORKS (Not in InfoBlox)")
        report.append("-" * 40)
        for item in results['missing']:
            report.append(f"  CIDR: {item['cidr']}")
            report.append(f"    Site ID: {item['site_id']}")
            report.append(f"    M_Host: {item['m_host']}")
            report.append("")
    
    # Discrepancies Detail
    if results['discrepancies']:
        report.append("NETWORKS WITH EA DISCREPANCIES")
        report.append("-" * 40)
        for item in results['discrepancies']:
            report.append(f"  CIDR: {item['cidr']}")
            report.append(f"    Site ID: {item['site_id']}")
            report.append(f"    Property EAs: {item['mapped_eas']}")
            report.append(f"    InfoBlox EAs: {item['ib_eas']}")
            report.append("")
    
    # Network Containers
    if results['containers']:
        report.append("NETWORKS EXISTING AS CONTAINERS")
        report.append("-" * 40)
        for item in results['containers']:
            report.append(f"  CIDR: {item['cidr']} (Container)")
            report.append(f"    Site ID: {item['site_id']}")
            report.append(f"    Note: {item['note']}")
            report.append("")
    
    # Errors
    if results['errors']:
        report.append("ERRORS")
        report.append("-" * 40)
        for item in results['errors']:
            report.append(f"  CIDR: {item['cidr']}")
            report.append(f"    Error: {item['error']}")
            report.append("")
    
    return "\n".join(report)


def print_summary(comparison_results: Dict, creation_results: Optional[Dict] = None, 
                  dry_run: bool = False):
    """Print a summary of the operation"""
    print("\n" + "=" * 60)
    print("OPERATION SUMMARY")
    print("=" * 60)
    
    # Comparison Summary
    print("\nCOMPARISON RESULTS:")
    print(f"  ✅ Matching Networks: {len(comparison_results['matches'])}")
    print(f"  🔴 Missing Networks: {len(comparison_results['missing'])}")
    print(f"  🟡 Networks with EA Discrepancies: {len(comparison_results['discrepancies'])}")
    print(f"  📦 Networks Existing as Containers: {len(comparison_results['containers'])}")
    print(f"  ❌ Errors: {len(comparison_results['errors'])}")
    
    # Creation Summary (if applicable)
    if creation_results:
        print("\nCREATION RESULTS:")
        if dry_run:
            print(f"  🔵 Would Create Containers: {len(creation_results['created_containers'])}")
            print(f"  🔵 Would Create Networks: {len(creation_results['created_networks'])}")
        else:
            print(f"  ✅ Created Containers: {len(creation_results['created_containers'])}")
            print(f"  ✅ Created Networks: {len(creation_results['created_networks'])}")
        print(f"  ⚠️  Skipped (Overlaps): {len(creation_results['skipped_due_to_overlap'])}")
        print(f"  ❌ Failed: {len(creation_results['failed'])}")


def main():
    """Main function to orchestrate the property to InfoBlox import"""
    # Parse command line arguments
    args = parse_arguments()
    
    try:
        # Get configuration
        if args.interactive:
            logger.info("Running in interactive mode")
            config = show_and_edit_config()
            
            # Apply any command line overrides
            if args.csv_file != 'modified_properties_file.csv':
                config['CSV_FILE'] = args.csv_file
            if args.network_view:
                config['NETWORK_VIEW'] = args.network_view
                
            # Get configuration values from the config dict
            grid_master = config['GRID_MASTER']
            network_view = config['NETWORK_VIEW']
            username = config['INFOBLOX_USERNAME']
            password = config['PASSWORD']
            csv_file = config['CSV_FILE']
        else:
            # Quiet mode - use config from file with command line overrides
            logger.info("Running in quiet mode (using config.env)")
            grid_master, network_view, username, password, csv_file, _, _ = get_config()
            
            # Apply command line overrides
            if args.csv_file != 'modified_properties_file.csv':
                csv_file = args.csv_file
            if args.network_view:
                network_view = args.network_view
        
        # Print mode and configuration summary
        print("\n" + "=" * 60)
        print(f"MODE: {'DRY RUN' if args.dry_run else 'LIVE'}")
        print("=" * 60)
        print(f"Grid Master: {grid_master}")
        print(f"Network View: {network_view}")
        print(f"CSV File: {csv_file}")
        print(f"Username: {username}")
        print("=" * 60 + "\n")
        
        # Check if CSV file exists
        if not os.path.exists(csv_file):
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
        
        # Initialize InfoBlox client
        logger.info(f"Connecting to InfoBlox Grid Master: {grid_master}")
        ib_client = InfoBloxClient(grid_master, username, password)
        
        # Initialize Property Manager
        property_manager = PropertyManager(ib_client)
        
        # Load and parse property data
        logger.info(f"Loading property data from {csv_file}")
        property_df = property_manager.load_property_data(csv_file)
        
        # Parse prefixes
        logger.info("Parsing property prefixes")
        expanded_df = property_manager.parse_prefixes(property_df)
        
        if expanded_df.empty:
            logger.warning("No property networks found after parsing")
            print("\n⚠️  No property networks found in the CSV file")
            return
        
        # Ensure required EAs exist
        logger.info("Ensuring required Extended Attributes exist")
        ea_results = property_manager.ensure_required_eas(expanded_df, dry_run=args.dry_run)
        
        if args.dry_run and ea_results['missing_eas']:
            print(f"\n📋 Would create {len(ea_results['missing_eas'])} Extended Attributes:")
            for ea in ea_results['missing_eas']:
                print(f"   - {ea}")
        
        # Compare properties with InfoBlox
        logger.info("Comparing property networks with InfoBlox")
        comparison_results = property_manager.compare_properties_with_infoblox(
            expanded_df, network_view
        )
        
        # Generate and save report
        report_content = generate_report(comparison_results, args.dry_run)
        
        # Generate filename with mode indicator
        mode_suffix = "_dryrun" if args.dry_run else ""
        report_filename = f"property_network_status_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}{mode_suffix}.txt"
        report_path = os.path.join("reports", report_filename)
        
        # Ensure reports directory exists
        os.makedirs("reports", exist_ok=True)
        
        # Save report
        with open(report_path, 'w') as f:
            f.write(report_content)
        logger.info(f"Report saved to {report_path}")
        
        # Handle missing networks if requested
        creation_results = None
        if args.create_missing and comparison_results['missing']:
            print(f"\n{'DRY RUN: Would create' if args.dry_run else 'Creating'} {len(comparison_results['missing'])} missing networks...")
            
            creation_results = property_manager.create_missing_networks_with_overlap_check(
                comparison_results['missing'],
                network_view,
                args.dry_run
            )
            
            # Save creation report
            creation_report = []
            creation_report.append("\n" + "=" * 80)
            creation_report.append("NETWORK CREATION REPORT - ENHANCED WITH OVERLAP DETECTION")
            creation_report.append("=" * 80)
            
            if creation_results['created_containers']:
                creation_report.append(f"\n{'WOULD CREATE' if args.dry_run else 'CREATED'} CONTAINERS:")
                for container in creation_results['created_containers']:
                    creation_report.append(f"  - {container['cidr']} (site_id: {container['site_id']})")
            
            if creation_results['created_networks']:
                creation_report.append(f"\n{'WOULD CREATE' if args.dry_run else 'CREATED'} NETWORKS:")
                for network in creation_results['created_networks']:
                    creation_report.append(f"  - {network['cidr']} (site_id: {network['site_id']})")
            
            if creation_results['skipped_due_to_overlap']:
                creation_report.append("\nSKIPPED DUE TO OVERLAPS:")
                for skipped in creation_results['skipped_due_to_overlap']:
                    creation_report.append(f"  - {skipped['cidr']}: {skipped['reason']}")
            
            if creation_results['failed']:
                creation_report.append("\nFAILED:")
                for failed in creation_results['failed']:
                    creation_report.append(f"  - {failed['cidr']} ({failed['type']}): {failed['error']}")
            
            with open(report_path, 'a') as f:
                f.write("\n".join(creation_report))
        
        # Print summary
        print_summary(comparison_results, creation_results, args.dry_run)
        
        # Final message
        print(f"\n📄 Detailed report saved to: {report_path}")
        print(f"📝 Log file: {ABS_LOG_FILE_PATH}")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
