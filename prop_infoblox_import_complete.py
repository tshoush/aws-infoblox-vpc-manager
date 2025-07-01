#!/usr/bin/env python3
"""
Properties File to InfoBlox Network Import Tool

Based on AWS InfoBlox VPC Manager logic, adapted for importing
networks from modified_properties_file.csv format.

Features:
1. Interactive configuration display & editing
2. Priority-based network creation (larger networks first)
3. Configurable container detection
4. Enhanced Extended Attributes reporting
5. CSV file environment configuration
6. Interactive network view selection
7. Dry run mode support

Author: Adapted from AWS-InfoBlox Integration
Date: June 5, 2025
"""

import pandas as pd
import requests
import json
import urllib3
import ast
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
import os
from dotenv import load_dotenv
import getpass
import sys

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


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Properties File to InfoBlox Network Import Tool',
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


class InfoBloxClient:
    """InfoBlox WAPI client for network management"""
    
    def __init__(self, grid_master: str, username: str, password: str, api_version: str = "v2.13.1"):
        self.grid_master = grid_master
        self.username = username
        self.password = password
        self.api_version = api_version
        self.base_url = f"https://{grid_master}/wapi/{api_version}"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False
        self._ea_cache = {}
        
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> requests.Response:
        """Make HTTP request to InfoBlox WAPI"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, params=params)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, params=params)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            error_msg = f"InfoBlox API request failed: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    if 'text' in error_details:
                        error_msg += f" - Details: {error_details['text']}"
                    elif 'Error' in error_details:
                        error_msg += f" - Details: {error_details['Error']}"
                except:
                    error_msg += f" - Response: {e.response.text}"
            logger.error(error_msg)
            raise
    
    def get_network_views(self) -> List[Dict]:
        """Get all network views from InfoBlox"""
        try:
            response = self._make_request('GET', 'networkview')
            views = response.json()
            return views
        except Exception as e:
            logger.error(f"Error fetching network views: {e}")
            return []
    
    def get_csv_files(self) -> List[str]:
        """Get list of CSV files in current directory"""
        try:
            csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
            return sorted(csv_files)
        except Exception as e:
            logger.error(f"Error listing CSV files: {e}")
            return []
    
    def get_network_by_cidr(self, cidr: str, network_view: str = "default") -> Optional[Dict]:
        """Get specific network by CIDR block"""
        params = {
            'network': cidr,
            'network_view': network_view,
            '_return_fields': 'network,comment,extattrs'
        }
        
        try:
            response = self._make_request('GET', 'network', params=params)
            networks = response.json()
            if networks:
                logger.debug(f"Found network {cidr} in view {network_view}")
                return networks[0]
            else:
                logger.debug(f"Network {cidr} not found in view {network_view}")
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 or e.response.status_code == 404:
                logger.debug(f"Network {cidr} not found in view {network_view} (HTTP {e.response.status_code})")
                return None
            else:
                logger.error(f"Error checking network {cidr}: HTTP {e.response.status_code}")
                raise
    
    def get_network_container_by_cidr(self, cidr: str, network_view: str = "default") -> Optional[Dict]:
        """Get specific network container by CIDR block"""
        params = {
            'network': cidr,
            'network_view': network_view,
            '_return_fields': 'network,comment,extattrs'
        }
        
        try:
            response = self._make_request('GET', 'networkcontainer', params=params)
            containers = response.json()
            if containers:
                logger.debug(f"Found network container {cidr} in view {network_view}")
                return containers[0]
            else:
                logger.debug(f"Network container {cidr} not found in view {network_view}")
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 or e.response.status_code == 404:
                logger.debug(f"Network container {cidr} not found in view {network_view} (HTTP {e.response.status_code})")
                return None
            else:
                logger.error(f"Error checking network container {cidr}: HTTP {e.response.status_code}")
                raise
    
    def check_network_or_container_exists(self, cidr: str, network_view: str = "default") -> Dict:
        """Check if CIDR exists as either a network or network container"""
        # First check if it exists as a regular network
        network = self.get_network_by_cidr(cidr, network_view)
        if network:
            return {
                'exists': True,
                'type': 'network',
                'object': network
            }
        
        # Then check if it exists as a network container
        container = self.get_network_container_by_cidr(cidr, network_view)
        if container:
            return {
                'exists': True,
                'type': 'container',
                'object': container
            }
        
        return {
            'exists': False,
            'type': None,
            'object': None
        }
    
    def create_network(self, cidr: str, network_view: str = "default", 
                      comment: str = "", extattrs: Optional[Dict[str, str]] = None) -> Dict:
        """Create a new network in InfoBlox"""
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
        logger.debug(f"Creating network with data: {json.dumps(data, indent=2)}")
        
        try:
            response = self._make_request('POST', 'network', data=data)
            logger.info(f"Created network {cidr} in view {network_view}")
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
            logger.error(f"Failed to create network {cidr}: {error_msg}")
            logger.debug(f"Request data was: {json.dumps(data, indent=2)}")
            
            # Re-raise with more specific error message
            raise Exception(f"{error_msg}")
    
    def get_extensible_attributes(self) -> List[Dict]:
        """Get all Extended Attribute definitions from InfoBlox"""
        if 'definitions' not in self._ea_cache:
            response = self._make_request('GET', 'extensibleattributedef')
            self._ea_cache['definitions'] = response.json()
        return self._ea_cache['definitions']
    
    def create_extensible_attribute(self, name: str, data_type: str = "STRING", 
                                  comment: str = "", default_value: str = "") -> Dict:
        """Create a new Extended Attribute definition in InfoBlox"""
        data = {
            'name': name,
            'type': data_type,
            'comment': comment
        }
        
        if default_value:
            data['default_value'] = default_value
        
        try:
            response = self._make_request('POST', 'extensibleattributedef', data=data)
            logger.info(f"Created Extended Attribute definition: {name}")
            if 'definitions' in self._ea_cache:
                del self._ea_cache['definitions']
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                error_details = e.response.text
                if "already exists" in error_details.lower():
                    logger.info(f"Extended Attribute {name} already exists")
                    return {'status': 'exists', 'name': name}
            raise
    
    def ensure_required_eas_exist(self, required_eas: List[str]) -> Dict[str, str]:
        """Ensure required Extended Attributes exist in InfoBlox, create if missing"""
        existing_eas = self.get_extensible_attributes()
        existing_names = {ea['name'] for ea in existing_eas}
        
        results = {}
        
        for ea_name in required_eas:
            if ea_name not in existing_names:
                logger.info(f"Creating missing Extended Attribute: {ea_name}")
                result = self.create_extensible_attribute(
                    name=ea_name,
                    data_type="STRING",
                    comment=f"Property file mapping for {ea_name}",
                    default_value=""
                )
                results[ea_name] = 'created'
            else:
                results[ea_name] = 'exists'
        
        return results
    
    def update_network_extattrs(self, network_ref: str, extattrs: Dict[str, str]) -> Dict:
        """Update Extended Attributes for an existing network"""
        # Format extattrs for InfoBlox API
        formatted_extattrs = {k: {'value': v} for k, v in extattrs.items()}
        
        data = {
            'extattrs': formatted_extattrs
        }
        
        # Use the network reference to update
        response = self._make_request('PUT', network_ref, data=data)
        logger.info(f"Updated Extended Attributes for network {network_ref}")
        return response.json()


class PropertyManager:
    """Main class for managing Property file to InfoBlox synchronization"""
    
    def __init__(self, infoblox_client: InfoBloxClient):
        self.ib_client = infoblox_client
        
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
            # Parse the prefixes string which contains a list
            prefixes_str = row['prefixes']
            try:
                if isinstance(prefixes_str, str):
                    # Use ast.literal_eval to safely parse the string list
                    prefixes_list = ast.literal_eval(prefixes_str)
                else:
                    prefixes_list = [prefixes_str] if prefixes_str else []
                    
                # Create a row for each prefix
                for prefix in prefixes_list:
                    new_row = row.copy()
                    new_row['cidr'] = prefix
                    expanded_rows.append(new_row)
                    
            except Exception as e:
                logger.warning(f"Error parsing prefixes for site_id {row['site_id']}: {e}")
                continue
        
        # Create new dataframe with expanded rows
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
                        'm_host':
