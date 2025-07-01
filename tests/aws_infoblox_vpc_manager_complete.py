#!/usr/bin/env python3
"""
AWS to InfoBlox VPC Management Tool - Complete Enhanced Version

All features implemented:
1. Interactive configuration display & editing
2. Priority-based network creation (larger networks first)
3. Configurable container detection
4. Categorized rejected networks CSV generation
5. Enhanced Extended Attributes reporting
6. CSV file environment configuration
7. Interactive network view selection to avoid case sensitivity issues
8. Interactive CSV file selection

Author: Generated for AWS-InfoBlox Integration
Date: June 4, 2025
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
ABS_LOG_FILE_PATH = os.path.abspath('aws_infoblox_vpc_manager.log')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for better troubleshooting
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ABS_LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
        description='AWS to InfoBlox VPC Management Tool - Enhanced Version',
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
  python %(prog)s --csv-file vpc_data_custom.csv
  
  # Specify network view
  python %(prog)s --network-view "AWS Networks"
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
        default='vpc_data.csv',
        help='CSV file containing VPC data (default: vpc_data.csv)'
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
        'CSV_FILE': os.getenv('CSV_FILE', 'vpc_data.csv'),
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
                else:
                    # Parse key from line
                    if '=' in line:
                        key = line.split('=')[0].strip()
                        if key in config:
                            lines.append(f"{key}={config[key]}")
                        else:
                            lines.append(line)
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
    csv_file = config_override.get('CSV_FILE') or os.getenv('CSV_FILE', 'vpc_data.csv')
    
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


def main():
    """Main function with all enhanced features"""
    args = parse_arguments()
    
    try:
        config_override = None
        
        # Check if interactive mode is requested
        if args.interactive:
            # Show and optionally edit configuration
            config_override = show_and_edit_config()
        else:
            # Quiet mode - just load from config.env
            logger.info("Running in quiet mode. Use -i for interactive configuration.")
        
        # Get configuration (no prompting in quiet mode)
        grid_master, network_view, username, password, csv_file, container_prefixes, container_mode = get_config(
            config_override=config_override
        )
        
        # Override network view if specified on command line
        if args.network_view:
            network_view = args.network_view
            print(f"Using network view from command line: {network_view}")
            
        # Override CSV file if specified on command line
        if args.csv_file and args.csv_file != 'vpc_data.csv':
            csv_file = args.csv_file
            print(f"Using CSV file from command line: {csv_file}")
        
        # Show container configuration
        if container_prefixes:
            print(f"📦 Container prefixes configured: /{', /'.join(map(str, container_prefixes))}")
            print(f"🔧 Container mode: {container_mode}")
        else:
            print("📦 Container detection: Auto-detect from InfoBlox")
        
        logger.info(f"Loading VPC data from {csv_file}...")
        
        # Initialize InfoBlox client
        print(f"\n🔗 Connecting to InfoBlox Grid Master: {grid_master}")
        ib_client = InfoBloxClient(grid_master, username, password)
        
        # Initialize VPC Manager
        vpc_manager = VPCManager(ib_client)
        
        # Load and parse VPC data
        try:
            vpc_df = vpc_manager.load_vpc_data(csv_file)
            vpc_df = vpc_manager.parse_vpc_tags(vpc_df)
        except Exception as e:
            logger.error(f"Failed to load VPC data: {e}")
            return 1
        
        print(f"\n📊 ANALYSIS SUMMARY:")
        print(f"   📁 CSV file: {csv_file}")
        print(f"   🔢 Total VPCs loaded: {len(vpc_df)}")
        print(f"   🌐 Network view: {network_view}")
        
        # Compare with InfoBlox
        logger.info("Comparing AWS VPCs with InfoBlox networks...")
        comparison_results = vpc_manager.compare_vpc_with_infoblox(vpc_df, network_view)
        
        # Display results
        print(f"\n🔍 COMPARISON RESULTS:")
        print(f"   ✅ Fully synchronized (network + tags): {len(comparison_results['matches'])}")
        print(f"   🔴 Missing from InfoBlox: {len(comparison_results['missing'])}")
        print(f"   🟡 Networks with outdated tags: {len(comparison_results['discrepancies'])}")
        print(f"   📦 Network containers: {len(comparison_results['containers'])}")
        print(f"   ❌ Processing errors: {len(comparison_results['errors'])}")
        
        # Show update requirements summary
        if comparison_results['discrepancies']:
            print(f"\n🔧 UPDATE REQUIREMENTS:")
            print(f"   🏷️ Networks requiring EA updates: {len(comparison_results['discrepancies'])}")
            
            # Show sample of networks that need updates
            sample_discrepancies = comparison_results['discrepancies'][:3]
            for item in sample_discrepancies:
                vpc_name = item['vpc'].get('Name', 'Unnamed')
                cidr = item['cidr']
                print(f"   📄 {cidr} ({vpc_name}) - EAs need updating")
            
            if len(comparison_results['discrepancies']) > 3:
                print(f"   ... and {len(comparison_results['discrepancies']) - 3} more networks")
        
        # Show network containers summary
        if comparison_results.get('containers'):
            print(f"\n📦 NETWORK CONTAINERS FOUND:")
            print(f"   🔢 VPCs existing as containers: {len(comparison_results['containers'])}")
            print(f"   ℹ️ These exist as network containers (parent networks) in InfoBlox")
            print(f"   💡 Container networks typically contain smaller subnet networks")
            for container in comparison_results['containers'][:3]:
                print(f"   📦 {container['cidr']} - {container['vpc']['Name']}")
            if len(comparison_results['containers']) > 3:
                print(f"   ... and {len(comparison_results['containers']) - 3} more")
        
        # Analyze Extended Attributes (regardless of missing networks)
        if args.create_missing:
            print(f"\n🔍 EXTENDED ATTRIBUTES ANALYSIS:")
            ea_analysis = vpc_manager.ensure_required_eas(vpc_df, dry_run=args.dry_run)
            
            # Generate EA summary report
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ea_report_filename = os.path.join(reports_dir, f"extended_attributes_summary_{timestamp}.txt")
            
            eas_to_report = []
            report_ea_title = ""

            if args.dry_run:
                print(f"   🏷️ Extended Attributes analysis: {len(ea_analysis['missing_eas'])} missing")
                eas_to_report = ea_analysis.get('missing_eas', [])
                report_ea_title = "Missing Extended Attributes (would be created):"
            else:
                print(f"   🏷️ Extended Attributes: {ea_analysis['created_count']} created, {ea_analysis['existing_count']} existed")
                created_eas = [name for name, status in ea_analysis.get('ea_results', {}).items() if status == 'created']
                eas_to_report = created_eas
                report_ea_title = "Extended Attributes Created:"

            if eas_to_report:
                with open(ea_report_filename, 'w', encoding='utf-8') as f:
                    f.write(f"{report_ea_title}\n")
                    f.write("=" * len(report_ea_title) + "\n")
                    for ea_name in eas_to_report:
                        f.write(f"{ea_name}\n")
                logger.info(f"Generated Extended Attributes summary: {ea_report_filename}")
                print(f"   📄 Extended Attributes summary file: {ea_report_filename}")
            else:
                logger.info("No new or missing Extended Attributes to report.")

        # Handle create-missing flag for networks
        if args.create_missing and comparison_results['missing']:
            print(f"\n🚀 CREATING MISSING NETWORKS:")
            
            # Sort missing networks by priority (larger networks first)
            missing_with_priority = []
            for item in comparison_results['missing']:
                vpc = item['vpc']
                aws_tags = item['aws_tags']
                priority = vpc_manager._calculate_network_priority(vpc, aws_tags)
                missing_with_priority.append((priority, item))
            
            # Sort by priority
            missing_with_priority.sort(key=lambda x: x[0])
            sorted_missing = [item for priority, item in missing_with_priority]
            
            print(f"   📋 Creating {len(sorted_missing)} networks in priority order...")
            print(f"   🔢 Priority order: larger networks (/16, /17) before smaller (/24, /25)")
            
            # Create networks
            operation_results = vpc_manager.create_missing_networks(
                sorted_missing, 
                network_view=network_view, 
                dry_run=args.dry_run
            )
            
            # Show results
            created_count = sum(1 for r in operation_results if r.get('action') == 'created')
            would_create_count = sum(1 for r in operation_results if r.get('action') == 'would_create')
            error_count = sum(1 for r in operation_results if r.get('action') == 'error')
            rejected_count = sum(1 for r in operation_results if r.get('action') == 'would_reject')
            
            if args.dry_run:
                print(f"   ✅ Would create: {would_create_count}")
                print(f"   ⚠️ Would reject: {rejected_count}")
                print(f"   ❌ Would fail: {error_count}")
            else:
                print(f"   ✅ Successfully created: {created_count}")
                print(f"   ❌ Failed to create: {error_count}")
                if error_count > 0:
                    print(f"   📄 Check rejected networks CSV for failed creations")
        
        # Handle EA Discrepancies
        if args.create_missing and comparison_results['discrepancies']:
            print(f"\n🔧 FIXING EA DISCREPANCIES:")
            discrepancy_results = vpc_manager.fix_ea_discrepancies(
                comparison_results['discrepancies'], 
                dry_run=args.dry_run
            )
            
            if args.dry_run:
                print(f"   🔧 Would update {discrepancy_results['would_update_count']} networks with correct EAs")
            else:
                print(f"   ✅ Updated {discrepancy_results['updated_count']} networks")
                print(f"   ❌ Failed to update {discrepancy_results['failed_count']} networks")

        # Generate EA Discrepancies Report
        if comparison_results['discrepancies']:
            generate_ea_discrepancies_report(comparison_results['discrepancies'])
        
        # Generate Comprehensive Network Status Report
        generate_network_status_report(comparison_results, args.dry_run)

        print(f"\n✅ OPERATION COMPLETED")
        print(f"   📝 Check logs: aws_infoblox_vpc_manager.log")
        print(f"   📊 For detailed reports, check the reports/ directory")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Error: {e}")
        return 1


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
                    comment=f"AWS tag mapping for {ea_name}",
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


class AWSTagParser:
    """Handles parsing of AWS tags from various formats"""
    
    @staticmethod
    def parse_tags_from_string(tags_str: str) -> Dict[str, str]:
        """Parse AWS tags from string representation"""
        if not tags_str or pd.isna(tags_str) or tags_str == '[]':
            return {}
        
        try:
            if isinstance(tags_str, str):
                tags_str = tags_str.strip()
                if tags_str.startswith('[') and tags_str.endswith(']'):
                    tag_list = ast.literal_eval(tags_str)
                    if isinstance(tag_list, list):
                        return {tag['Key']: tag['Value'] for tag in tag_list if 'Key' in tag and 'Value' in tag}
            elif isinstance(tags_str, list):
                return {tag['Key']: tag['Value'] for tag in tags_str if 'Key' in tag and 'Value' in tag}
            
            return {}
            
        except (ValueError, SyntaxError, KeyError) as e:
            logger.warning(f"Error parsing tags: {tags_str[:100]}... Error: {e}")
            return {}


class VPCManager:
    """Main class for managing AWS VPC to InfoBlox synchronization"""
    
    def __init__(self, infoblox_client: InfoBloxClient):
        self.ib_client = infoblox_client
        self.tag_parser = AWSTagParser()
        
    def load_vpc_data(self, csv_file_path: str) -> pd.DataFrame:
        """Load VPC data from CSV file"""
        try:
            df = pd.read_csv(csv_file_path)
            logger.info(f"Loaded {len(df)} VPC records from {csv_file_path}")
            return df
        except Exception as e:
            logger.error(f"Error loading VPC data: {e}")
            raise
    
    def parse_vpc_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse tags column and add parsed tags as new column"""
        df = df.copy()
        df['ParsedTags'] = df['Tags'].apply(self.tag_parser.parse_tags_from_string)
        return df
    
    def map_aws_tags_to_infoblox_eas(self, aws_tags: Dict[str, str]) -> Dict[str, str]:
        """Map AWS tags to InfoBlox Extended Attributes"""
        tag_mapping = {
            'Name': 'aws_name',
            'environment': 'environment', 
            'Environment': 'environment',
            'owner': 'owner',
            'Owner': 'owner', 
            'project': 'project',
            'Project': 'project',
            'location': 'aws_location',
            'Location': 'aws_location',
            'cloudservice': 'aws_cloudservice',
            'createdby': 'aws_created_by',
            'RequestedBy': 'aws_requested_by',
            'Requested_By': 'aws_requested_by',
            'dud': 'aws_dud',
            'AccountId': 'aws_account_id',
            'Region': 'aws_region',
            'VpcId': 'aws_vpc_id',
            'Description': 'description'
        }
        
        mapped_eas = {}
        for aws_key, aws_value in aws_tags.items():
            ea_key = tag_mapping.get(aws_key, f"aws_{aws_key.lower()}")
            ea_key = ea_key.replace('-', '_').replace(' ', '_').lower()
            ea_value = str(aws_value)[:255] if len(str(aws_value)) > 255 else str(aws_value)
            mapped_eas[ea_key] = ea_value
        
        return mapped_eas
    
    def compare_vpc_with_infoblox(self, vpc_df: pd.DataFrame, network_view: str = "default") -> Dict:
        """Compare AWS VPC data with InfoBlox networks and network containers"""
        results = {
            'matches': [],
            'missing': [], 
            'discrepancies': [],
            'containers': [],
            'errors': []
        }
        
        for _, vpc in vpc_df.iterrows():
            cidr = vpc['CidrBlock']
            vpc_id = vpc.get('VpcId', 'unknown')
            
            try:
                aws_tags = vpc.get('ParsedTags', {})
                mapped_eas = self.map_aws_tags_to_infoblox_eas(aws_tags)
                
                # Check if network exists
                existence_check = self.ib_client.check_network_or_container_exists(cidr, network_view)
                
                if not existence_check['exists']:
                    logger.debug(f"Network {cidr} ({vpc_id}) not found in InfoBlox")
                    results['missing'].append({
                        'vpc': vpc.to_dict(),
                        'cidr': cidr,
                        'aws_tags': aws_tags,
                        'mapped_eas': mapped_eas
                    })
                elif existence_check['type'] == 'container':
                    logger.info(f"CIDR {cidr} ({vpc_id}) exists as network container in InfoBlox")
                    ib_container = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_container.get('extattrs', {}).items()}
                    
                    results['containers'].append({
                        'vpc': vpc.to_dict(),
                        'cidr': cidr,
                        'ib_container': ib_container,
                        'aws_tags': aws_tags,
                        'ib_eas': ib_eas,
                        'mapped_eas': mapped_eas,
                        'note': 'Exists as network container - contains subnets'
                    })
                else:
                    # Network exists as regular network
                    logger.debug(f"Network {cidr} ({vpc_id}) found in InfoBlox")
                    ib_network = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_network.get('extattrs', {}).items()}
                    
                    # Compare EAs
                    ea_match = self._compare_eas(mapped_eas, ib_eas)
                    
                    if ea_match:
                        logger.debug(f"Network {cidr} ({vpc_id}) has matching EAs")
                        results['matches'].append({
                            'vpc': vpc.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'aws_tags': aws_tags,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                    else:
                        logger.info(f"Network {cidr} ({vpc_id}) has EA discrepancies")
                        results['discrepancies'].append({
                            'vpc': vpc.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'aws_tags': aws_tags,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                        
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing VPC {vpc_id} ({cidr}): {error_msg}")
                
                # Try to provide more context about the error
                if "not found" in error_msg.lower() or "404" in error_msg:
                    logger.info(f"Network {cidr} ({vpc_id}) appears to not exist in InfoBlox")
                    results['missing'].append({
                        'vpc': vpc.to_dict(),
                        'cidr': cidr,
                        'aws_tags': aws_tags,
                        'mapped_eas': self.map_aws_tags_to_infoblox_eas(aws_tags)
                    })
                else:
                    # Only true errors go here (network issues, parsing errors, etc.)
                    results['errors'].append({
                        'vpc': vpc.to_dict(),
                        'cidr': cidr,
                        'error': error_msg
                    })
        
        return results
    
    def _compare_eas(self, mapped_eas: Dict[str, str], ib_eas: Dict[str, str]) -> bool:
        """Compare mapped AWS tags with InfoBlox EAs - returns True only if they match exactly"""
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
    
    def _calculate_network_priority(self, vpc: Dict, aws_tags: Dict) -> int:
        """Calculate priority for network creation - lower values = higher priority"""
        cidr = vpc.get('CidrBlock', '')
        
        # Extract network size from CIDR
        try:
            prefix_len = int(cidr.split('/')[-1])
        except:
            prefix_len = 32  # Default to smallest if can't parse
        
        # Priority is based on network size - larger networks (smaller prefix) get higher priority
        return prefix_len
    
    def ensure_required_eas(self, vpc_df: pd.DataFrame, dry_run: bool = False) -> Dict:
        """Ensure all required Extended Attributes exist in InfoBlox"""
        all_eas = set()
        
        # Collect all unique EA names from AWS tags
        for _, vpc in vpc_df.iterrows():
            aws_tags = vpc.get('ParsedTags', {})
            mapped_eas = self.map_aws_tags_to_infoblox_eas(aws_tags)
            all_eas.update(mapped_eas.keys())
        
        logger.info(f"Found {len(all_eas)} unique Extended Attributes in AWS tags")
        
        if dry_run:
            # In dry run, just check what would be created
            existing_eas = self.ib_client.get_extensible_attributes()
            existing_names = {ea['name'] for ea in existing_eas}
            missing_eas = list(all_eas - existing_names)
            
            return {
                'missing_eas': missing_eas,
                'existing_count': len(all_eas & existing_names),
                'would_create_count': len(missing_eas)
            }
        else:
            # Actually create missing EAs
            ea_results = self.ib_client.ensure_required_eas_exist(list(all_eas))
            
            created_count = sum(1 for status in ea_results.values() if status == 'created')
            existing_count = sum(1 for status in ea_results.values() if status == 'exists')
            
            return {
                'ea_results': ea_results,
                'created_count': created_count,
                'existing_count': existing_count
            }
    
    def create_missing_networks(self, missing_networks: List[Dict], network_view: str = "default", 
                               dry_run: bool = False) -> List[Dict]:
        """Create missing networks in InfoBlox"""
        results = []
        
        for item in missing_networks:
            vpc = item['vpc']
            cidr = item['cidr']
            mapped_eas = item['mapped_eas']
            vpc_name = vpc.get('Name', 'Unnamed VPC')
            
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would create network: {cidr} ({vpc_name})")
                    results.append({
                        'cidr': cidr,
                        'vpc_name': vpc_name,
                        'action': 'would_create',
                        'result': 'success'
                    })
                else:
                    # Create the network
                    comment = f"AWS VPC: {vpc_name} (VPC ID: {vpc.get('VpcId', 'Unknown')})"
                    result = self.ib_client.create_network(
                        cidr=cidr,
                        network_view=network_view,
                        comment=comment,
                        extattrs=mapped_eas
                    )
                    
                    logger.info(f"Created network: {cidr} ({vpc_name})")
                    results.append({
                        'cidr': cidr,
                        'vpc_name': vpc_name,
                        'action': 'created',
                        'result': 'success',
                        'ref': result
                    })
                    
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                
                # Check if network already exists (not really an error)
                if 'already exists' in error_lower or 'duplicate' in error_lower:
                    logger.info(f"Network {cidr} already exists - checking if EAs need updating")
                    
                    # Try to get the existing network and update its EAs
                    try:
                        existing_network = self.ib_client.get_network_by_cidr(cidr, network_view)
                        if existing_network:
                            # Update the EAs on the existing network
                            network_ref = existing_network['_ref']
                            self.ib_client.update_network_extattrs(network_ref, mapped_eas)
                            logger.info(f"Updated EAs for existing network: {cidr}")
                            
                            results.append({
                                'cidr': cidr,
                                'vpc_name': vpc_name,
                                'action': 'already_existed_updated_eas',
                                'result': 'success'
                            })
                        else:
                            results.append({
                                'cidr': cidr,
                                'vpc_name': vpc_name,
                                'action': 'already_existed',
                                'result': 'success'
                            })
                    except Exception as update_error:
                        logger.warning(f"Could not update EAs for existing network {cidr}: {update_error}")
                        results.append({
                            'cidr': cidr,
                            'vpc_name': vpc_name,
                            'action': 'already_existed_ea_update_failed',
                            'error': str(update_error),
                            'vpc': vpc
                        })
                else:
                    # This is a real error
                    logger.error(f"Failed to create network {cidr}: {error_msg}")
                    
                    # Categorize the error
                    category = 'unknown'
                    if 'overlap' in error_lower or 'parent' in error_lower:
                        category = 'overlap'
                    elif 'permission' in error_lower or 'auth' in error_lower:
                        category = 'permission'
                    elif 'invalid' in error_lower:
                        category = 'invalid'
                    elif 'network view' in error_lower:
                        category = 'network_view_error'
                    elif 'not found' in error_lower:
                        category = 'not_found'
                    elif 'extensible' in error_lower or 'attribute' in error_lower:
                        category = 'ea_error'
                    
                    # Log detailed debugging info
                    logger.debug(f"Network creation failed - Category: {category}")
                    logger.debug(f"VPC Details: Name={vpc_name}, CIDR={cidr}, VPC_ID={vpc.get('VpcId', 'Unknown')}")
                    logger.debug(f"Extended Attributes: {mapped_eas}")
                    
                    results.append({
                        'cidr': cidr,
                        'vpc_name': vpc_name,
                        'action': 'error',
                        'error': error_msg,
                        'category': category,
                        'vpc': vpc
                    })
        
        # Generate status CSV files
        if not dry_run:
            # Networks that already existed
            already_existed = [r for r in results if r.get('action') in ['already_existed', 'already_existed_updated_eas']]
            if already_existed:
                self._generate_already_existed_csv(already_existed)
            
            # Real errors (not including "already exists")
            error_results = [r for r in results if r.get('action') == 'error']
            if error_results:
                self._generate_network_creation_errors_csv(error_results)
            
            # EA update failures
            ea_failures = [r for r in results if r.get('action') == 'already_existed_ea_update_failed']
            if ea_failures:
                self._generate_ea_update_failures_csv(ea_failures)
        
        return results
    
    def _generate_network_creation_errors_csv(self, error_results: List[Dict]):
        """Generate CSV file with actual network creation errors"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"network_creation_errors_{timestamp}.csv"
        
        data = []
        for result in error_results:
            vpc = result.get('vpc', {})
            data.append({
                'CIDR': result['cidr'],
                'VPC_Name': result['vpc_name'],
                'VPC_ID': vpc.get('VpcId', ''),
                'Account_ID': vpc.get('AccountId', ''),
                'Region': vpc.get('Region', ''),
                'Error_Category': result['category'],
                'Error_Message': result['error'],
                'AWS_Tags': str(vpc.get('ParsedTags', {}))
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Generated network creation errors report: {filename}")
    
    def _generate_already_existed_csv(self, existed_results: List[Dict]):
        """Generate CSV file for networks that already existed"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"networks_already_existed_{timestamp}.csv"
        
        data = []
        for result in existed_results:
            vpc_name = result.get('vpc_name', 'Unnamed')
            data.append({
                'CIDR': result['cidr'],
                'VPC_Name': vpc_name,
                'Status': 'Already Existed',
                'EA_Updated': 'Yes' if result['action'] == 'already_existed_updated_eas' else 'No'
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Generated already existed networks report: {filename}")
    
    def _generate_ea_update_failures_csv(self, ea_failures: List[Dict]):
        """Generate CSV file for EA update failures"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ea_update_failures_{timestamp}.csv"
        
        data = []
        for result in ea_failures:
            vpc = result.get('vpc', {})
            data.append({
                'CIDR': result['cidr'],
                'VPC_Name': result.get('vpc_name', 'Unnamed'),
                'Error': result.get('error', 'Unknown error'),
                'VPC_ID': vpc.get('VpcId', ''),
                'AWS_Tags': str(vpc.get('ParsedTags', {}))
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Generated EA update failures report: {filename}")
    
    def fix_ea_discrepancies(self, discrepancies: List[Dict], dry_run: bool = False) -> Dict:
        """Fix EA discrepancies by updating networks with correct EAs from AWS"""
        results = {
            'updated_count': 0,
            'would_update_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        for item in discrepancies:
            cidr = item['cidr']
            ib_network = item['ib_network']
            mapped_eas = item['mapped_eas']
            vpc_name = item['vpc'].get('Name', 'Unnamed')
            
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would update EAs for network: {cidr} ({vpc_name})")
                    results['would_update_count'] += 1
                    results['details'].append({
                        'cidr': cidr,
                        'vpc_name': vpc_name,
                        'action': 'would_update',
                        'current_eas': item['ib_eas'],
                        'new_eas': mapped_eas
                    })
                else:
                    # Update the network's EAs
                    network_ref = ib_network['_ref']
                    self.ib_client.update_network_extattrs(network_ref, mapped_eas)
                    
                    logger.info(f"Updated EAs for network: {cidr} ({vpc_name})")
                    results['updated_count'] += 1
                    results['details'].append({
                        'cidr': cidr,
                        'vpc_name': vpc_name,
                        'action': 'updated',
                        'old_eas': item['ib_eas'],
                        'new_eas': mapped_eas
                    })
                    
            except Exception as e:
                logger.error(f"Failed to update EAs for network {cidr}: {e}")
                results['failed_count'] += 1
                results['details'].append({
                    'cidr': cidr,
                    'vpc_name': vpc_name,
                    'action': 'error',
                    'error': str(e)
                })
        
        return results


def generate_ea_discrepancies_report(discrepancies: List[Dict]):
    """Generate detailed report of EA discrepancies"""
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(reports_dir, f"ea_discrepancies_{timestamp}.md")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Extended Attributes Discrepancies Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total networks with EA discrepancies: {len(discrepancies)}\n\n")
        
        f.write("## Detailed Discrepancies\n\n")
        
        for item in discrepancies:
            vpc_name = item['vpc'].get('Name', 'Unnamed')
            cidr = item['cidr']
            vpc_id = item['vpc'].get('VpcId', 'Unknown')
            
            f.write(f"### {cidr} - {vpc_name}\n\n")
            f.write(f"- **VPC ID**: {vpc_id}\n")
            f.write(f"- **Account**: {item['vpc'].get('AccountId', 'Unknown')}\n")
            f.write(f"- **Region**: {item['vpc'].get('Region', 'Unknown')}\n\n")
            
            f.write("#### Current InfoBlox EAs:\n```\n")
            for k, v in sorted(item['ib_eas'].items()):
                f.write(f"{k}: {v}\n")
            f.write("```\n\n")
            
            f.write("#### Expected EAs from AWS:\n```\n")
            for k, v in sorted(item['mapped_eas'].items()):
                f.write(f"{k}: {v}\n")
            f.write("```\n\n")
            
            f.write("#### Differences:\n")
            all_keys = set(item['ib_eas'].keys()) | set(item['mapped_eas'].keys())
            for key in sorted(all_keys):
                ib_val = item['ib_eas'].get(key, '(missing)')
                aws_val = item['mapped_eas'].get(key, '(missing)')
                if ib_val != aws_val:
                    f.write(f"- **{key}**: `{ib_val}` → `{aws_val}`\n")
            
            f.write("\n---\n\n")
    
    logger.info(f"Generated EA discrepancies report: {filename}")


def generate_network_status_report(comparison_results: Dict, dry_run: bool = False):
    """Generate comprehensive network status report"""
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(reports_dir, f"network_status_report_{timestamp}.md")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# AWS VPC to InfoBlox Network Status Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Total Networks Analyzed**: {sum(len(v) for v in comparison_results.values())}\n")
        f.write(f"- **Fully Synchronized Networks**: {len(comparison_results['matches'])}\n")
        f.write(f"- **Missing from InfoBlox**: {len(comparison_results['missing'])}\n")
        f.write(f"- **Networks with Outdated Tags**: {len(comparison_results['discrepancies'])}\n")
        f.write(f"- **Network Containers**: {len(comparison_results['containers'])}\n")
        f.write(f"- **Processing Errors**: {len(comparison_results['errors'])}\n\n")
        
        # Missing Networks
        if comparison_results['missing']:
            f.write("## Missing Networks\n\n")
            f.write("These VPCs exist in AWS but not in InfoBlox:\n\n")
            f.write("| CIDR | VPC Name | VPC ID | Account | Region |\n")
            f.write("|------|----------|--------|---------|--------|\n")
            
            for item in comparison_results['missing']:
                vpc = item['vpc']
                f.write(f"| {item['cidr']} | {vpc.get('Name', 'Unnamed')} | ")
                f.write(f"{vpc.get('VpcId', 'Unknown')} | {vpc.get('AccountId', 'Unknown')} | ")
                f.write(f"{vpc.get('Region', 'Unknown')} |\n")
            f.write("\n")
        
        # Network Containers
        if comparison_results['containers']:
            f.write("## Network Containers\n\n")
            f.write("These VPCs exist as network containers in InfoBlox:\n\n")
            f.write("| CIDR | VPC Name | VPC ID | Note |\n")
            f.write("|------|----------|--------|------|\n")
            
            for item in comparison_results['containers']:
                vpc = item['vpc']
                f.write(f"| {item['cidr']} | {vpc.get('Name', 'Unnamed')} | ")
                f.write(f"{vpc.get('VpcId', 'Unknown')} | {item['note']} |\n")
            f.write("\n")
        
        # Processing Errors
        if comparison_results['errors']:
            f.write("## Processing Errors\n\n")
            f.write("Errors encountered during processing:\n\n")
            
            for item in comparison_results['errors']:
                vpc = item['vpc']
                f.write(f"### {item['cidr']} - {vpc.get('Name', 'Unnamed')}\n")
                f.write(f"- **Error**: {item['error']}\n")
                f.write(f"- **VPC ID**: {vpc.get('VpcId', 'Unknown')}\n\n")
    
    logger.info(f"Generated network status report: {filename}")


if __name__ == "__main__":
    sys.exit(main())
