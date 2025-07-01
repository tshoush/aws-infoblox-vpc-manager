*Generated on June 3, 2025 at 02:50 PM EDT by Grok, powered by xAI*

## Overview
This file contains the Python script, markdown report, and Chart.js configuration for comparing AWS subnets (from a CSV or Excel file) with Infoblox subnets using WAPI v2.13.1. The comparison focuses on subnets listed in the AWS file, ensuring they exist in Infoblox within the specified network view, with tags mapped to Extensible Attributes (EAs) and comments matched. The CSV/Excel has columns `Subnet`, `Comments`, optional columns, and `Tags` (last column).

## Instructions
1. **Save This File**:
  - Copy the entire content below.
  - On your iPhone, paste into the Notes app, Files app (save as `aws_infoblox_comparison.md`), or an email to yourself.
  - Transfer to your laptop via email, AirDrop, iCloud, or USB (see options below).
2. **Extract Python Script**:
  - Copy the content of the `python` code block.
  - Paste into a text editor (e.g., VS Code, Notepad) on your laptop.
  - Save as `compare_subnets.py`.
  - Install required Python libraries: `pip install pandas requests urllib3 python-dotenv`.
3. **Set Up Configuration File (Optional)**:
  - Create a `config.env` file in the same directory as `compare_subnets.py` with:
    ```
    GRID_MASTER=192.168.1.222
    NETWORK_VIEW=default
    USERNAME=admin
    PASSWORD=infoblox
    ```
  - The script will use these if present; otherwise, it prompts with defaults.
4. **Extract Chart.js Configuration**:
  - Copy the `chartjs` code block if needed for visualization.
  - Use in a Chart.js-compatible environment (e.g., a web app).
5. **Run the Script**:
  - Update `file_path` in the script to point to your CSV/Excel file.
  - Run with `python compare_subnets.py`. If no `config.env` exists, enter grid master IP (`192.168.1.222`), network view (`default`), username (`admin`), and password (`infoblox`) when prompted.
6. **Transfer Options**:
  - **Email**: Paste this content into an email and send to yourself.
  - **AirDrop (Mac)**: Save as a file in the Files app and AirDrop to your Mac.
  - **iCloud**: Upload to iCloud Drive via Files app and download on your laptop.
  - **USB**: Connect iPhone to laptop and copy via Finder (Mac) or iTunes (Windows).

## Python Script
This script reads a CSV/Excel file with `Subnet`, `Comments`, optional columns, and `Tags` (last column), prompts for or reads Infoblox credentials and network view, queries Infoblox WAPI v2.13.1, and generates a markdown report.

```python
import pandas as pd
import requests
import json
import urllib3
from ipaddress import ip_network
import os
from dotenv import load_dotenv
import getpass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_parent_network(subnet, parent_mask=17):
   """Derive parent network (e.g., 10.10.10.0/24 -> 10.10.0.0/17)."""
   try:
       network = ip_network(subnet, strict=False)
       parent = ip_network(f"{network.network_address}/17", strict=False)
       return str(parent)
   except ValueError:
       return None

def get_infoblox_subnets(grid_master, username, password, parent_network, target_subnets, network_view):
   """Fetch specific subnets from Infoblox within a parent network and network view."""
   url = f"https://{grid_master}/wapi/v2.13.1/network?network_container={parent_network}&network_view={network_view}&_return_fields+=network,comment,extattrs"
   response = requests.get(url, auth=(username, password), verify=False)
   if response.status_code == 200:
       subnets = json.loads(response.text)
       return [s for s in subnets if s['network'] in target_subnets]
   else:
       print(f"Error fetching subnets for {parent_network} in view {network_view}: {response.status_code}")
       return []

def parse_tags(tags_str):
   """Parse AWS tags (e.g., 'env=prod,team=dev') into a dict."""
   if not tags_str or isinstance(tags_str, float):  # Handle NaN or empty
       return {}
   try:
       return dict(t.split('=') for t in str(tags_str).split(',') if '=' in t)
   except:
       return {}

def get_config():
   """Load config from .env or prompt user with defaults."""
   load_dotenv('config.env')
   grid_master = os.getenv('GRID_MASTER', '192.168.1.222')
   network_view = os.getenv('NETWORK_VIEW', 'default')
   username = os.getenv('USERNAME', 'admin')
   password = os.getenv('PASSWORD', None)  # Password not stored by default

   if not os.path.exists('config.env') or not password:
       print(f"Enter Grid Master IP (default: {grid_master}): ", end='')
       user_input = input().strip()
       grid_master = user_input if user_input else grid_master

       print(f"Enter Network View (default: {network_view}): ", end='')
       user_input = input().strip()
       network_view = user_input if user_input else network_view

       print(f"Enter Username (default: {username}): ", end='')
       user_input = input().strip()
       username = user_input if user_input else username

       print("Enter Password (default: infoblox): ", end='')
       password = getpass.getpass() if not password else password
       password = password if password else 'infoblox'

   return grid_master, network_view, username, password

def compare_subnets(file_path, grid_master, network_view, username, password, is_excel=False):
   # Read AWS data
   try:
       if is_excel:
           df_aws = pd.read_excel(file_path)
       else:
           df_aws = pd.read_csv(file_path)
   except Exception as e:
       print(f"Error reading file: {e}")
       return [], [], []

   # Ensure required columns exist
   required_cols = ['Subnet', 'Tags']
   if not all(col in df_aws.columns for col in required_cols):
       print(f"Missing required columns: {required_cols}")
       return [], [], []

   # Extract relevant columns (Subnet, Comments, Tags as last column)
   aws_subnets = {}
   for _, row in df_aws.iterrows():
       if isinstance(row['Subnet'], str):
           aws_subnets[row['Subnet']] = {
               'tags': parse_tags(row[df_aws.columns[-1]]),  # Tags is last column
               'comments': str(row.get('Comments', '')) if 'Comments' in df_aws.columns else ''
           }

   # Get parent networks for each subnet
   parent_networks = {}
   for subnet in aws_subnets:
       parent = get_parent_network(subnet)
       if parent:
           parent_networks[subnet] = parent

   # Fetch Infoblox subnets (only those in CSV)
   ib_subnets = {}
   for subnet, parent in parent_networks.items():
       subnets = get_infoblox_subnets(grid_master, username, password, parent, [subnet], network_view)
       for s in subnets:
           ib_subnets[s['network']] = {
               'extattrs': {k: v['value'] for k, v in s.get('extattrs', {}).items()},
               'comment': s.get('comment', '')
           }

   # Compare
   matches = []
   missing = []
   discrepancies = []

   for subnet, data in aws_subnets.items():
       if subnet in ib_subnets:
           ib_eas = ib_subnets[subnet]['extattrs']
           if data['tags'] == ib_eas:
               matches.append((subnet, data['tags'], ib_eas, data['comments'], ib_subnets[subnet]['comment']))
           else:
               discrepancies.append((subnet, data['tags'], ib_eas, data['comments'], ib_subnets[subnet]['comment']))
       else:
           missing.append((subnet, data['tags'], data['comments']))

   return matches, missing, discrepancies

def generate_markdown_report(matches, missing, discrepancies):
   """Generate markdown report for CSV subnets only."""
   report = [
       "# AWS and Infoblox Subnet Comparison Report",
       f"*Generated on June 3, 2025 at 02:50 PM EDT*",
       "",
       "## Overview",
       "This report compares subnets listed in an AWS-exported CSV or Excel file with subnets in Infoblox v9.3 using WAPI v2.13.1. AWS subnets are queried within their parent networks (e.g., 10.10.10.0/24 in 10.10.0.0/17) in the specified network view. All AWS subnets should exist in Infoblox, with tags mapped to Infoblox Extensible Attributes (EAs). Only subnets listed in the CSV are compared.",
       "",
       "## Methodology",
       "- **AWS Data**: Parsed from CSV/Excel with columns `Subnet`, `Comments`, optional columns, and `Tags` (last column).",
       "- **Infoblox Data**: Retrieved via WAPI v2.13.1 for parent networks in the specified network view (e.g., `/network?network_container=10.10.0.0/17&network_view=default&_return_fields+=network,comment,extattrs`).",
       "- **Comparison**: Subnets matched by CIDR; AWS tags compared to Infoblox EAs; comments included for reference.",
       "",
       "## Results",
       "",
       "### 1. Matching Subnets",
       "Subnets present in both AWS and Infoblox with consistent tags/EAs.",
       "",
       "| Subnet | AWS Tags | Infoblox EAs | AWS Comments | Infoblox Comment | Status |",
       "|--------|----------|--------------|--------------|------------------|--------|"
   ]

   for subnet, aws_tags, ib_eas, aws_comment, ib_comment in matches:
       aws_tags_str = ", ".join(f"{k}={v}" for k, v in aws_tags.items())
       ib_eas_str = ", ".join(f"{k}={v}" for k, v in ib_eas.items())
       report.append(f"| {subnet} | {aws_tags_str} | {ib_eas_str} | {aws_comment} | {ib_comment} | Match |")

   report.extend([
       "",
       "### 2. Missing Subnets in Infoblox",
       "AWS subnets not found in Infoblox.",
       "",
       "| Subnet | AWS Tags | AWS Comments |",
       "|--------|----------|--------------|"
   ])

   for subnet, aws_tags, aws_comment in missing:
       aws_tags_str = ", ".join(f"{k}={v}" for k, v in aws_tags.items())
       report.append(f"| {subnet} | {aws_tags_str} | {aws_comment} |")

   report.extend([
       "",
       "### 3. Tag/EA Discrepancies",
       "Subnets present in both but with differing tags/EAs.",
       "",
       "| Subnet | AWS Tags | Infoblox EAs | AWS Comments | Infoblox Comment |",
       "|--------|----------|--------------|--------------|------------------|"
   ])

   for subnet, aws_tags, ib_eas, aws_comment, ib_comment in discrepancies:
       aws_tags_str = ", ".join(f"{k}={v}" for k, v in aws_tags.items())
       ib_eas_str = ", ".join(f"{k}={v}" for k, v in ib_eas.items())
       report.append(f"| {subnet} | {aws_tags_str} | {ib_eas_str} | {aws_comment} | {ib_comment} |")

   report.extend([
       "",
       "## Summary",
       f"- **Total AWS Subnets**: {len(matches) + len(missing) + len(discrepancies)}",
       f"- **Matching Subnets**: {len(matches)}",
       f"- **Missing Subnets**: {len(missing)}",
       f"- **Tag/EA Discrepancies**: {len(discrepancies)}",
       "",
       "## Recommendations"
   ])

   if missing:
       report.append("- Create missing subnets in Infoblox with corresponding EAs and comments.")
   if discrepancies:
       report.append("- Update EAs in Infoblox to match AWS tags for discrepant subnets.")
   if not missing and not discrepancies:
       report.append("- No actions required; all subnets match.")

   report.append("\n---\n*Generated by Grok, powered by xAI*")
   return "\n".join(report)

# Main execution
if __name__ == "__main__":
   file_path = "aws_subnets.csv"  # or "aws_subnets.xlsx"
   is_excel = file_path.endswith('.xlsx')
   grid_master, network_view, username, password = get_config()
   matches, missing, discrepancies = compare_subnets(file_path, grid_master, network_view, username, password, is_excel)
   markdown_report = generate_markdown_report(matches, missing, discrepancies)
   print(markdown_report)
   # Optionally save the report to a file
   with open("subnet_comparison_report.md", "w") as f:
       f.write(markdown_report)