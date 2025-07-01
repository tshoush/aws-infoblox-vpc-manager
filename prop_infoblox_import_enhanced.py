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
        if args.csv_file and args.csv_file != 'modified_properties_file.csv':
            csv_file = args.csv_file
            print(f"Using CSV file from command line: {csv_file}")
        
        # Show container configuration
        if container_prefixes:
            print(f"📦 Container prefixes configured: /{', /'.join(map(str, container_prefixes))}")
            print(f"🔧 Container mode: {container_mode}")
        else:
            print("📦 Container detection: Auto-detect from overlaps")
        
        logger.info(f"Loading property data from {csv_file}...")
        
        # Initialize InfoBlox client
        print(f"\n🔗 Connecting to InfoBlox Grid Master: {grid_master}")
        ib_client = InfoBloxClient(grid_master, username, password)
        
        # Initialize Property Manager
        prop_manager = PropertyManager(ib_client)
        
        # Load and parse property data
        try:
            property_df = prop_manager.load_property_data(csv_file)
            property_df = prop_manager.parse_prefixes(property_df)
        except Exception as e:
            logger.error(f"Failed to load property data: {e}")
            return 1
        
        print(f"\n📊 ANALYSIS SUMMARY:")
        print(f"   📁 CSV file: {csv_file}")
        print(f"   🔢 Total networks loaded: {len(property_df)}")
        print(f"   🌐 Network view: {network_view}")
        
        # Compare with InfoBlox
        logger.info("Comparing property networks with InfoBlox...")
        comparison_results = prop_manager.compare_properties_with_infoblox(property_df, network_view)
        
        # Display results
        print(f"\n🔍 COMPARISON RESULTS:")
        print(f"   ✅ Fully synchronized (network + EAs): {len(comparison_results['matches'])}")
        print(f"   🔴 Missing from InfoBlox: {len(comparison_results['missing'])}")
        print(f"   🟡 Networks with outdated EAs: {len(comparison_results['discrepancies'])}")
        print(f"   📦 Network containers: {len(comparison_results['containers'])}")
        print(f"   ❌ Processing errors: {len(comparison_results['errors'])}")
        
        # Show update requirements summary
        if comparison_results['discrepancies']:
            print(f"\n🔧 UPDATE REQUIREMENTS:")
            print(f"   🏷️ Networks requiring EA updates: {len(comparison_results['discrepancies'])}")
            
            # Show sample of networks that need updates
            sample_discrepancies = comparison_results['discrepancies'][:3]
            for item in sample_discrepancies:
                site_id = item['site_id']
                m_host = item['m_host']
                cidr = item['cidr']
                print(f"   📄 {cidr} (Site: {site_id}, Host: {m_host}) - EAs need updating")
            
            if len(comparison_results['discrepancies']) > 3:
                print(f"   ... and {len(comparison_results['discrepancies']) - 3} more networks")
        
        # Show network containers summary
        if comparison_results.get('containers'):
            print(f"\n📦 NETWORK CONTAINERS FOUND:")
            print(f"   🔢 Networks existing as containers: {len(comparison_results['containers'])}")
            print(f"   ℹ️ These exist as network containers (parent networks) in InfoBlox")
            print(f"   💡 Container networks typically contain smaller subnet networks")
            for container in comparison_results['containers'][:3]:
                print(f"   📦 {container['cidr']} - Site: {container['site_id']}")
            if len(comparison_results['containers']) > 3:
                print(f"   ... and {len(comparison_results['containers']) - 3} more")
        
        # Analyze Extended Attributes (regardless of missing networks)
        if args.create_missing:
            print(f"\n🔍 EXTENDED ATTRIBUTES ANALYSIS:")
            ea_analysis = prop_manager.ensure_required_eas(property_df, dry_run=args.dry_run)
            
            # Generate EA summary report
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ea_report_filename = os.path.join(reports_dir, f"property_extended_attributes_summary_{timestamp}.txt")
            
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

        # Handle create-missing flag for networks WITH OVERLAP DETECTION
        if args.create_missing and comparison_results['missing']:
            print(f"\n🚀 ANALYZING NETWORKS FOR OVERLAPS AND CREATION:")
            
            # Perform overlap analysis first
            overlap_analysis = analyze_network_overlaps(comparison_results['missing'])
            
            # Report overlap findings
            if overlap_analysis['containers']:
                print(f"\n🔍 OVERLAP DETECTION RESULTS:")
                print(f"   📦 Networks to be created as containers: {len(overlap_analysis['containers'])}")
                for container_cidr in sorted(overlap_analysis['containers']):
                    contained_nets = overlap_analysis['relationships'].get(container_cidr, [])
                    print(f"      - {container_cidr} (will contain {len(contained_nets)} networks)")
                    for net in contained_nets[:3]:
                        print(f"        └─ {net['cidr']} (Site: {net['site_id']})")
                    if len(contained_nets) > 3:
                        print(f"        └─ ... and {len(contained_nets) - 3} more")
            
            if overlap_analysis['overlaps']:
                print(f"\n⚠️  PARTIAL OVERLAPS DETECTED:")
                for overlap in overlap_analysis['overlaps']:
                    print(f"   - {overlap['message']}")
            
            # Create networks with overlap handling
            operation_results = prop_manager.create_missing_networks_with_overlap_handling(
                comparison_results['missing'], 
                network_view=network_view, 
                dry_run=args.dry_run,
                overlap_analysis=overlap_analysis
            )
            
            # Show results
            container_count = sum(1 for r in operation_results if 'container' in r.get('action', ''))
            network_count = sum(1 for r in operation_results if 'container' not in r.get('action', '') and r.get('action') != 'error')
            error_count = sum(1 for r in operation_results if r.get('action') == 'error')
            
            if args.dry_run:
                print(f"\n📊 DRY RUN RESULTS:")
                print(f"   📦 Would create containers: {sum(1 for r in operation_results if r.get('action') == 'would_create_container')}")
                print(f"   🌐 Would create networks: {sum(1 for r in operation_results if r.get('action') in ['would_create', 'would_create_in_container'])}")
                print(f"   ❌ Would fail: {error_count}")
            else:
                print(f"\n📊 CREATION RESULTS:")
                print(f"   📦 Containers created: {sum(1 for r in operation_results if r.get('action') == 'created_container')}")
                print(f"   🌐 Networks created: {sum(1 for r in operation_results if r.get('action') in ['created', 'created_in_container'])}")
                print(f"   ❌ Failed: {error_count}")
                if error_count > 0:
                    print(f"   📄 Check creation status CSV for details")
        
        # Handle EA Discrepancies
        if args.create_missing and comparison_results['discrepancies']:
            print(f"\n🔧 FIXING EA DISCREPANCIES:")
            discrepancy_results = prop_manager.fix_ea_discrepancies(
                comparison_results['discrepancies'], 
                dry_run=args.dry_run
            )
            
            if args.dry_run:
                print(f"   🔧 Would update {discrepancy_results['would_update_count']} networks with correct EAs")
            else:
                print(f"   ✅ Updated {discrepancy_
