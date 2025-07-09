# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Initial setup
./setup.sh  # Unix/Linux/macOS
setup.bat   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Applications

#### Command Line Tools
```bash
# AWS VPC Import
python aws_infoblox_vpc_manager.py --help
python aws_infoblox_vpc_manager.py --dry-run
python aws_infoblox_vpc_manager.py --create-missing --network-view WedView

# Property Import
python prop_infoblox_import.py --help
python prop_infoblox_import.py --dry-run --csv-file properties.csv
```

#### Web Application
```bash
cd web_app
./run.sh  # Automatically finds available port
# Or manually:
python app.py  # Runs on port 8000-8010
```

### Testing
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_infoblox_client.py
pytest tests/test_property_importer.py
pytest tests/test_web_app.py

# Test with coverage
pytest --cov=. --cov-report=html

# Individual test scripts
python test_infoblox_connectivity.py
python test_network_view_selection.py
```

## Architecture

### Core Components

1. **InfoBloxClient** (`aws_infoblox_vpc_manager_complete.py`)
   - Handles all InfoBlox API interactions
   - Manages authentication and SSL
   - Provides network CRUD operations
   - Extended Attributes (EA) management

2. **VPCManager** (`aws_infoblox_vpc_manager_complete.py`)
   - Processes AWS VPC export data
   - Compares AWS networks with InfoBlox
   - Handles network creation and updates
   - Generates comprehensive reports

3. **PropertyImporter** (`prop_infoblox_import.py`)
   - Imports property-specific network data
   - Maps property attributes to InfoBlox EAs
   - Supports MyView integration
   - Overlap detection capabilities

4. **Web Application** (`web_app/app.py`)
   - FastAPI backend with REST API
   - WebSocket support for real-time updates
   - Background job processing
   - File upload/download handling
   - EA creation and mapping UI

### Key Design Patterns

1. **Modular Architecture**: Separate classes for distinct responsibilities
2. **Configuration Management**: Environment-based config with .env files
3. **Error Handling**: Comprehensive try-catch blocks with detailed logging
4. **Reporting**: Markdown-based reports with summary statistics
5. **Testing**: Mock objects for InfoBlox API testing

### Data Flow

1. **Input**: CSV files (AWS VPC export or property data)
2. **Processing**: Parse → Validate → Compare → Action
3. **Output**: Markdown reports, CSV summaries, InfoBlox updates

## Important Considerations

### InfoBlox Integration
- Always use HTTPS with SSL verification disabled (self-signed certs)
- API version defaults to v2.13.1
- Network views must exist before use
- Extended Attributes must be defined before assignment

### Network Creation Rules
- Larger networks created first (priority ordering)
- Container detection prevents overlaps
- Dry-run mode for safety
- Detailed logging for troubleshooting

### Web Application
- Static files served from `/static`
- WebSocket endpoints at `/ws/{job_id}`
- Background tasks for long-running operations
- Port auto-detection for conflict avoidance