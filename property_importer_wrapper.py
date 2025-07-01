#!/usr/bin/env python3
"""
Wrapper to provide PropertyImporter interface using PropertyManager
"""
from prop_infoblox_import import PropertyManager
from prop_infoblox_import_base import InfoBloxClient
import pandas as pd
from typing import Dict, List, Optional


class PropertyImporter:
    """Wrapper class to provide PropertyImporter interface"""
    
    def __init__(self, infoblox_client, network_view="default", dry_run=False):
        self.infoblox_client = infoblox_client
        self.network_view = network_view
        self.dry_run = dry_run
        self.created_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.updated_count = 0
        self.manager = PropertyManager(infoblox_client)
        
    def load_property_data(self, csv_file: str) -> pd.DataFrame:
        """Load property data from CSV"""
        return self.manager.load_property_data(csv_file)
    
    def create_extended_attributes(self):
        """Create extended attributes"""
        result = self.manager.ensure_required_eas(pd.DataFrame(), dry_run=self.dry_run)
        return result
    
    def import_properties(self, csv_file: str) -> Dict:
        """Import properties from CSV file"""
        # Load data
        df = self.manager.load_property_data(csv_file)
        expanded_df = self.manager.parse_prefixes(df)
        
        # Compare with existing
        comparison = self.manager.compare_properties_with_infoblox(expanded_df, self.network_view)
        
        # Count results
        total_properties = len(df)
        total_networks = len(expanded_df)
        
        # Create missing if not dry run
        if not self.dry_run and comparison['missing']:
            creation_results = self.manager.create_missing_networks_with_overlap_check(
                comparison['missing'],
                self.network_view,
                self.dry_run
            )
            self.created_count = len(creation_results['created_networks']) + len(creation_results['created_containers'])
            self.failed_count = len(creation_results['failed'])
        else:
            self.created_count = 0
            self.failed_count = 0
        
        return {
            "total_properties": total_properties,
            "total_networks": total_networks,
            "networks_created": self.created_count
        }
    
    def generate_reports(self, output_dir: str) -> Dict[str, str]:
        """Generate reports"""
        # Simple report generation
        report_path = f"{output_dir}/property_report.txt"
        with open(report_path, 'w') as f:
            f.write("Property Import Report\n")
            f.write(f"Created: {self.created_count}\n")
            f.write(f"Failed: {self.failed_count}\n")
            f.write(f"Skipped: {self.skipped_count}\n")
        
        return {"summary": report_path}
    
    def process_property_network(self, property_data: Dict) -> bool:
        """Process a single property network"""
        try:
            # Extract network info
            network = property_data.get('Network', property_data.get('network', ''))
            
            # Create network using manager
            if not self.dry_run:
                comment = f"Property: {property_data.get('Property Name', '')}"
                extattrs = {
                    'Property_Code': property_data.get('Property Code', ''),
                    'Property_Name': property_data.get('Property Name', '')
                }
                
                self.infoblox_client.create_network(
                    network=network,
                    network_view=self.network_view,
                    comment=comment,
                    extattrs=extattrs
                )
                self.created_count += 1
            
            return True
        except Exception as e:
            self.failed_count += 1
            return False