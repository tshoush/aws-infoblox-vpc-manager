#!/usr/bin/env python3
"""
Test script for overlap detection functionality
Tests the overlap detection logic without actually creating networks in InfoBlox
"""

import ipaddress
from typing import Dict, List
import pandas as pd
import ast

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
        print(f"Error checking overlap between {cidr1} and {cidr2}: {e}")
        return 'error'


def analyze_network_overlaps(networks: List[Dict]) -> Dict:
    """
    Analyze all networks for overlaps and determine which should be containers.
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
                print(f"  ✓ Network {cidr1} contains {cidr2} - marking as container")
                
            elif overlap_type == 'overlap':
                # Partial overlap - this is problematic
                result['overlaps'].append({
                    'network1': net1,
                    'network2': net2,
                    'message': f"Networks {cidr1} and {cidr2} partially overlap"
                })
                print(f"  ⚠️  Partial overlap detected between {cidr1} and {cidr2}")
    
    return result


def save_analysis_report(overlap_analysis: Dict, networks: List[Dict], csv_file: str):
    """Save the overlap analysis to a report file with proper naming convention"""
    from datetime import datetime
    
    # Generate filename: test_overlap_analysis_{timestamp}.txt
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_overlap_analysis_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"Overlap Analysis Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Source file: {csv_file}\n")
        f.write(f"Total networks analyzed: {len(networks)}\n")
        f.write("="*60 + "\n\n")
        
        if overlap_analysis['containers']:
            f.write(f"Networks to be created as containers: {len(overlap_analysis['containers'])}\n\n")
            for container_cidr in sorted(overlap_analysis['containers']):
                contained_nets = overlap_analysis['relationships'].get(container_cidr, [])
                f.write(f"Container: {container_cidr}\n")
                f.write(f"  Contains {len(contained_nets)} networks:\n")
                for net in contained_nets:
                    f.write(f"    - {net['cidr']} (Site: {net['site_id']}, Host: {net['m_host']})\n")
                f.write("\n")
        else:
            f.write("No overlapping networks detected - all can be created as regular networks\n\n")
        
        if overlap_analysis['overlaps']:
            f.write(f"\nPartial overlaps detected: {len(overlap_analysis['overlaps'])}\n")
            for overlap in overlap_analysis['overlaps']:
                f.write(f"  - {overlap['message']}\n")
    
    print(f"\n📄 Analysis report saved: {filename}")
    return filename


def test_with_csv(csv_file: str):
    """Test overlap detection with a CSV file"""
    print(f"\n{'='*60}")
    print(f"Testing with CSV file: {csv_file}")
    print(f"{'='*60}\n")
    
    # Load and parse the CSV
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} rows from CSV")
    
    # Expand prefixes
    networks = []
    for _, row in df.iterrows():
        prefixes_str = row['prefixes']
        try:
            if isinstance(prefixes_str, str):
                prefixes_list = ast.literal_eval(prefixes_str)
            else:
                prefixes_list = [prefixes_str] if prefixes_str else []
                
            for prefix in prefixes_list:
                networks.append({
                    'cidr': prefix,
                    'site_id': row['site_id'],
                    'm_host': row['m_host']
                })
        except Exception as e:
            print(f"Error parsing prefixes for site_id {row['site_id']}: {e}")
            continue
    
    print(f"Expanded to {len(networks)} networks\n")
    
    # Display all networks
    print("Networks to analyze:")
    for net in sorted(networks, key=lambda x: (int(x['cidr'].split('/')[1]), x['cidr'])):
        print(f"  - {net['cidr']} (Site: {net['site_id']}, Host: {net['m_host']})")
    
    print("\nAnalyzing overlaps...")
    overlap_analysis = analyze_network_overlaps(networks)
    
    # Report results
    print(f"\n{'='*60}")
    print("OVERLAP DETECTION RESULTS:")
    print(f"{'='*60}\n")
    
    if overlap_analysis['containers']:
        print(f"📦 Networks to be created as containers: {len(overlap_analysis['containers'])}")
        for container_cidr in sorted(overlap_analysis['containers']):
            contained_nets = overlap_analysis['relationships'].get(container_cidr, [])
            print(f"\n   Container: {container_cidr}")
            print(f"   Contains {len(contained_nets)} networks:")
            for net in contained_nets:
                print(f"      └─ {net['cidr']} (Site: {net['site_id']})")
    else:
        print("✓ No overlapping networks detected - all can be created as regular networks")
    
    if overlap_analysis['overlaps']:
        print(f"\n⚠️  PARTIAL OVERLAPS DETECTED: {len(overlap_analysis['overlaps'])}")
        for overlap in overlap_analysis['overlaps']:
            print(f"   - {overlap['message']}")
    
    # Show creation order
    print(f"\n{'='*60}")
    print("RECOMMENDED CREATION ORDER:")
    print(f"{'='*60}\n")
    
    if overlap_analysis['containers']:
        print("1. Create Containers First:")
        for container in sorted(overlap_analysis['containers']):
            print(f"   - {container} [CONTAINER]")
        
        print("\n2. Then Create Regular Networks:")
        for net in networks:
            if net['cidr'] not in overlap_analysis['containers']:
                # Find parent container if any
                parent = None
                for container in overlap_analysis['containers']:
                    if check_network_overlap(container, net['cidr']) == 'contains':
                        parent = container
                        break
                
                if parent:
                    print(f"   - {net['cidr']} → inside {parent}")
                else:
                    print(f"   - {net['cidr']} → standalone")
    else:
        print("Create all as regular networks (no specific order required)")
    
    # Save analysis report
    save_analysis_report(overlap_analysis, networks, csv_file)


def test_simple_examples():
    """Test with simple hardcoded examples"""
    print("\n" + "="*60)
    print("SIMPLE OVERLAP TESTS")
    print("="*60 + "\n")
    
    test_cases = [
        ("10.0.0.0/16", "10.0.1.0/24", "contains"),
        ("10.0.1.0/24", "10.0.0.0/16", "contained"),
        ("10.0.0.0/24", "10.0.1.0/24", "none"),
        ("10.0.0.0/23", "10.0.1.0/24", "contains"),
        ("192.168.0.0/24", "192.168.0.128/25", "contains"),
        ("10.0.0.0/24", "10.0.0.128/25", "contains"),
        ("10.0.0.0/25", "10.0.0.128/25", "none"),
    ]
    
    for cidr1, cidr2, expected in test_cases:
        result = check_network_overlap(cidr1, cidr2)
        status = "✓" if result == expected else "✗"
        print(f"{status} {cidr1} vs {cidr2}: {result} (expected: {expected})")


if __name__ == "__main__":
    # Run simple tests first
    test_simple_examples()
    
    # Test with CSV files
    import os
    
    # Try to find test CSV files
    csv_files = [
        'test_overlap_data.csv',
        'modified_properties_file.csv',
        'sdwan_gpns_prefix_report.csv'
    ]
    
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            test_with_csv(csv_file)
            break
    else:
        print("\n⚠️  No CSV files found for testing.")
        print("Create 'test_overlap_data.csv' with overlapping networks to test.")
