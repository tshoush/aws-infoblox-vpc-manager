#!/usr/bin/env python3
"""
Enhanced Report Generator for AWS-InfoBlox VPC Manager

This module provides comprehensive reporting functionality including:
- Detailed comparison reports
- Operation summary reports
- Executive summary reports
- Tag analysis reports

Author: Generated for AWS-InfoBlox Integration
Date: June 4, 2025
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import os


class EnhancedReportGenerator:
    """Generate multiple types of detailed reports for VPC operations"""
    
    def __init__(self, output_dir: str = "reports"):
        """Initialize report generator with output directory"""
        self.output_dir = output_dir
        self.timestamp = datetime.now()
        self.timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self.date_str = self.timestamp.strftime("%Y-%m-%d")
        
        # Create reports directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def generate_all_reports(self, comparison_results: Dict, operation_results: Optional[Dict] = None, 
                           network_view: str = "default", network_creation_list: Optional[Dict] = None,
                           ea_analysis: Optional[Dict] = None) -> Dict[str, str]:
        """Generate all report types and return their filenames"""
        reports = {}
        
        # Generate comparison report
        reports['comparison'] = self.generate_comparison_report(comparison_results, network_view)
        
        # Generate executive summary
        reports['executive'] = self.generate_executive_summary(comparison_results, operation_results, network_view)
        
        # Generate tag analysis report
        reports['tag_analysis'] = self.generate_tag_analysis_report(comparison_results)
        
        # Generate network creation list report
        if network_creation_list:
            reports['network_creation'] = self.generate_network_creation_report(network_creation_list, network_view)
        
        # Generate extended attribute report
        if ea_analysis:
            reports['extended_attributes'] = self.generate_extended_attribute_report(ea_analysis)
        
        # Generate operation results report if operations were performed
        if operation_results:
            reports['operations'] = self.generate_operation_report(operation_results)
        
        # Generate master index file
        reports['index'] = self.generate_index_report(reports)
        
        return reports
    
    def generate_comparison_report(self, comparison_results: Dict, network_view: str) -> str:
        """Generate detailed comparison report with enhanced formatting"""
        filename = f"{self.output_dir}/vpc_comparison_report_{self.date_str}.md"
        
        report_lines = [
            "# AWS VPC to InfoBlox Detailed Comparison Report",
            f"*Generated on {self.timestamp_str}*",
            "",
            f"**Network View**: `{network_view}`",
            "",
            "---",
            "",
            "## 📊 Executive Summary",
            "",
            "### Overall Statistics",
            f"- **Total VPCs Analyzed**: {self._get_total_vpcs(comparison_results)}",
            f"- **✅ Matching Networks**: {len(comparison_results['matches'])}",
            f"- **🔴 Missing Networks**: {len(comparison_results['missing'])}",
            f"- **🟡 Networks with Discrepancies**: {len(comparison_results['discrepancies'])}",
            f"- **❌ Processing Errors**: {len(comparison_results['errors'])}",
            "",
            "### Sync Status",
            self._generate_sync_chart(comparison_results),
            "",
            "---",
            "",
            "## 📋 Detailed Analysis",
            ""
        ]
        
        # Matching networks section with enhanced details
        if comparison_results['matches']:
            report_lines.extend([
                "### ✅ Matching Networks",
                "> Networks that are properly synchronized between AWS and InfoBlox",
                "",
                "| # | VPC Name | CIDR Block | Account ID | Region | Environment | Owner | Status |",
                "|---|----------|------------|------------|---------|-------------|-------|--------|"
            ])
            
            for idx, match in enumerate(comparison_results['matches'], 1):
                vpc = match['vpc']
                aws_tags = match.get('aws_tags', {})
                report_lines.append(
                    f"| {idx} | {vpc['Name']} | `{match['cidr']}` | {vpc['AccountId']} | "
                    f"{vpc['Region']} | {aws_tags.get('environment', 'N/A')} | "
                    f"{aws_tags.get('owner', 'N/A')} | ✅ Synced |"
                )
            
            report_lines.append("")
        
        # Missing networks section with action items
        if comparison_results['missing']:
            report_lines.extend([
                "### 🔴 Missing Networks in InfoBlox",
                "> AWS VPCs that need to be created in InfoBlox",
                "",
                "| # | VPC Name | CIDR Block | Account ID | Region | Environment | Project | Action Required |",
                "|---|----------|------------|------------|---------|-------------|---------|-----------------|"
            ])
            
            for idx, missing in enumerate(comparison_results['missing'], 1):
                vpc = missing['vpc']
                aws_tags = missing.get('aws_tags', {})
                report_lines.append(
                    f"| {idx} | {vpc['Name']} | `{missing['cidr']}` | {vpc['AccountId']} | "
                    f"{vpc['Region']} | {aws_tags.get('environment', 'N/A')} | "
                    f"{aws_tags.get('project', 'N/A')} | 🔴 Create Network |"
                )
            
            report_lines.extend([
                "",
                "#### 🎯 Quick Actions for Missing Networks:",
                "```bash",
                f"# Create all missing networks (dry-run first)",
                f"python aws_infoblox_vpc_manager.py --network-view {network_view} --create-missing --dry-run",
                "",
                f"# Create all missing networks (actual)",
                f"python aws_infoblox_vpc_manager.py --network-view {network_view} --create-missing",
                "```",
                ""
            ])
        
        # Discrepancies section with detailed differences
        if comparison_results['discrepancies']:
            report_lines.extend([
                "### 🟡 Networks with Tag/EA Discrepancies",
                "> Networks that exist in both systems but have different tags/Extended Attributes",
                "",
                "| # | VPC Name | CIDR Block | Discrepancy Type | AWS Value | InfoBlox Value | Action |",
                "|---|----------|------------|------------------|-----------|----------------|--------|"
            ])
            
            for idx, discrepancy in enumerate(comparison_results['discrepancies'], 1):
                vpc = discrepancy['vpc']
                # Add logic to show specific tag differences
                report_lines.append(
                    f"| {idx} | {vpc['Name']} | `{discrepancy['cidr']}` | "
                    f"Tag Mismatch | Various | Various | 🟡 Update EAs |"
                )
            
            report_lines.append("")
        
        # Errors section
        if comparison_results['errors']:
            report_lines.extend([
                "### ❌ Processing Errors",
                "> VPCs that encountered errors during comparison",
                "",
                "| # | VPC ID | VPC Name | Error Message | Suggested Action |",
                "|---|--------|----------|---------------|------------------|"
            ])
            
            for idx, error in enumerate(comparison_results['errors'], 1):
                vpc = error['vpc']
                report_lines.append(
                    f"| {idx} | {vpc.get('VpcId', 'Unknown')} | {vpc.get('Name', 'Unknown')} | "
                    f"{error['error'][:50]}... | 🔍 Manual Review |"
                )
            
            report_lines.append("")
        
        # Region distribution
        report_lines.extend(self._generate_region_distribution(comparison_results))
        
        # Environment distribution
        report_lines.extend(self._generate_environment_distribution(comparison_results))
        
        # Recommendations
        report_lines.extend([
            "",
            "---",
            "",
            "## 📌 Recommendations",
            ""
        ])
        
        if comparison_results['missing']:
            report_lines.extend([
                "### 1. Create Missing Networks",
                f"- **Count**: {len(comparison_results['missing'])} networks",
                "- **Priority**: High",
                "- **Action**: Run the create command shown above",
                ""
            ])
        
        if comparison_results['discrepancies']:
            report_lines.extend([
                "### 2. Update Discrepant Networks",
                f"- **Count**: {len(comparison_results['discrepancies'])} networks",
                "- **Priority**: Medium",
                "- **Action**: Review tag differences and update as needed",
                ""
            ])
        
        if comparison_results['errors']:
            report_lines.extend([
                "### 3. Resolve Processing Errors",
                f"- **Count**: {len(comparison_results['errors'])} errors",
                "- **Priority**: High",
                "- **Action**: Review error messages and resolve issues",
                ""
            ])
        
        # Footer
        report_lines.extend([
            "---",
            "",
            f"*Report generated by AWS-InfoBlox VPC Manager on {self.timestamp_str}*",
            f"*Network View: {network_view}*"
        ])
        
        # Write report
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    def generate_executive_summary(self, comparison_results: Dict, 
                                 operation_results: Optional[Dict] = None, network_view: str = "default") -> str:
        """Generate executive summary report"""
        filename = f"{self.output_dir}/executive_summary_{self.date_str}.md"
        
        total_vpcs = self._get_total_vpcs(comparison_results)
        sync_percentage = (len(comparison_results['matches']) / total_vpcs * 100) if total_vpcs > 0 else 0
        
        report_lines = [
            "# Executive Summary - AWS to InfoBlox VPC Synchronization",
            f"*Report Date: {self.timestamp.strftime('%B %d, %Y')}*",
            "",
            "## 🎯 Key Metrics",
            "",
            f"### Overall Synchronization Status: {sync_percentage:.1f}%",
            "",
            "| Metric | Count | Percentage |",
            "|--------|-------|------------|",
            f"| Total AWS VPCs | {total_vpcs} | 100% |",
            f"| ✅ Synchronized | {len(comparison_results['matches'])} | {len(comparison_results['matches'])/total_vpcs*100:.1f}% |",
            f"| 🔴 Missing in InfoBlox | {len(comparison_results['missing'])} | {len(comparison_results['missing'])/total_vpcs*100:.1f}% |",
            f"| 🟡 Tag Discrepancies | {len(comparison_results['discrepancies'])} | {len(comparison_results['discrepancies'])/total_vpcs*100:.1f}% |",
            f"| ❌ Processing Errors | {len(comparison_results['errors'])} | {len(comparison_results['errors'])/total_vpcs*100:.1f}% |",
            "",
        ]
        
        # Add operation results if available
        if operation_results:
            report_lines.extend([
                "## 🔧 Operations Performed",
                "",
                "| Operation | Attempted | Successful | Failed |",
                "|-----------|-----------|------------|--------|"
            ])
            
            if 'create' in operation_results:
                create_stats = self._calculate_operation_stats(operation_results['create'])
                report_lines.append(
                    f"| Network Creation | {create_stats['total']} | "
                    f"{create_stats['success']} | {create_stats['failed']} |"
                )
            
            if 'update' in operation_results:
                update_stats = self._calculate_operation_stats(operation_results['update'])
                report_lines.append(
                    f"| Network Updates | {update_stats['total']} | "
                    f"{update_stats['success']} | {update_stats['failed']} |"
                )
            
            report_lines.append("")
        
        # Action items
        report_lines.extend([
            "## 📋 Action Items",
            ""
        ])
        
        if comparison_results['missing']:
            report_lines.append(f"1. **Create {len(comparison_results['missing'])} missing networks in InfoBlox**")
        
        if comparison_results['discrepancies']:
            report_lines.append(f"2. **Update {len(comparison_results['discrepancies'])} networks with tag discrepancies**")
        
        if comparison_results['errors']:
            report_lines.append(f"3. **Investigate and resolve {len(comparison_results['errors'])} processing errors**")
        
        if not any([comparison_results['missing'], comparison_results['discrepancies'], comparison_results['errors']]):
            report_lines.append("✅ **No action required** - All VPCs are fully synchronized")
        
        # Summary
        report_lines.extend([
            "",
            "## 📈 Trend Analysis",
            "",
            "| Time Period | Status |",
            "|-------------|---------|",
            f"| Current Sync Rate | {sync_percentage:.1f}% |",
            f"| Networks Requiring Action | {len(comparison_results['missing']) + len(comparison_results['discrepancies'])} |",
            f"| Critical Issues | {len(comparison_results['errors'])} |",
            "",
            "---",
            f"*Executive Summary generated on {self.timestamp_str}*"
        ])
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    def generate_tag_analysis_report(self, comparison_results: Dict) -> str:
        """Generate detailed tag analysis report"""
        filename = f"{self.output_dir}/tag_analysis_report_{self.date_str}.md"
        
        # Analyze tag usage across all VPCs
        tag_stats = self._analyze_tags(comparison_results)
        
        report_lines = [
            "# AWS VPC Tag Analysis Report",
            f"*Generated on {self.timestamp_str}*",
            "",
            "## 📊 Tag Usage Statistics",
            "",
            "### Most Common Tags",
            "",
            "| Tag Name | Usage Count | Percentage | Common Values |",
            "|----------|-------------|------------|---------------|"
        ]
        
        # Sort tags by usage
        sorted_tags = sorted(tag_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:20]
        
        for tag_name, stats in sorted_tags:
            usage_pct = stats['count'] / self._get_total_vpcs(comparison_results) * 100
            common_values = ', '.join(list(stats['values'])[:3])
            if len(stats['values']) > 3:
                common_values += f" (+{len(stats['values']) - 3} more)"
            
            report_lines.append(
                f"| {tag_name} | {stats['count']} | {usage_pct:.1f}% | {common_values} |"
            )
        
        # Tag compliance
        report_lines.extend([
            "",
            "## 🏷️ Tag Compliance Analysis",
            "",
            "### Required Tags Coverage",
            "",
            "| Required Tag | Coverage | Missing From |",
            "|--------------|----------|--------------|"
        ])
        
        required_tags = ['Name', 'environment', 'owner', 'project']
        for tag in required_tags:
            if tag in tag_stats:
                coverage = tag_stats[tag]['count'] / self._get_total_vpcs(comparison_results) * 100
                missing = self._get_total_vpcs(comparison_results) - tag_stats[tag]['count']
                report_lines.append(f"| {tag} | {coverage:.1f}% | {missing} VPCs |")
            else:
                report_lines.append(f"| {tag} | 0% | All VPCs |")
        
        # Environment distribution
        report_lines.extend([
            "",
            "## 🌍 Environment Distribution",
            "",
            "| Environment | VPC Count | Percentage |",
            "|-------------|-----------|------------|"
        ])
        
        if 'environment' in tag_stats:
            env_total = sum(tag_stats['environment']['value_counts'].values())
            for env, count in sorted(tag_stats['environment']['value_counts'].items(), 
                                    key=lambda x: x[1], reverse=True):
                pct = count / env_total * 100
                report_lines.append(f"| {env} | {count} | {pct:.1f}% |")
        
        report_lines.extend([
            "",
            "---",
            f"*Tag Analysis Report generated on {self.timestamp_str}*"
        ])
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    def generate_operation_report(self, operation_results: Dict) -> str:
        """Generate detailed operation results report"""
        filename = f"{self.output_dir}/operation_results_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        
        report_lines = [
            "# InfoBlox Operation Results Report",
            f"*Executed on {self.timestamp_str}*",
            "",
            "## 🚀 Operation Summary",
            ""
        ]
        
        # Create operations
        if 'create' in operation_results:
            create_results = operation_results['create']
            create_stats = self._calculate_operation_stats(create_results)
            
            report_lines.extend([
                "### Network Creation Operations",
                "",
                f"- **Total Attempted**: {create_stats['total']}",
                f"- **✅ Successful**: {create_stats['success']}",
                f"- **❌ Failed**: {create_stats['failed']}",
                f"- **Success Rate**: {create_stats['success_rate']:.1f}%",
                ""
            ])
            
            if create_stats['success'] > 0:
                report_lines.extend([
                    "#### Successfully Created Networks:",
                    "",
                    "| # | Network CIDR | Comment | Status |",
                    "|---|--------------|---------|--------|"
                ])
                
                for idx, result in enumerate([r for r in create_results if r.get('action') == 'created'], 1):
                    report_lines.append(
                        f"| {idx} | `{result['cidr']}` | Created | ✅ |"
                    )
                
                report_lines.append("")
            
            if create_stats['failed'] > 0:
                report_lines.extend([
                    "#### Failed Creation Attempts:",
                    "",
                    "| # | Network CIDR | Error Message | Action Required |",
                    "|---|--------------|---------------|-----------------|"
                ])
                
                for idx, result in enumerate([r for r in create_results if r.get('action') == 'error'], 1):
                    error_msg = result.get('error', 'Unknown error')[:50]
                    report_lines.append(
                        f"| {idx} | `{result['cidr']}` | {error_msg}... | Review error |"
                    )
                
                report_lines.append("")
        
        # Update operations
        if 'update' in operation_results:
            update_results = operation_results['update']
            update_stats = self._calculate_operation_stats(update_results)
            
            report_lines.extend([
                "### Network Update Operations",
                "",
                f"- **Total Attempted**: {update_stats['total']}",
                f"- **✅ Successful**: {update_stats['success']}",
                f"- **❌ Failed**: {update_stats['failed']}",
                f"- **Success Rate**: {update_stats['success_rate']:.1f}%",
                ""
            ])
        
        # Recommendations
        report_lines.extend([
            "## 💡 Post-Operation Recommendations",
            ""
        ])
        
        any_failures = False
        if 'create' in operation_results:
            if self._calculate_operation_stats(operation_results['create'])['failed'] > 0:
                any_failures = True
                report_lines.append("1. **Review failed network creations** - Check error messages and resolve issues")
        
        if 'update' in operation_results:
            if self._calculate_operation_stats(operation_results['update'])['failed'] > 0:
                any_failures = True
                report_lines.append("2. **Review failed network updates** - Verify permissions and data validity")
        
        if not any_failures:
            report_lines.append("✅ **All operations completed successfully!**")
        
        report_lines.extend([
            "",
            "---",
            f"*Operation Results Report generated on {self.timestamp_str}*"
        ])
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    def generate_network_creation_report(self, network_creation_list: Dict, network_view: str) -> str:
        """Generate detailed network creation list report"""
        filename = f"{self.output_dir}/network_creation_list_{self.date_str}.md"
        
        report_lines = [
            "# Network Creation List Report",
            f"*Generated on {self.timestamp_str}*",
            "",
            f"**Network View**: `{network_view}`",
            "",
            "## 📋 Summary",
            "",
            f"- **Total Networks to Create**: {network_creation_list['total_count']}",
            f"- **Required Extended Attributes**: {len(network_creation_list['required_eas'])}",
            f"- **Regions Involved**: {len(network_creation_list['summary_by_region'])}",
            f"- **AWS Accounts**: {len(network_creation_list['summary_by_account'])}",
            f"- **Environments**: {len(network_creation_list['summary_by_environment'])}",
            "",
            "## 🌍 Distribution by Region",
            "",
            "| Region | Networks | Percentage |",
            "|--------|----------|------------|"
        ]
        
        total = network_creation_list['total_count']
        for region, count in sorted(network_creation_list['summary_by_region'].items(), 
                                   key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            report_lines.append(f"| {region} | {count} | {pct:.1f}% |")
        
        # Environment distribution
        report_lines.extend([
            "",
            "## 🏗️ Distribution by Environment",
            "",
            "| Environment | Networks | Percentage |",
            "|-------------|----------|------------|"
        ])
        
        for env, count in sorted(network_creation_list['summary_by_environment'].items(), 
                                key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            report_lines.append(f"| {env} | {count} | {pct:.1f}% |")
        
        # Account distribution
        report_lines.extend([
            "",
            "## 🏢 Distribution by AWS Account",
            "",
            "| Account ID | Networks | Percentage |",
            "|------------|----------|------------|"
        ])
        
        for account, count in sorted(network_creation_list['summary_by_account'].items(), 
                                    key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            report_lines.append(f"| {account} | {count} | {pct:.1f}% |")
        
        # Required Extended Attributes
        report_lines.extend([
            "",
            "## 🏷️ Required Extended Attributes",
            "",
            "The following Extended Attributes will be needed in InfoBlox:",
            ""
        ])
        
        for ea in network_creation_list['required_eas']:
            report_lines.append(f"- `{ea}`")
        
        # Detailed network list
        report_lines.extend([
            "",
            "## 📋 Detailed Network Creation List",
            "",
            "| Priority | CIDR Block | VPC Name | Account | Region | Environment | State |",
            "|----------|------------|----------|---------|--------|-------------|-------|"
        ])
        
        for network in network_creation_list['networks_to_create']:
            env = network['aws_tags'].get('environment', 
                                        network['aws_tags'].get('Environment', 'unknown'))
            report_lines.append(
                f"| {network['priority']} | `{network['cidr']}` | {network['vpc_name']} | "
                f"{network['account_id']} | {network['region']} | {env} | {network['state']} |"
            )
        
        # Quick creation commands
        report_lines.extend([
            "",
            "## 🚀 Quick Actions",
            "",
            "### Create All Networks (Dry Run)",
            "```bash",
            f"python aws_infoblox_vpc_manager.py --network-view {network_view} --create-missing --dry-run",
            "```",
            "",
            "### Create All Networks (Execute)",
            "```bash",
            f"python aws_infoblox_vpc_manager.py --network-view {network_view} --create-missing",
            "```",
            "",
            "### Create by Priority (High Priority First)",
            "Create production and staging environments first:",
            "```bash",
            "# Filter by environment in your CSV if needed",
            f"python aws_infoblox_vpc_manager.py --network-view {network_view} --create-missing --dry-run",
            "```",
            "",
            "---",
            f"*Network Creation List generated on {self.timestamp_str}*"
        ])
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    def generate_extended_attribute_report(self, ea_analysis: Dict) -> str:
        """Generate Extended Attribute analysis and status report"""
        filename = f"{self.output_dir}/extended_attributes_{self.date_str}.md"
        
        report_lines = [
            "# Extended Attributes Analysis Report",
            f"*Generated on {self.timestamp_str}*",
            "",
            "## 📊 Extended Attributes Overview",
            ""
        ]
        
        if ea_analysis['action'] == 'dry_run':
            report_lines.extend([
                f"- **Required Extended Attributes**: {len(ea_analysis['required_eas'])}",
                f"- **Currently Existing in InfoBlox**: {len(ea_analysis['existing_eas'])}",
                f"- **Missing (Need to Create)**: {len(ea_analysis['missing_eas'])}",
                "",
                "## 🔍 Analysis Results (Dry Run)",
                "",
                "### ✅ Existing Extended Attributes",
                ""
            ])
            
            if ea_analysis['existing_eas']:
                for ea in sorted(ea_analysis['existing_eas']):
                    if ea in ea_analysis['required_eas']:
                        report_lines.append(f"- `{ea}` ✅")
            else:
                report_lines.append("*No existing Extended Attributes found*")
            
            report_lines.extend([
                "",
                "### 🔴 Missing Extended Attributes",
                ""
            ])
            
            if ea_analysis['missing_eas']:
                for ea in sorted(ea_analysis['missing_eas']):
                    report_lines.append(f"- `{ea}` ❌ (needs to be created)")
            else:
                report_lines.append("✅ *All required Extended Attributes already exist*")
            
        else:  # action == 'ensured'
            report_lines.extend([
                f"- **Total Required Extended Attributes**: {len(ea_analysis['required_eas'])}",
                f"- **Created in this session**: {ea_analysis['created_count']}",
                f"- **Already existed**: {ea_analysis['existing_count']}",
                "",
                "## ✅ Extended Attributes Status",
                ""
            ])
            
            for ea_name, status in sorted(ea_analysis['ea_results'].items()):
                if status == 'created':
                    report_lines.append(f"- `{ea_name}` 🆕 Created")
                else:
                    report_lines.append(f"- `{ea_name}` ✅ Already existed")
        
        # Required EAs details
        report_lines.extend([
            "",
            "## 📋 Complete List of Required Extended Attributes",
            "",
            "| EA Name | Description | Data Type | Purpose |",
            "|---------|-------------|-----------|---------|"
        ])
        
        ea_descriptions = {
            'aws_name': 'AWS VPC Name', 
            'environment': 'Environment (prod/staging/test/dev)',
            'owner': 'Resource Owner',
            'project': 'Project Name',
            'aws_location': 'AWS Region/Location',
            'aws_cloudservice': 'AWS Cloud Service Type',
            'aws_created_by': 'Created By User',
            'aws_requested_by': 'Requested By User',
            'aws_dud': 'DUD Number',
            'aws_account_id': 'AWS Account ID',
            'aws_region': 'AWS Region',
            'aws_vpc_id': 'AWS VPC ID',
            'description': 'VPC Description',
            'aws_tfc_created': 'Terraform Cloud Created Flag',
            'aws_tfe_created': 'Terraform Enterprise Created Flag'
        }
        
        for ea in sorted(ea_analysis['required_eas']):
            description = ea_descriptions.get(ea, 'AWS tag mapping')
            report_lines.append(f"| `{ea}` | {description} | STRING | AWS Tag Mapping |")
        
        # Recommendations
        report_lines.extend([
            "",
            "## 💡 Recommendations",
            ""
        ])
        
        if ea_analysis['action'] == 'dry_run' and ea_analysis['missing_eas']:
            report_lines.extend([
                "### ⚠️ Missing Extended Attributes Need to be Created",
                "",
                f"**{len(ea_analysis['missing_eas'])} Extended Attributes** must be created in InfoBlox before networks can be successfully created.",
                "",
                "#### 📋 Complete List of Extended Attributes to Create:",
                "",
                "| EA Name | Data Type | Comment | Status |",
                "|---------|-----------|---------|--------|"
            ])
            
            for ea in sorted(ea_analysis['missing_eas']):
                ea_descriptions = {
                    'aws_name': 'AWS VPC Name', 
                    'environment': 'Environment (prod/staging/test/dev)',
                    'owner': 'Resource Owner',
                    'project': 'Project Name',
                    'aws_location': 'AWS Region/Location',
                    'aws_cloudservice': 'AWS Cloud Service Type',
                    'aws_created_by': 'Created By User',
                    'aws_requested_by': 'Requested By User',
                    'aws_dud': 'DUD Number',
                    'aws_account_id': 'AWS Account ID',
                    'aws_region': 'AWS Region',
                    'aws_vpc_id': 'AWS VPC ID',
                    'description': 'VPC Description',
                    'aws_tfc_created': 'Terraform Cloud Created Flag',
                    'aws_tfe_created': 'Terraform Enterprise Created Flag'
                }
                description = ea_descriptions.get(ea, 'AWS tag mapping')
                report_lines.append(f"| `{ea}` | STRING | {description} | ❌ Missing |")
            
            report_lines.extend([
                "",
                "#### 🚀 Automatic Creation Commands:",
                "",
                "**Option 1: Automatic Creation (Recommended)**",
                "```bash",
                "# This will automatically create all missing EAs before creating networks:",
                "python aws_infoblox_vpc_manager.py --create-missing",
                "```",
                "",
                "**Option 2: Manual Creation in InfoBlox GUI**",
                "1. Log into InfoBlox Grid Manager",
                "2. Navigate to Administration → Extensible Attributes",
                "3. Click 'Add' and create each EA with these settings:",
                "   - **Data Type**: STRING",
                "   - **Default Value**: (leave empty)",
                "   - **Comment**: Use descriptions from table above",
                "",
                f"**⚠️ Important**: All {len(ea_analysis['missing_eas'])} Extended Attributes must be created before network creation will succeed."
            ])
        elif ea_analysis['action'] == 'ensured':
            if ea_analysis['created_count'] > 0:
                report_lines.extend([
                    "### Extended Attributes Successfully Created",
                    "",
                    f"✅ {ea_analysis['created_count']} new Extended Attributes were created",
                    f"✅ {ea_analysis['existing_count']} Extended Attributes already existed",
                    "",
                    "Your InfoBlox system is now ready for network creation with proper Extended Attributes."
                ])
            else:
                report_lines.append("✅ **All required Extended Attributes already existed** - no action needed")
        
        # Best practices
        report_lines.extend([
            "",
            "## 📚 Extended Attributes Best Practices",
            "",
            "### Naming Convention",
            "- Use lowercase with underscores: `aws_vpc_id`",
            "- Prefix AWS-specific attributes with `aws_`",
            "- Keep names descriptive but concise",
            "",
            "### Data Types",
            "- Use STRING for most AWS tag values",
            "- Consider ENUM for standardized values (environments)",
            "- Use appropriate length limits for values",
            "",
            "### Maintenance",
            "- Regularly review unused Extended Attributes",
            "- Document the purpose of each attribute",
            "- Consider archiving obsolete attributes",
            "",
            "---",
            f"*Extended Attributes Report generated on {self.timestamp_str}*"
        ])
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    def generate_index_report(self, reports: Dict[str, str]) -> str:
        """Generate index file linking to all reports"""
        filename = f"{self.output_dir}/index.md"
        
        report_lines = [
            "# AWS-InfoBlox VPC Reports Index",
            f"*Generated on {self.timestamp_str}*",
            "",
            "## 📁 Available Reports",
            ""
        ]
        
        report_descriptions = {
            'executive': '📊 Executive Summary - High-level overview and metrics',
            'comparison': '🔍 Detailed Comparison Report - Full VPC comparison analysis',
            'tag_analysis': '🏷️ Tag Analysis Report - AWS tag usage and compliance',
            'network_creation': '📋 Network Creation List - Prioritized list of networks to create',
            'extended_attributes': '🏷️ Extended Attributes Report - EA analysis and status',
            'operations': '🚀 Operation Results - Results of create/update operations'
        }
        
        for report_type, filepath in reports.items():
            if report_type != 'index' and os.path.exists(filepath):
                filename_only = os.path.basename(filepath)
                description = report_descriptions.get(report_type, 'Report')
                report_lines.append(f"- [{description}](./{filename_only})")
        
        report_lines.extend([
            "",
            "## 🔗 Quick Links",
            "",
            "- [AWS-InfoBlox VPC Manager Documentation](../README.md)",
            "- [Quick Start Guide](../QUICK_START.md)",
            "",
            "---",
            f"*Report index generated on {self.timestamp_str}*"
        ])
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename
    
    # Helper methods
    def _get_total_vpcs(self, comparison_results: Dict) -> int:
        """Get total number of VPCs analyzed"""
        return (len(comparison_results.get('matches', [])) + 
                len(comparison_results.get('missing', [])) + 
                len(comparison_results.get('discrepancies', [])) + 
                len(comparison_results.get('errors', [])))
    
    def _generate_sync_chart(self, comparison_results: Dict) -> str:
        """Generate ASCII sync status chart"""
        total = self._get_total_vpcs(comparison_results)
        if total == 0:
            return "No VPCs analyzed"
        
        matches_pct = len(comparison_results['matches']) / total * 100
        missing_pct = len(comparison_results['missing']) / total * 100
        discrepancies_pct = len(comparison_results['discrepancies']) / total * 100
        errors_pct = len(comparison_results['errors']) / total * 100
        
        chart = "```\n"
        chart += "Sync Status Distribution:\n"
        chart += f"✅ Synced      : {'█' * int(matches_pct/2)} {matches_pct:.1f}%\n"
        chart += f"🔴 Missing     : {'█' * int(missing_pct/2)} {missing_pct:.1f}%\n"
        chart += f"🟡 Discrepant  : {'█' * int(discrepancies_pct/2)} {discrepancies_pct:.1f}%\n"
        chart += f"❌ Errors      : {'█' * int(errors_pct/2)} {errors_pct:.1f}%\n"
        chart += "```"
        
        return chart
    
    def _generate_region_distribution(self, comparison_results: Dict) -> List[str]:
        """Generate region distribution analysis"""
        region_counts = {}
        
        for category in ['matches', 'missing', 'discrepancies']:
            for item in comparison_results.get(category, []):
                region = item['vpc'].get('Region', 'Unknown')
                region_counts[region] = region_counts.get(region, 0) + 1
        
        if not region_counts:
            return []
        
        lines = [
            "",
            "## 🌎 Regional Distribution",
            "",
            "| AWS Region | VPC Count | Percentage |",
            "|------------|-----------|------------|"
        ]
        
        total_with_region = sum(region_counts.values())
        for region, count in sorted(region_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_with_region * 100
            lines.append(f"| {region} | {count} | {pct:.1f}% |")
        
        return lines
    
    def _generate_environment_distribution(self, comparison_results: Dict) -> List[str]:
        """Generate environment distribution analysis"""
        env_counts = {}
        
        for category in ['matches', 'missing', 'discrepancies']:
            for item in comparison_results.get(category, []):
                aws_tags = item.get('aws_tags', {})
                env = aws_tags.get('environment', 'Unknown')
                env_counts[env] = env_counts.get(env, 0) + 1
        
        if not env_counts:
            return []
        
        lines = [
            "",
            "## 🏗️ Environment Distribution",
            "",
            "| Environment | VPC Count | Percentage |",
            "|-------------|-----------|------------|"
        ]
        
        total_with_env = sum(env_counts.values())
        for env, count in sorted(env_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_with_env * 100
            lines.append(f"| {env} | {count} | {pct:.1f}% |")
        
        return lines
    
    def _analyze_tags(self, comparison_results: Dict) -> Dict:
        """Analyze tag usage across all VPCs"""
        tag_stats = {}
        
        for category in ['matches', 'missing', 'discrepancies']:
            for item in comparison_results.get(category, []):
                aws_tags = item.get('aws_tags', {})
                for tag_name, tag_value in aws_tags.items():
                    if tag_name not in tag_stats:
                        tag_stats[tag_name] = {
                            'count': 0,
                            'values': set(),
                            'value_counts': {}
                        }
                    tag_stats[tag_name]['count'] += 1
                    tag_stats[tag_name]['values'].add(str(tag_value)[:50])  # Limit value length
                    
                    # Count occurrences of each value
                    value_key = str(tag_value)
                    if value_key not in tag_stats[tag_name]['value_counts']:
                        tag_stats[tag_name]['value_counts'][value_key] = 0
                    tag_stats[tag_name]['value_counts'][value_key] += 1
        
        return tag_stats
    
    def _calculate_operation_stats(self, operation_results: List[Dict]) -> Dict:
        """Calculate statistics for operation results"""
        total = len(operation_results)
        success = sum(1 for r in operation_results if r.get('action') in ['created', 'updated'])
        failed = sum(1 for r in operation_results if r.get('action') == 'error')
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': (success / total * 100) if total > 0 else 0
        }


if __name__ == "__main__":
    # Example usage
    print("Enhanced Report Generator Module")
    print("This module is imported by aws_infoblox_vpc_manager.py")
    print("It generates comprehensive markdown reports for VPC operations")
