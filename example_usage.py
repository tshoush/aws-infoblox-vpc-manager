#!/usr/bin/env python3
"""
Example usage script for AWS-InfoBlox VPC Manager

This script demonstrates how to use the VPCManager class to:
1. Parse AWS VPC data from CSV
2. Compare with InfoBlox networks
3. Generate reports
4. Create/update networks

Author: Generated for AWS-InfoBlox Integration
Date: June 3, 2025
"""

import pandas as pd
from aws_infoblox_vpc_manager import InfoBloxClient, VPCManager, ReportGenerator, AWSTagParser

def example_tag_parsing():
    """Example of parsing AWS tags from your CSV data"""
    print("=== AWS Tag Parsing Example ===")
    
    # Example tag string from your CSV data
    example_tags = "[{'Key': 'Name', 'Value': 'mi-lz-icd-core-team-hold-prod-pci-us-east-1-vpc'}, {'Key': 'environment', 'Value': 'prodpci'}, {'Key': 'owner', 'Value': 'S:Public Cloud Adnan Haq'}]"
    
    parser = AWSTagParser()
    parsed_tags = parser.parse_tags_from_string(example_tags)
    
    print("Original tags string:")
    print(f"  {example_tags}")
    print("\nParsed tags dictionary:")
    for key, value in parsed_tags.items():
        print(f"  {key}: {value}")
    
    return parsed_tags

def example_tag_mapping():
    """Example of mapping AWS tags to InfoBlox Extended Attributes"""
    print("\n=== AWS Tag to InfoBlox EA Mapping Example ===")
    
    # Get parsed tags from previous example
    aws_tags = {
        'Name': 'mi-lz-icd-core-team-hold-prod-pci-us-east-1-vpc',
        'environment': 'prodpci',
        'owner': 'S:Public Cloud Adnan Haq',
        'location': 'aws-us-east-1',
        'project': 'Backup Account in AWS for Cloud backup implementation',
        'createdby': 'amanj426'
    }
    
    # Create a dummy VPC manager to use the mapping function
    # (In real usage, you'd initialize with an actual InfoBlox client)
    vpc_manager = VPCManager(None)
    mapped_eas = vpc_manager.map_aws_tags_to_infoblox_eas(aws_tags)
    
    print("AWS Tags -> InfoBlox Extended Attributes mapping:")
    for aws_key, aws_value in aws_tags.items():
        ea_key = [k for k, v in mapped_eas.items() if v == aws_value]
        if ea_key:
            print(f"  {aws_key} -> {ea_key[0]}")
    
    print("\nMapped Extended Attributes:")
    for ea_key, ea_value in mapped_eas.items():
        print(f"  {ea_key}: {ea_value}")

def example_load_and_parse_vpc_data():
    """Example of loading and parsing VPC data from CSV"""
    print("\n=== VPC Data Loading and Parsing Example ===")
    
    try:
        # Load the CSV data
        df = pd.read_csv('vpc_data.csv')
        print(f"Loaded {len(df)} VPC records")
        
        # Parse tags for each VPC
        parser = AWSTagParser()
        df['ParsedTags'] = df['Tags'].apply(parser.parse_tags_from_string)
        
        # Display sample data
        print("\nSample VPC data with parsed tags:")
        for i, row in df.head(3).iterrows():
            print(f"\nVPC {i+1}:")
            print(f"  Name: {row['Name']}")
            print(f"  CIDR: {row['CidrBlock']}")
            print(f"  Account: {row['AccountId']}")
            print(f"  Region: {row['Region']}")
            print(f"  Parsed Tags: {len(row['ParsedTags'])} tags")
            
            # Show first few tags
            for j, (key, value) in enumerate(list(row['ParsedTags'].items())[:3]):
                print(f"    {key}: {value}")
            if len(row['ParsedTags']) > 3:
                print(f"    ... and {len(row['ParsedTags']) - 3} more")
        
        return df
        
    except FileNotFoundError:
        print("vpc_data.csv not found. Make sure the file exists in the current directory.")
        return None
    except Exception as e:
        print(f"Error loading VPC data: {e}")
        return None

def example_infoblox_operations_simulation():
    """Simulate InfoBlox operations without actual connection"""
    print("\n=== InfoBlox Operations Simulation ===")
    
    # This is a simulation - in real usage you'd provide actual InfoBlox credentials
    print("This example simulates InfoBlox operations.")
    print("To run with actual InfoBlox:")
    print("1. Set up your InfoBlox Grid Master")
    print("2. Create a config.env file with your credentials")
    print("3. Run the main aws_infoblox_vpc_manager.py script")
    
    # Example of what the operations would look like
    sample_comparison_results = {
        'matches': [
            {
                'vpc': {
                    'Name': 'existing-vpc',
                    'VpcId': 'vpc-12345',
                    'AccountId': '123456789',
                    'Region': 'us-east-1',
                    'CidrBlock': '10.0.0.0/16'
                },
                'cidr': '10.0.0.0/16',
                'aws_tags': {'environment': 'prod', 'team': 'network'},
                'ib_eas': {'environment': 'prod', 'team': 'network'}
            }
        ],
        'missing': [
            {
                'vpc': {
                    'Name': 'new-vpc',
                    'VpcId': 'vpc-67890',
                    'AccountId': '123456789',
                    'Region': 'us-west-2',
                    'CidrBlock': '10.1.0.0/16'
                },
                'cidr': '10.1.0.0/16',
                'aws_tags': {'environment': 'dev', 'team': 'development'},
                'mapped_eas': {'environment': 'dev', 'aws_team': 'development'}
            }
        ],
        'discrepancies': [
            {
                'vpc': {
                    'Name': 'mismatched-vpc',
                    'VpcId': 'vpc-54321',
                    'AccountId': '123456789',
                    'Region': 'us-east-1',
                    'CidrBlock': '10.2.0.0/16'
                },
                'cidr': '10.2.0.0/16',
                'aws_tags': {'environment': 'staging', 'team': 'qa'},
                'ib_eas': {'environment': 'test', 'team': 'qa'},
                'mapped_eas': {'environment': 'staging', 'aws_team': 'qa'}
            }
        ],
        'errors': []
    }
    
    # Generate a sample report
    report_gen = ReportGenerator()
    report = report_gen.generate_comparison_report(sample_comparison_results, "sample_report.md")
    
    print(f"\nGenerated sample report:")
    print("=" * 50)
    print(report[:500] + "..." if len(report) > 500 else report)

def main():
    """Run all examples"""
    print("AWS to InfoBlox VPC Manager - Usage Examples")
    print("=" * 60)
    
    # Run examples
    example_tag_parsing()
    example_tag_mapping()
    vpc_data = example_load_and_parse_vpc_data()
    example_infoblox_operations_simulation()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("\nNext steps:")
    print("1. Install required packages: pip install -r requirements.txt")
    print("2. Copy config.env.template to config.env and configure your InfoBlox settings")
    print("3. Run the main script: python aws_infoblox_vpc_manager.py")

if __name__ == "__main__":
    main()
