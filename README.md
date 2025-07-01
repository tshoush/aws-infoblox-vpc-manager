# AWS to InfoBlox VPC Management Tool

A comprehensive solution for mapping AWS VPC data to InfoBlox Extended Attributes and managing network synchronization between AWS and InfoBlox systems.

## Overview

This tool provides functionality to:

1. **Parse AWS Tags** from CSV export data into structured format
2. **Map AWS Tags to InfoBlox Extended Attributes** with customizable mapping rules
3. **Compare AWS VPCs with InfoBlox networks** to identify discrepancies
4. **Create missing networks** in InfoBlox with proper tags/EAs
5. **Update existing networks** to sync tag differences
6. **Generate detailed reports** of comparison results and recommended actions

## Features

- **Robust Tag Parsing**: Handles complex AWS tag structures from CSV exports
- **Flexible Mapping**: Customizable AWS tag to InfoBlox EA mapping rules
- **Safe Operations**: Dry-run mode for testing before making changes
- **Comprehensive Reporting**: Detailed markdown reports with actionable insights
- **Error Handling**: Graceful handling of parsing errors and API failures
- **Logging**: Complete audit trail of all operations

## Data Structure

The tool works with AWS VPC CSV exports containing these columns:

| Column | Description | Example |
|--------|-------------|---------|
| AccountId | AWS Account ID | 007710834192 |
| Region | AWS Region | us-east-1 |
| VpcId | VPC Identifier | vpc-03380da9924618762 |
| Name | VPC Name | mi-lz-icd-core-team-hold-prod-pci-us-east-1-vpc |
| CidrBlock | Network CIDR | 10.212.224.0/23 |
| IsDefault | Default VPC flag | False |
| State | VPC State | available |
| DhcpOptionsId | DHCP Options | dopt-0bfca59f8ee68b9e1 |
| InstanceTenancy | Tenancy | default |
| AdditionalCidrBlocks | Extra CIDRs | [] |
| Tags | AWS Tags (JSON string) | [{'Key': 'environment', 'Value': 'prod'}] |

### Tag Format

AWS tags are stored as JSON strings representing lists of dictionaries:

```json
[
  {"Key": "environment", "Value": "prod"},
  {"Key": "owner", "Value": "John Doe"},
  {"Key": "project", "Value": "Web Application"}
]
```

## Installation

### Prerequisites

- Python 3.7 or higher
- Access to InfoBlox Grid Master
- InfoBlox WAPI v2.13.1 or compatible

### Setup

1. **Clone or download the tool files:**
   ```bash
   # Download all files to your working directory
   ls -la
   # Should show: aws_infoblox_vpc_manager.py, requirements.txt, config.env.template, etc.
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure InfoBlox connection:**
   ```bash
   cp config.env.template config.env
   # Edit config.env with your InfoBlox details
   ```

4. **Edit config.env:**
   ```bash
   GRID_MASTER=your.infoblox.server.com
   NETWORK_VIEW=default
   USERNAME=admin
   # PASSWORD= (leave empty to prompt securely)
   ```

## Usage

### Quick Start

1. **Run the example script to test parsing:**
   ```bash
   python example_usage.py
   ```

2. **Run the main tool:**
   ```bash
   python aws_infoblox_vpc_manager.py
   ```

### Main Tool Workflow

1. **Connection Setup**: Enter InfoBlox credentials when prompted
2. **Data Loading**: Specify path to your VPC CSV file (default: vpc_data.csv)
3. **Comparison**: Tool compares AWS VPCs with InfoBlox networks
4. **Report Generation**: Detailed markdown report shows results
5. **Action Selection**: Choose what operations to perform:
   - Create missing networks (dry run or actual)
   - Update discrepant networks (dry run or actual)
   - Both operations combined

### Available Actions

| Action | Description |
|--------|-------------|
| 1 | Create missing networks (dry run) - Preview what would be created |
| 2 | Create missing networks (actual) - Actually create networks in InfoBlox |
| 3 | Update discrepant networks (dry run) - Preview what would be updated |
| 4 | Update discrepant networks (actual) - Actually update networks in InfoBlox |
| 5 | Both create and update (dry run) - Preview all changes |
| 6 | Both create and update (actual) - Execute all changes |
| 7 | Exit - Generate report only |

## Tag Mapping

### Default Mapping Rules

The tool maps AWS tags to InfoBlox Extended Attributes using these rules:

| AWS Tag | InfoBlox EA | Description |
|---------|-------------|-------------|
| Name | aws_name | VPC name from AWS |
| environment/Environment | environment | Environment designation |
| owner/Owner | owner | Resource owner |
| project/Project | project | Project association |
| location/Location | aws_location | AWS region/location |
| cloudservice | aws_cloudservice | Cloud service type |
| createdby | aws_created_by | Creator username |
| RequestedBy/Requested_By | aws_requested_by | Requester username |
| dud | aws_dud | DUD number |
| Description | description | Resource description |
| tfc_created/tfe_created | aws_tfc_created/aws_tfe_created | Terraform creation flag |

### Custom Mapping

Modify the `map_aws_tags_to_infoblox_eas()` method in `VPCManager` class to customize mapping:

```python
tag_mapping = {
    'YourAWSTag': 'your_infoblox_ea',
    'CustomTag': 'custom_ea_name',
    # Add your custom mappings here
}
```

## Report Example

```markdown
# AWS VPC to InfoBlox Comparison Report
*Generated on 2025-06-03 17:45:00*

## Summary
- **Total VPCs Analyzed**: 23
- **Matching Networks**: 15
- **Missing Networks**: 5
- **Networks with Discrepancies**: 3
- **Processing Errors**: 0

## Missing Networks in InfoBlox
| VPC Name | CIDR | Account ID | Region | Recommended Action |
|----------|------|------------|---------|-------------------|
| mi-lz-tech-svcs-dev-us-east-1-vpc | 10.212.118.0/25 | 011528291507 | us-east-1 | 🔴 Create Network |

## Networks with Tag/EA Discrepancies
| VPC Name | CIDR | Account ID | Region | Recommended Action |
|----------|------|------------|---------|-------------------|
| mi-lz-ocp-prod-us-east-1-vpc | 10.212.252.0/23 | 047659599919 | us-east-1 | 🟡 Update EAs |
```

## Configuration Options

### Environment Variables

- **GRID_MASTER**: InfoBlox Grid Master IP/hostname
- **NETWORK_VIEW**: InfoBlox network view (default: "default")
- **USERNAME**: InfoBlox API username
- **PASSWORD**: InfoBlox API password (optional, will prompt if not set)
- **API_VERSION**: InfoBlox WAPI version (default: "v2.13.1")

### Logging

Logs are written to:
- **Console**: INFO level messages
- **File**: `aws_infoblox_vpc_manager.log` (all levels)

## Error Handling

The tool handles various error conditions:

- **CSV parsing errors**: Invalid or malformed CSV files
- **Tag parsing errors**: Malformed AWS tag JSON strings
- **InfoBlox API errors**: Connection, authentication, or API failures
- **Network validation errors**: Invalid CIDR blocks or network references

## Security Considerations

- **Passwords**: Never store passwords in config files
- **SSL Verification**: Disabled for InfoBlox (common in enterprise environments)
- **API Access**: Requires appropriate InfoBlox permissions for network management
- **Logging**: Sensitive data is not logged (passwords, etc.)

## Troubleshooting

### Common Issues

1. **"Unable to import 'pandas'"**
   ```bash
   pip install -r requirements.txt
   ```

2. **InfoBlox connection errors**
   - Verify Grid Master IP/hostname
   - Check firewall rules for HTTPS (443)
   - Confirm API credentials

3. **Tag parsing errors**
   - Check CSV format matches expected structure
   - Verify Tags column contains valid JSON

4. **Permission errors**
   - Ensure InfoBlox user has network management permissions
   - Verify network view access rights

### Debug Mode

Enable detailed logging by modifying the logging level:

```python
logging.basicConfig(level=logging.DEBUG)
```

## File Structure

```
.
├── aws_infoblox_vpc_manager.py    # Main application
├── example_usage.py               # Usage examples and testing
├── requirements.txt               # Python dependencies
├── config.env.template            # Configuration template
├── vpc_data.csv                   # Your AWS VPC export data
└── README.md                      # This documentation
```

## Example Workflow

1. **Export VPC data from AWS** to CSV format
2. **Place CSV file** in the same directory as the tool
3. **Configure InfoBlox connection** using config.env
4. **Run the tool** and review the comparison report
5. **Execute dry runs** to preview changes
6. **Apply actual changes** when satisfied with the plan

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files for detailed error information
3. Ensure all prerequisites are met
4. Verify InfoBlox connectivity and permissions

## License

This tool is provided as-is for AWS-InfoBlox integration purposes.
