# InfoBlox Network Import to Custom View Documentation

## Description

The `myview_import_properties.py` script is a specialized Python utility designed to import network data from CSV files into InfoBlox version 9.3 using a custom network view called "Tarig_view". This tool extends the functionality of the standard import script by adding network view management capabilities, allowing for better organization and segregation of network data within InfoBlox.

The script automatically checks if the "Tarig_view" network view exists in InfoBlox, and if not, creates it before proceeding with the network imports. This ensures that all imported networks are properly organized within the designated view, making network management more structured and efficient.

## Key Features

- **Custom Network View**: Imports all networks to the "Tarig_view" network view
- **Network View Creation**: Automatically creates the network view if it doesn't exist
- **Interactive Prompts**: Prompts for file path, InfoBlox Grid Master, username, and password with sensible defaults
- **Extended Attribute Management**: Automatically checks for and creates required extended attributes
- **Data Validation**: Validates CIDR format before attempting to import
- **Descriptive Logging**: Adds timestamps and detailed descriptions to imported networks
- **Idempotent Operation**: Updates existing networks rather than creating duplicates
- **Error Handling**: Robust error handling with informative messages

## Prerequisites

### System Requirements
- Python 3.6 or higher
- Network connectivity to the InfoBlox Grid Master
- Appropriate permissions to create network views and networks in InfoBlox

### Required Python Packages
- requests: For making API calls to InfoBlox
- pandas: For reading and processing CSV data
- ipaddress: For validating CIDR notation
- ast (standard library): For safely evaluating string representations of lists
- datetime (standard library): For timestamping imports

You can install the required third-party packages using pip:

```bash
pip install requests pandas
```

## CSV File Format

The script is designed to work with CSV files containing network information. The expected format is:

| Column    | Description                                                | Example                |
|-----------|------------------------------------------------------------|------------------------|
| site_id   | Numeric identifier mapped to an InfoBlox extended attribute | 16540968605520072     |
| m_host    | String mapped to an InfoBlox extended attribute            | IADXMP01              |
| prefixes  | List of CIDR blocks (as a string representation)           | ['10.101.224.0/22']   |

Example CSV content:
```
site_id,m_host,prefixes
16540968605520072,IADXMP01,['10.101.224.0/22']
16534423216510206,WASCTP01,['10.99.116.0/22']
16534424701980039,WASNHP01,['10.107.20.0/22']
```

## Usage Guide

### Running the Script

To run the script, simply execute it with Python:

```bash
python myview_import_properties.py
```

### Interactive Prompts

The script will prompt you for the following information:

1. CSV file path
   - Enter the path to your CSV file
   - Press Enter to use the default (`modified_properties_file.csv`)

2. InfoBlox Grid Master's name or IP address
   - Enter the hostname or IP of your InfoBlox Grid Master
   - Press Enter to use the default (192.168.1.222)

3. InfoBlox username
   - Enter your InfoBlox username
   - Press Enter to use the default (admin)

4. InfoBlox password
   - Enter your InfoBlox password
   - Press Enter to use the default (infoblox)

### Example Session

```
$ python myview_import_properties.py
Enter CSV file path [default: modified_properties_file.csv]: 
Enter InfoBlox Grid Master's name or IP address [default: 192.168.1.222]: 
Enter InfoBlox username [default: admin]: 
Enter InfoBlox password [default: infoblox]: 
Loaded 8 records from modified_properties_file.csv
Checking if network view 'Tarig_view' exists...
Creating network view 'Tarig_view'...
Successfully created network view 'Tarig_view'.
------------------------------
Found existing EA definition for 'site_id'.
Found existing EA definition for 'm_host'.
Creating network: 10.101.224.0/22 in view 'Tarig_view'...
Successfully created network: 10.101.224.0/22 in view 'Tarig_view'
------------------------------
Creating network: 10.99.116.0/22 in view 'Tarig_view'...
Successfully created network: 10.99.116.0/22 in view 'Tarig_view'
...
------------------------------
InfoBlox import process completed. Networks imported to view 'Tarig_view'.
```

## Technical Details

### Workflow

1. **Input Collection**: The script prompts for the CSV file path and InfoBlox credentials.
2. **Network View Management**:
   - Checks if the "Tarig_view" network view exists in InfoBlox.
   - If it doesn't exist, creates the network view.
3. **CSV Processing**: It reads the CSV file using pandas and processes each row.
4. **Extended Attribute Management**:
   - For each row, it checks if the required extended attributes exist in InfoBlox.
   - If they don't exist, it creates them with appropriate types and flags.
5. **Network Processing**:
   - For each CIDR in the prefixes list, it validates the format.
   - It checks if the network already exists in the "Tarig_view" network view.
   - If it exists, it updates the extended attributes and description.
   - If it doesn't exist, it creates a new network in the "Tarig_view" view with the extended attributes and description.
6. **Completion**: It provides a summary of the import process.

### Network Views in InfoBlox

Network views in InfoBlox provide a way to create multiple logical views of the network, allowing for:

- Segregation of network data for different purposes or departments
- Management of overlapping IP address spaces
- Organization of networks by function, location, or other criteria
- Simplified administration through logical grouping

The "Tarig_view" network view created by this script serves as a dedicated container for the imported networks, keeping them separate from networks in the default view.

### Extended Attributes

The script creates and manages two extended attributes in InfoBlox:

| Attribute | Type   | Flags       | Description                           |
|-----------|--------|-------------|---------------------------------------|
| site_id   | STRING | Inheritable | Stores the site_id value from the CSV |
| m_host    | STRING | Inheritable | Stores the m_host value from the CSV  |

### Network Description

Each network is created or updated with a description that includes a timestamp:

```
Imported by Property script on YYYY-MM-DD HH:MM:SS
```

This helps track when networks were imported and by which process.

## User Stories

### Story 1: Network Administrator Managing Multiple Network Domains

**User**: Alex, Network Administrator

Alex manages networks for multiple business units within a large enterprise. Each business unit needs its own logical space in InfoBlox to manage their networks independently.

**How the Script Helps**:
- Alex uses the script to import networks for a specific business unit into the "Tarig_view" network view.
- The script automatically creates the view if it doesn't exist.
- All networks for this business unit are kept separate from other units' networks.
- Alex can easily manage and report on this business unit's networks by filtering on the network view.

**Outcome**: Alex successfully maintains separate network spaces for different business units, improving organization and reducing the risk of conflicts.

### Story 2: Cloud Migration Project

**User**: Jennifer, Cloud Migration Specialist

Jennifer is working on a project to migrate on-premises infrastructure to the cloud. She needs to track which networks have been allocated for the migration in a separate view.

**How the Script Helps**:
- Jennifer exports the planned cloud network allocations to a CSV file.
- She runs the script to import these networks into the "Tarig_view" network view.
- The migration team can now easily see all cloud-allocated networks in one place.
- The extended attributes provide additional context about each network's purpose.

**Outcome**: Jennifer creates a clear, separate inventory of cloud-allocated networks, facilitating the migration process and preventing IP conflicts.

### Story 3: Test Environment Setup

**User**: Marcus, Network Engineer

Marcus needs to set up a test environment that mirrors the production network but exists in a separate logical space to prevent conflicts.

**How the Script Helps**:
- Marcus exports the production network information to a CSV file.
- He runs the script to import these networks into the "Tarig_view" network view.
- The test environment now has the same network structure as production but is logically separated.
- Marcus can make changes to the test environment without affecting production.

**Outcome**: Marcus successfully creates a test environment that mirrors production while maintaining logical separation, enabling safe testing and development.

## Security Considerations

- **SSL Verification**: The script currently disables SSL certificate verification (`verify=False`). In a production environment, you should use proper certificate validation.
- **Credential Management**: Default credentials are hardcoded in the script. For production use, consider using environment variables or a secure configuration file.
- **Access Control**: Ensure the user running the script has appropriate permissions in InfoBlox to create network views and networks.
- **Network View Permissions**: In InfoBlox, set up appropriate permissions for the "Tarig_view" network view to control who can access and modify networks within it.

## Troubleshooting Guide

If you encounter issues:

1. **Network View Creation Failures**:
   - Verify you have permissions to create network views in InfoBlox
   - Check if there are any naming restrictions or conflicts

2. **File Not Found**:
   - Verify the CSV file path is correct
   - Check file permissions

3. **Connection Issues**:
   - Ensure network connectivity to the InfoBlox Grid Master
   - Verify the hostname/IP is correct
   - Check firewall rules

4. **Authentication Failures**:
   - Verify username and password
   - Check account lockout policies

5. **API Errors**:
   - Review the console output for specific error messages
   - Check InfoBlox logs for additional details

6. **Data Format Issues**:
   - Ensure the CSV file follows the expected format
   - Verify CIDR notation is correct
