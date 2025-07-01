#!/usr/bin/env python3
"""
AWS to InfoBlox VPC Management Tool

This script reads AWS VPC data from CSV format and provides functionality to:
1. Parse AWS Tags and map them to InfoBlox Extended Attributes
2. Compare VPC subnets between AWS and InfoBlox
3. Create missing subnets in InfoBlox with proper tags/EAs
4. Update existing subnets with corrected tags/EAs

Author: Generated for AWS-InfoBlox Integration
Date: June 4, 2025
"""

import pandas as pd
import requests
import json
import urllib3
import ast
import logging
from ipaddress import ip_network, AddressValueError
import os
from dotenv import load_dotenv
import getpass
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import argparse
import sys
from enhanced_report_generator import EnhancedReportGenerator

# Disable SSL warnings for InfoBlox API calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aws_infoblox_vpc_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AWSTagParser:
    """Handles parsing of AWS tags from various formats"""
    
    @staticmethod
    def parse_tags_from_string(tags_str: str) -> Dict[str, str]:
        """
        Parse AWS tags from string representation of list of dictionaries
        
        Example input: "[{'Key': 'environment', 'Value': 'prod'}, {'Key': 'team', 'Value': 'dev'}]"
        Output: {'environment': 'prod', 'team': 'dev'}
        """
        if not tags_str or pd.isna(tags_str) or tags_str == '[]':
            return {}
        
        try:
            # Handle string representation of Python list
            if isinstance(tags_str, str):
                # Remove any extra whitespace and normalize quotes
                tags_str = tags_str.strip()
                if tags_str.startswith('[') and tags_str.endswith(']'):
                    # Use ast.literal_eval for safe evaluation
                    tag_list = ast.literal_eval(tags_str)
                    if isinstance(tag_list, list):
                        return {tag['Key']: tag['Value'] for tag in tag_list if 'Key' in tag and 'Value' in tag}
            
            # Handle direct list input
            elif isinstance(tags_str, list):
                return {tag['Key']: tag['Value'] for tag in tags_str if 'Key' in tag and 'Value' in tag}
            
            return {}
            
        except (ValueError, SyntaxError, KeyError) as e:
            logger.warning(f"Error parsing tags: {tags_str[:100]}... Error: {e}")
            return {}


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
        self._ea_cache = {}  # Cache for Extended Attribute definitions
        
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
            # Log the full error details
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
        """Get all available network views"""
        response = self._make_request('GET', 'networkview')
        return response.json()
    
    def get_networks_in_view(self, network_view: str = "default", network_container: Optional[str] = None) -> List[Dict]:
        """Get all networks in a specific network view"""
        params = {
            'network_view': network_view,
            '_return_fields': 'network,comment,extattrs'
        }
        
        if network_container:
            params['network_container'] = network_container
            
        response = self._make_request('GET', 'network', params=params)
        return response.json()
    
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
            return networks[0] if networks else None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                # 400 usually means "network not found" which is normal
                logger.debug(f"Network {cidr} not found in view {network_view} (this is normal if creating new networks)")
                return None
            else:
                # Re-raise other HTTP errors
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
            return containers[0] if containers else None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.debug(f"Network container {cidr} not found in view {network_view}")
                return None
            else:
                raise
    
    def check_network_or_container_exists(self, cidr: str, network_view: str = "default") -> Dict[str, Any]:
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
            # Convert simple dict to InfoBlox EA format
            data['extattrs'] = {k: {'value': v} for k, v in extattrs.items()}
        
        response = self._make_request('POST', 'network', data=data)
        logger.info(f"Created network {cidr} in view {network_view}")
        return response.json()
    
    def update_network(self, network_ref: str, comment: Optional[str] = None, 
                      extattrs: Optional[Dict[str, str]] = None) -> Dict:
        """Update an existing network in InfoBlox"""
        data = {}
        
        if comment is not None:
            data['comment'] = comment
            
        if extattrs:
            # Convert simple dict to InfoBlox EA format
            data['extattrs'] = {k: {'value': v} for k, v in extattrs.items()}
        
        response = self._make_request('PUT', network_ref, data=data)
        logger.info(f"Updated network {network_ref}")
        return response.json()
    
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
            # Clear cache to force refresh
            if 'definitions' in self._ea_cache:
                del self._ea_cache['definitions']
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                # Check if EA already exists
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
        """
        Map AWS tags to InfoBlox Extended Attributes with standardized naming
        
        This function can be customized to implement specific tag mapping rules
        """
        # Define tag mapping rules
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
            'Description': 'description',
            'tfc_created': 'aws_tfc_created',
            'tfe_created': 'aws_tfe_created'
        }
        
        # Apply mapping
        mapped_eas = {}
        for aws_key, aws_value in aws_tags.items():
            # Use mapped name if available, otherwise use original key with aws_ prefix
            ea_key = tag_mapping.get(aws_key, f"aws_{aws_key.lower()}")
            
            # Clean up the key (InfoBlox EA names have restrictions)
            ea_key = ea_key.replace('-', '_').replace(' ', '_').lower()
            
            # Truncate value if too long (InfoBlox EA values have length limits)
            ea_value = str(aws_value)[:255] if len(str(aws_value)) > 255 else str(aws_value)
            
            mapped_eas[ea_key] = ea_value
        
        return mapped_eas
    
    def compare_vpc_with_infoblox(self, vpc_df: pd.DataFrame, network_view: str = "default") -> Dict[str, List]:
        """
        Compare AWS VPC data with InfoBlox networks and network containers
        
        Returns:
        - matches: VPCs that exist in both with matching tags
        - missing: VPCs that don't exist in InfoBlox
        - discrepancies: VPCs that exist but have different tags
        - containers: VPCs that exist as network containers (not regular networks)
        """
        results = {
            'matches': [],
            'missing': [], 
            'discrepancies': [],
            'containers': [],
            'errors': []
        }
        
        for _, vpc in vpc_df.iterrows():
            try:
                cidr = vpc['CidrBlock']
                aws_tags = vpc.get('ParsedTags', {})
                
                # Check if exists as network or container
                existence_check = self.ib_client.check_network_or_container_exists(cidr, network_view)
                
                if not existence_check['exists']:
                    # Network doesn't exist in InfoBlox at all
                    results['missing'].append({
                        'vpc': vpc.to_dict(),
                        'cidr': cidr,
                        'aws_tags': aws_tags,
                        'mapped_eas': self.map_aws_tags_to_infoblox_eas(aws_tags)
                    })
                elif existence_check['type'] == 'container':
                    # Exists as network container - treat as special case
                    ib_container = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_container.get('extattrs', {}).items()}
                    mapped_eas = self.map_aws_tags_to_infoblox_eas(aws_tags)
                    
                    results['containers'].append({
                        'vpc': vpc.to_dict(),
                        'cidr': cidr,
                        'ib_container': ib_container,
                        'aws_tags': aws_tags,
                        'ib_eas': ib_eas,
                        'mapped_eas': mapped_eas,
                        'note': 'Exists as network container - contains subnets'
                    })
                    logger.info(f"CIDR {cidr} exists as network container in InfoBlox")
                else:
                    # Exists as regular network, compare tags/EAs
                    ib_network = existence_check['object']
                    ib_eas = {k: v.get('value', '') for k, v in ib_network.get('extattrs', {}).items()}
                    mapped_eas = self.map_aws_tags_to_infoblox_eas(aws_tags)
                    
                    if self._compare_eas(mapped_eas, ib_eas):
                        results['matches'].append({
                            'vpc': vpc.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'aws_tags': aws_tags,
                            'ib_eas': ib_eas
                        })
                    else:
                        results['discrepancies'].append({
                            'vpc': vpc.to_dict(),
                            'cidr': cidr,
                            'ib_network': ib_network,
                            'aws_tags': aws_tags,
                            'ib_eas': ib_eas,
                            'mapped_eas': mapped_eas
                        })
                        
            except Exception as e:
                logger.error(f"Error processing VPC {vpc.get('VpcId', 'unknown')}: {e}")
                results['errors'].append({
                    'vpc': vpc.to_dict(),
                    'error': str(e)
                })
        
        return results
    
    def _compare_eas(self, mapped_eas: Dict[str, str], ib_eas: Dict[str, str]) -> bool:
        """Compare mapped AWS tags with InfoBlox EAs"""
        # Compare only the keys that exist in mapped_eas
        for key, value in mapped_eas.items():
            if key not in ib_eas or ib_eas[key] != value:
                return False
        return True
    
    def _calculate_network_priority(self, vpc: Dict, aws_tags: Dict[str, str]) -> int:
        """
        Calculate priority for network creation (lower number = higher priority)
        Create larger networks first (smaller CIDR prefix numbers)
        """
        # Start with CIDR prefix as base priority (larger networks = lower numbers = higher priority)
        try:
            cidr_prefix = int(vpc['CidrBlock'].split('/')[1])
            # Use CIDR prefix directly as base priority
            # /16 = priority 16, /17 = priority 17, /24 = priority 24, etc.
            priority = cidr_prefix
        except:
            priority = 99  # Default high priority (low importance) for unparseable CIDRs
        
        # Adjust priority based on environment (subtract from base to increase priority)
        env = aws_tags.get('environment', aws_tags.get('Environment', '')).lower()
        if env in ['prod', 'production']:
            priority -= 5  # Highest environment priority
        elif env in ['staging', 'stage']:
            priority -= 3
        elif env in ['test', 'testing']:
            priority -= 2
        elif env in ['dev', 'development']:
            priority -= 1
        
        return max(1, priority)  # Ensure priority is at least 1
    
    def create_missing_networks(self, missing_networks: List[Dict], network_view: str = "default", 
                              dry_run: bool = True) -> List[Dict]:
        """Create missing networks in InfoBlox"""
        results = []
        rejected_networks = []
        
        for item in missing_networks:
            try:
                vpc = item['vpc']
                cidr = item['cidr']
                mapped_eas = item['mapped_eas']
                
                # Create comment from VPC data
                comment = f"AWS VPC: {vpc['Name']} ({vpc['VpcId']}) in {vpc['AccountId']}/{vpc['Region']}"
                
                if dry_run:
                    # Double-check if it's a network container during dry run
                    existence_check = self.ib_client.check_network_or_container_exists(cidr, network_view)
                    if existence_check['exists'] and existence_check['type'] == 'container':
                        logger.info(f"DRY RUN: {cidr} exists as network container - cannot create as regular network")
                        results.append({
                            'cidr': cidr,
                            'action': 'would_reject',
                            'reason': 'exists_as_container',
                            'comment': comment,
                            'eas': mapped_eas
                        })
                    else:
                        logger.info(f"DRY RUN: Would create network {cidr} with comment: {comment}")
                        logger.info(f"DRY RUN: EAs would be: {mapped_eas}")
                        results.append({
                            'cidr': cidr,
                            'action': 'would_create',
                            'comment': comment,
                            'eas': mapped_eas
                        })
                else:
                    # Actually create the network
                    response = self.ib_client.create_network(
                        cidr=cidr,
                        network_view=network_view,
                        comment=comment,
                        extattrs=mapped_eas
                    )
                    results.append({
                        'cidr': cidr,
                        'action': 'created',
                        'response': response
                    })
                    
            except Exception as e:
                error_str = str(e)
                logger.error(f"Error creating network {item['cidr']}: {error_str}")
                
                # Determine rejection reason
                rejection_reason = "Unknown error"
                suggestion = "Review error details"
                
                if "network container" in error_str.lower() or "parent" in error_str.lower():
                    rejection_reason = "Conflicts with existing network container"
                    suggestion = "Network exists as container or conflicts with parent network"
                elif "already exists" in error_str.lower():
                    rejection_reason = "Network already exists"
                    suggestion = "Network already exists in InfoBlox"
                elif "extensible attribute" in error_str.lower():
                    rejection_reason = "Extended Attribute error"
                    suggestion = "Create missing Extended Attributes first"
                elif "overlap" in error_str.lower():
                    rejection_reason = "Network overlap conflict"
                    suggestion = "Check for overlapping networks"
                
                results.append({
                    'cidr': item['cidr'],
                    'action': 'error',
                    'error': error_str,
                    'rejection_reason': rejection_reason
                })
                
                rejected_networks.append({
                    'vpc': item['vpc'],
                    'reason': rejection_reason,
                    'suggestion': suggestion,
                    'error_details': error_str
                })
        
        # Generate rejected networks CSV if there are any rejections
        if rejected_networks and not dry_run:
            self._generate_rejected_networks_csv(rejected_networks)
        
        return results
    
    def _generate_rejected_networks_csv(self, rejected_networks: List[Dict]) -> None:
        """Generate simple rejected networks CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rejected_networks_{timestamp}.csv"
        
        csv_data = []
        for item in rejected_networks:
            vpc = item['vpc']
            csv_row = {
                'AccountId': vpc.get('AccountId', ''),
                'Region': vpc.get('Region', ''),
                'VpcId': vpc.get('VpcId', ''),
                'Name': vpc.get('Name', ''),
                'CidrBlock': vpc.get('CidrBlock', ''),
                'RejectionReason': item.get('reason', ''),
                'Suggestion': item.get('suggestion', ''),
                'ErrorDetails': item.get('error_details', '')
            }
            csv_data.append(csv_row)
        
        df = pd.DataFrame(csv_data)
        df.to_csv(filename, index=False)
        
        logger.info(f"Generated rejected networks CSV: {filename}")
        print(f"\n📄 REJECTED NETWORKS FILE GENERATED: {filename}")


def show_and_edit_config():
    """Display current configuration and allow user to edit it"""
    load_dotenv('config.env')
    
    print("\n" + "=" * 60)
    print("📋 CURRENT CONFIGURATION")
    print("=" * 60)
    
    config = {
        'GRID_MASTER': os.getenv('GRID_MASTER', ''),
        'NETWORK_VIEW': os.getenv('NETWORK_VIEW', 'default'),
        'USERNAME': os.getenv('USERNAME', ''),
        'PASSWORD': os.getenv('PASSWORD', ''),
        'CSV_FILE': os.getenv('CSV_FILE', 'vpc_data.csv'),
        'PARENT_CONTAINER_PREFIXES': os.getenv('PARENT_CONTAINER_PREFIXES', ''),
        'CONTAINER_HIERARCHY_MODE': os.getenv('CONTAINER_HIERARCHY_MODE', 'strict')
    }
    
    print(f"🌐 InfoBlox Grid Master: {config['GRID_MASTER'] or '(not set)'}")
    print(f"🔍 Network View: {config['NETWORK_VIEW']}")
    print(f"👤 Username: {config['USERNAME'] or '(not set)'}")
    print(f"🔒 Password: {'***' if config['PASSWORD'] else '(not set)'}")
    print(f"📄 CSV File: {config['CSV_FILE']}")
    print(f"📦 Container Prefixes: {config['PARENT_CONTAINER_PREFIXES'] or '(auto-detect)'}")
    print(f"🔧 Container Mode: {config['CONTAINER_HIERARCHY_MODE']}")
    
    print("\n" + "=" * 60)
    
    while True:
        choice = input("\nDo you want to modify any configuration? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            print("\n📝 Edit mode not implemented in this version")
            print("Please modify config.env directly if needed")
            break
        elif choice in ['n', 'no']:
            break
        else:
            print("Please enter 'y' for yes or 'n' for no.")
    
    return config


def get_config(skip_network_view_prompt=False, config_override=None):
    """Load configuration from environment or prompt user"""
    if config_override:
        grid_master = config_override['GRID_MASTER']
        network_view = config_override['NETWORK_VIEW']
        username = config_override['USERNAME']
        password = config_override['PASSWORD']
        csv_file = config_override['CSV_FILE']
        container_prefixes_str = config_override['PARENT_CONTAINER_PREFIXES']
        container_mode = config_override['CONTAINER_HIERARCHY_MODE']
    else:
        load_dotenv('config.env')
        grid_master = os.getenv('GRID_MASTER')
        network_view = os.getenv('NETWORK_VIEW', 'default')
        username = os.getenv('USERNAME')
        password = os.getenv('PASSWORD')
        csv_file = os.getenv('CSV_FILE', 'vpc_data.csv')
        container_prefixes_str = os.getenv('PARENT_CONTAINER_PREFIXES', '')
        container_mode = os.getenv('CONTAINER_HIERARCHY_MODE', 'strict').lower()
    
    # Parse container configuration
    container_prefixes = []
    if container_prefixes_str:
        try:
            container_prefixes = [int(x.strip()) for x in container_prefixes_str.split(',') if x.strip()]
        except ValueError as e:
            logger.warning(f"Invalid PARENT_CONTAINER_PREFIXES format: {e}. Using auto-detection.")
    
    # Prompt for missing values
    if not grid_master:
        grid_master = input("Enter InfoBlox Grid Master IP/hostname: ").strip()
    
    if not username:
        username = input(f"Enter InfoBlox username (default: admin): ").strip() or 'admin'
    
    if not password:
        password = getpass.getpass("Enter InfoBlox password: ")
    
    # Only prompt for network view if not overridden by command line
    if not skip_network_view_prompt:
        network_view = input(f"Enter Network View (default: {network_view}): ").strip() or network_view
    
    return grid_master, network_view, username, password, csv_file, container_prefixes, container_mode


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="AWS to InfoBlox VPC Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--csv-file', 
        default='vpc_data.csv',
        help='Path to AWS VPC CSV file (default: vpc_data.csv)'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--create-missing', 
        action='store_true',
        help='Create missing networks in InfoBlox'
    )
    
    parser.add_argument(
        '--network-view', 
        default=None,
        help='InfoBlox network view'
