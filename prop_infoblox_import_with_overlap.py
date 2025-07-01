#!/usr/bin/env python3
"""
Properties File to InfoBlox Network Import Tool with Overlap Detection

Enhanced version that detects overlapping networks and automatically
creates network containers for larger networks when overlaps are found.

Features:
1. Overlap detection between networks
2. Automatic container creation for larger overlapping networks
3. Hierarchical network creation (containers -> networks)
4. Detailed dry-run reporting
5. All original features preserved

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


class PropertyManager:
    """Enhanced Property Manager with overlap detection and container creation"""
    
    def __init__(self, infoblox_client):
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
    
    def create_networks_with_overlap_handling(self, missing_networks: List[Dict], 
                                            network_view: str = "default", 
                                            dry_run: bool = False) -> List[Dict]:
        """
        Create missing networks with overlap detection and container creation.
        """
        results = []
        
        # Analyze overlaps
        overlap_analysis = analyze_network_overlaps(missing_networks)
        
        # Report overlap analysis
        if overlap_analysis['containers']:
            print(f"\n🔍 OVERLAP DETECTION RESULTS:")
            print(f"   📦 Networks to be created as containers: {len(overlap_analysis['containers'])}")
            for container_cidr in sorted(overlap_analysis['containers']):
                contained_count = len(overlap_analysis['relationships'].get(container_cidr, []))
                print(f"      - {container_cidr} (contains {contained_count} networks)")
        
        if overlap_analysis['overlaps']:
            print(f"\n⚠️  PARTIAL OVERLAPS DETECTED:")
            for overlap in overlap_analysis['overlaps']:
                print(f"   - {overlap['message']}")
        
        # Track what we've created
        created_containers = set()
        created_networks = set()
        
        # First, create all containers
        if overlap_analysis['containers']:
            print(f"\n📦 CREATING NETWORK CONTAINERS:")
            
            for item in missing_networks:
                cidr = item['cidr']
                if cidr not in overlap_analysis['containers']:
                    continue
                    
                site_id = item['site_id']
                m_host = item['m_host']
                mapped_eas = item['mapped_eas']
                
                try:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would create network container: {cidr} (site_id: {site_id})")
                        results.append({
                            'cidr': cidr,
                            'site_id': site_id,
                            'm_host': m_host,
                            'action': 'would_create_container',
                            'result': 'success',
                            'contained_networks': len(overlap_analysis['relationships'].get(cidr, []))
                        })
                        created_containers.add(cidr)
                    else:
                        # Create as network container
                        comment = f"Property Network Container: {m_host} (Site ID: {site_id})"
                        result = self.ib_client.create_network_container(
                            cidr=cidr,
                            network_view=network_view,
                            comment=comment,
                            extattrs=mapped_eas
                        )
                        
                        logger.info(f"Created network container: {cidr} (site_id: {site_id})")
                        results.append({
                            'cidr': cidr,
                            'site_id': site_id,
                            'm_host': m_host,
                            'action': 'created_container',
                            'result': 'success',
                            'ref': result,
                            'contained_networks': len(overlap_analysis['relationships'].get(cidr, []))
                        })
                        created_containers.add(cidr)
                        
                except Exception as e:
                    logger.error(f"Failed to create container {cidr}: {e}")
                    results.append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'error_container',
                        'error': str(e),
                        'category': 'container_creation'
                    })
        
        # Then create regular networks (that aren't containers)
        print(f"\n🌐 CREATING REGULAR NETWORKS:")
        
        for item in missing_networks:
            cidr = item['cidr']
            if cidr in created_containers:
                continue  # Already created as container
                
            site_id = item['site_id']
            m_host = item['m_host']
            mapped_eas = item['mapped_eas']
            
            # Check if this network is contained by any container
            parent_container = None
            for container_cidr in overlap_analysis['containers']:
                if check_network_overlap(container_cidr, cidr) == 'contains':
                    parent_container = container_cidr
                    break
            
            try:
                if dry_run:
                    action = 'would_create'
                    if parent_container:
                        action = 'would_create_in_container'
                    
                    logger.info(f"[DRY RUN] Would create network: {cidr} (site_id: {site_id})")
                    if parent_container:
                        logger.info(f"  └─ Inside container: {parent_container}")
                    
                    results.append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': action,
                        'result': 'success',
                        'parent_container': parent_container
                    })
                else:
                    # Create the network
                    comment = f"Property Network: {m_host} (Site ID: {site_id})"
                    if parent_container:
                        comment += f" [Container: {parent_container}]"
                    
                    result = self.ib_client.create_network(
                        cidr=cidr,
                        network_view=network_view,
                        comment=comment,
                        extattrs=mapped_eas
                    )
                    
                    logger.info(f"Created network: {cidr} (site_id: {site_id})")
                    if parent_container:
                        logger.info(f"  └─ Inside container: {parent_container}")
                    
                    results.append({
                        'cidr': cidr,
                        'site_id': site_id,
                        'm_host': m_host,
                        'action': 'created' if not parent_container else 'created_in_container',
                        'result': 'success',
                        'ref': result,
                        'parent_container': parent_container
                    })
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to create network {cidr}: {error_msg}")
                
                # Categorize the error
                category = 'unknown'
                if 'overlap' in error_msg.lower():
                    category = 'overlap'
                elif 'permission' in error_msg.lower():
                    category = 'permission'
                
                results.append({
                    'cidr': cidr,
                    'site_id': site_id,
                    'm_host': m_host,
                    'action': 'error',
                    'error': error_msg,
                    'category': category,
                    'parent_container': parent_container
                })
        
        # Generate enhanced status report
        self._generate_overlap_aware_status_report(results, overlap_analysis, dry_run)
        
        return results
    
    def _generate_overlap_aware_status_report(self, results: List[Dict], 
                                            overlap_analysis: Dict, 
                                            dry_run: bool):
        """Generate status report with overlap information"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"property_network_creation_overlap_report_{timestamp}.csv"
        
        data = []
        for result in results:
            data.append({
                'CIDR': result['cidr'],
                'Site_ID': result.get('site_id', ''),
                'M_Host': result.get('m_host', ''),
                'Action': result['action'],
                'Result': result.get('result', 'N/A'),
                'Type': 'Container' if 'container' in result['action'] else 'Network',
                'Parent_Container': result.get('parent_container', ''),
                'Contained_Networks': result.get('contained_networks', 0),
                'Error': result.get('error', ''),
                'Error_Category': result.get('category', '')
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Generated overlap-aware network creation report: {filename}")
        
        # Also generate a summary report
        summary_filename = f"overlap_analysis_summary_{timestamp}.txt"
        with open(summary_filename, 'w') as f:
            f.write(f"Network Overlap Analysis Summary\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n\n")
            
            f.write(f"Networks to be created as containers: {len(overlap_analysis['containers'])}\n")
            for container in sorted(overlap_analysis['containers']):
                contained = overlap_analysis['relationships'].get(container, [])
                f.write(f"  - {container} (contains {len(contained)} networks)\n")
                for net in contained:
                    f.write(f"    └─ {net['cidr']} (Site: {net['site_id']})\n")
            
            if overlap_analysis['overlaps']:
                f.write(f"\nPartial overlaps detected: {len(overlap_analysis['overlaps'])}\n")
                for overlap in overlap_analysis['overlaps']:
                    f.write(f"  - {overlap['message']}\n")
            
            f.write(f"\nTotal operations:\n")
            container_ops = len([r for r in results if 'container' in r['action']])
            network_ops = len([r for r in results if 'container' not in r['action']])
            f.write(f"  - Container operations: {container_ops}\n")
            f.write(f"  - Network operations: {network_ops}\n")
            f.write(f"  - Total: {len(results)}\n")
        
        logger.info(f"Generated overlap analysis summary: {summary_filename}")


# Add the create_network_container method to InfoBloxClient
def create_network_container(self, cidr: str, network_view: str = "default", 
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
        response = self._make_request('POST', 'networkcontainer', data=data)
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


# Import all the other necessary functions and classes from the original file
# (parse_arguments, show_and_edit_config, get_config, InfoBloxClient, etc.)
# For brevity, I'm showing the key modifications. The rest remains the same.
