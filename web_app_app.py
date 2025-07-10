#!/usr/bin/env python3
"""
InfoBlox Management Web Interface - FastAPI Backend

This provides a modern web interface for the AWS to InfoBlox VPC Manager
and Property Import tools with a Marriott-inspired design.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import os
import sys
import subprocess
import tempfile
import shutil
from datetime import datetime
import pandas as pd
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import EA creation functionality
from api_ea_creation import add_ea_creation_endpoint, CreateEARequest

# Import our existing scripts
try:
    from aws_infoblox_vpc_manager_complete import VPCManager, InfoBloxClient
    from prop_infoblox_import import PropertyImporter
except ImportError:
    # Fallback imports if modules aren't available yet
    VPCManager = None
    PropertyImporter = None
    InfoBloxClient = None

app = FastAPI(title="InfoBlox Management Portal", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files - use absolute path
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Pydantic models
class ConfigUpdate(BaseModel):
    grid_master: str
    network_view: str
    username: str
    password: Optional[str] = None
    api_version: str = "v2.13.1"

class ImportRequest(BaseModel):
    dry_run: bool = True
    network_view: str = "default"
    sync_all: bool = False
    create_missing: bool = False
    update_discrepant: bool = False

class JobStatus(BaseModel):
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress: int
    message: str
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

# In-memory job storage (in production, use Redis or database)
jobs: Dict[str, JobStatus] = {}

# Configuration management
def load_config():
    """Load configuration from config.env"""
    config_path = Path(__file__).parent.parent / "config.env"
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    config[key] = value.strip('"').strip("'")
    return config

def save_config(config: dict):
    """Save configuration to config.env"""
    config_path = Path(__file__).parent.parent / "config.env"
    with open(config_path, 'w') as f:
        for key, value in config.items():
            f.write(f'{key}={value}\n')

# Add EA creation endpoints
add_ea_creation_endpoint(app, load_config)

# API Routes
@app.get("/")
async def root():
    """Serve the login page as the entry point"""
    return FileResponse(os.path.join(static_dir, 'login.html'))

@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return load_config()

@app.post("/api/config")
async def update_config(config: ConfigUpdate):
    """Update configuration"""
    config_dict = config.dict()
    if not config_dict.get('password'):
        # Keep existing password if not provided
        current_config = load_config()
        config_dict['password'] = current_config.get('PASSWORD', '')
    
    # Map to config.env keys
    env_config = {
        'GRID_MASTER': config_dict['grid_master'],
        'NETWORK_VIEW': config_dict['network_view'],
        'INFOBLOX_USERNAME': config_dict['username'],
        'PASSWORD': config_dict['password'],
        'API_VERSION': config_dict['api_version']
    }
    
    save_config(env_config)
    return {"message": "Configuration updated successfully"}

@app.post("/api/test-connection")
async def test_connection():
    """Test InfoBlox connection"""
    config = load_config()
    try:
        # Run the test script
        result = subprocess.run(
            [sys.executable, "../test_infoblox_connectivity.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        success = result.returncode == 0
        message = result.stdout if success else result.stderr
        
        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error testing connection: {str(e)}"
        }

@app.get("/api/network-views")
async def get_network_views():
    """Get available network views from InfoBlox"""
    config = load_config()
    try:
        import requests
        from requests.auth import HTTPBasicAuth
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Get network views from Infoblox
        response = requests.get(
            f"https://{config['GRID_MASTER']}/wapi/{config.get('API_VERSION', 'v2.13.1')}/networkview",
            auth=HTTPBasicAuth(config.get('INFOBLOX_USERNAME', config.get('USERNAME', '')), config['PASSWORD']),
            verify=False,
            timeout=5
        )
        
        if response.status_code == 200:
            views = response.json()
            # Extract just the view names
            view_names = [view['name'] for view in views]
            return {
                "success": True,
                "views": view_names,
                "current": config.get('NETWORK_VIEW', 'default')
            }
        else:
            # Return default views if API fails
            return {
                "success": False,
                "message": f"Failed to fetch network views: {response.status_code}",
                "views": ['default'],
                "current": config.get('NETWORK_VIEW', 'default')
            }
    except Exception as e:
        # Return default views if connection fails
        return {
            "success": False,
            "message": f"Error fetching network views: {str(e)}",
            "views": ['default'],
            "current": config.get('NETWORK_VIEW', 'default')
        }

@app.post("/api/aws-import")
async def aws_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: str = Form(...)
):
    """Import AWS VPC data"""
    # Parse the request JSON
    try:
        import_options = json.loads(request)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid request format")
    
    # Generate job ID
    job_id = f"aws_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Save uploaded file
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create job status
    job = JobStatus(
        job_id=job_id,
        status="pending",
        progress=0,
        message="Job queued",
        created_at=datetime.now()
    )
    jobs[job_id] = job
    
    # Add background task
    background_tasks.add_task(
        run_aws_import,
        job_id,
        file_path,
        import_options,
        temp_dir
    )
    
    return {"job_id": job_id}

@app.post("/api/property-import")
async def property_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: str = Form(...)
):
    """Import property data"""
    # Parse the request JSON
    try:
        import_options = json.loads(request)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid request format")
    
    # Generate job ID
    job_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Save uploaded file
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create job status
    job = JobStatus(
        job_id=job_id,
        status="pending",
        progress=0,
        message="Job queued",
        created_at=datetime.now()
    )
    jobs[job_id] = job
    
    # Add background task
    background_tasks.add_task(
        run_property_import,
        job_id,
        file_path,
        import_options,
        temp_dir
    )
    
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/jobs")
async def list_jobs():
    """List all jobs"""
    return list(jobs.values())

@app.get("/api/reports")
async def list_reports():
    """List available reports"""
    reports_dir = Path(__file__).parent.parent / "reports"
    reports = []
    
    if reports_dir.exists():
        for file in reports_dir.glob("*.md"):
            stats = file.stat()
            reports.append({
                "filename": file.name,
                "size": stats.st_size,
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
            })
    
    return sorted(reports, key=lambda x: x['modified'], reverse=True)

@app.get("/api/reports/{filename}")
async def download_report(filename: str):
    """Download a specific report"""
    reports_dir = Path(__file__).parent.parent / "reports"
    file_path = reports_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    
    return FileResponse(file_path, filename=filename)

@app.post("/api/analyze")
async def analyze_networks(file: UploadFile = File(...)):
    """Perform comprehensive network analysis between AWS and InfoBlox"""
    config = load_config()
    
    # Save uploaded file
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Read AWS data
        aws_df = pd.read_csv(file_path)
        
        # Connect to InfoBlox
        import requests
        from requests.auth import HTTPBasicAuth
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Get all networks from InfoBlox
        infoblox_networks = []
        try:
            response = requests.get(
                f"https://{config['GRID_MASTER']}/wapi/{config.get('API_VERSION', 'v2.13.1')}/network",
                auth=HTTPBasicAuth(config.get('INFOBLOX_USERNAME', config.get('USERNAME', '')), config['PASSWORD']),
                verify=False,
                params={
                    'network_view': config.get('NETWORK_VIEW', 'default'),
                    '_return_fields': 'network,comment,extattrs',
                    '_max_results': 10000
                }
            )
            
            if response.status_code == 200:
                infoblox_networks = response.json()
        except Exception as e:
            pass  # Continue with empty list
        
        # Analyze the data
        analysis = {
            'aws_networks': [],
            'infoblox_networks': [],
            'in_both': [],
            'missing_from_infoblox': [],
            'missing_from_aws': [],
            'attribute_differences': []
        }
        
        # Process AWS networks
        for _, row in aws_df.iterrows():
            aws_network = {
                'cidr': row.get('cidr', ''),
                'vpc_name': row.get('vpc_name', ''),
                'vpc_id': row.get('vpc_id', ''),
                'account': row.get('account', ''),
                'region': row.get('region', ''),
                'extattrs': {
                    'VPC_ID': row.get('vpc_id', ''),
                    'VPC_Name': row.get('vpc_name', ''),
                    'Account': row.get('account', ''),
                    'Region': row.get('region', '')
                }
            }
            analysis['aws_networks'].append(aws_network)
        
        # Process InfoBlox networks
        for network in infoblox_networks:
            ib_network = {
                'cidr': network.get('network', ''),
                'comment': network.get('comment', ''),
                'extattrs': network.get('extattrs', {})
            }
            analysis['infoblox_networks'].append(ib_network)
        
        # Find networks in both, missing, and with differences
        aws_cidrs = {n['cidr'] for n in analysis['aws_networks']}
        ib_cidrs = {n['cidr'] for n in analysis['infoblox_networks']}
        
        # Networks in both
        common_cidrs = aws_cidrs & ib_cidrs
        for cidr in common_cidrs:
            aws_net = next(n for n in analysis['aws_networks'] if n['cidr'] == cidr)
            ib_net = next(n for n in analysis['infoblox_networks'] if n['cidr'] == cidr)
            
            # Check for attribute differences
            differences = []
            aws_attrs = aws_net['extattrs']
            ib_attrs = ib_net['extattrs']
            
            for key in aws_attrs:
                ib_value = ib_attrs.get(key, {}).get('value', '') if isinstance(ib_attrs.get(key), dict) else ''
                if str(aws_attrs[key]) != str(ib_value):
                    differences.append({
                        'attribute': key,
                        'aws_value': aws_attrs[key],
                        'infoblox_value': ib_value
                    })
            
            network_info = {
                'cidr': cidr,
                'aws_data': aws_net,
                'infoblox_data': ib_net,
                'has_differences': len(differences) > 0,
                'differences': differences
            }
            
            analysis['in_both'].append(network_info)
            if differences:
                analysis['attribute_differences'].append(network_info)
        
        # Missing from InfoBlox
        for cidr in aws_cidrs - ib_cidrs:
            aws_net = next(n for n in analysis['aws_networks'] if n['cidr'] == cidr)
            analysis['missing_from_infoblox'].append(aws_net)
        
        # Missing from AWS
        for cidr in ib_cidrs - aws_cidrs:
            ib_net = next(n for n in analysis['infoblox_networks'] if n['cidr'] == cidr)
            analysis['missing_from_aws'].append(ib_net)
        
        # Generate summary
        analysis['summary'] = {
            'total_aws_networks': len(analysis['aws_networks']),
            'total_infoblox_networks': len(analysis['infoblox_networks']),
            'networks_in_both': len(analysis['in_both']),
            'missing_from_infoblox': len(analysis['missing_from_infoblox']),
            'missing_from_aws': len(analysis['missing_from_aws']),
            'networks_with_differences': len(analysis['attribute_differences'])
        }
        
        return analysis
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/dry-run-analysis")
async def dry_run_analysis(
    file: UploadFile = File(...),
    options: str = Form(...)
):
    """Perform detailed dry run analysis"""
    config = load_config()
    import_options = json.loads(options)
    
    # Save uploaded file
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Read AWS data
        aws_df = pd.read_csv(file_path)
        
        # Connect to InfoBlox
        import requests
        from requests.auth import HTTPBasicAuth
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        analysis = {
            'networks_to_create': [],
            'networks_to_update': [],
            'ea_mappings': {},
            'missing_eas': [],
            'conflicts': [],
            'summary': {}
        }
        
        # Get all networks from InfoBlox
        try:
            response = requests.get(
                f"https://{config['GRID_MASTER']}/wapi/{config.get('API_VERSION', 'v2.13.1')}/network",
                auth=HTTPBasicAuth(config.get('INFOBLOX_USERNAME', ''), config['PASSWORD']),
                verify=False,
                params={
                    'network_view': import_options.get('network_view', config.get('NETWORK_VIEW', 'default')),
                    '_return_fields': 'network,comment,extattrs',
                    '_max_results': 10000
                }
            )
            
            if response.status_code == 200:
                infoblox_networks = {net['network']: net for net in response.json()}
            else:
                infoblox_networks = {}
        except Exception as e:
            infoblox_networks = {}
        
        # Get all extensible attributes definitions
        try:
            ea_response = requests.get(
                f"https://{config['GRID_MASTER']}/wapi/{config.get('API_VERSION', 'v2.13.1')}/extensibleattributedef",
                auth=HTTPBasicAuth(config.get('INFOBLOX_USERNAME', ''), config['PASSWORD']),
                verify=False
            )
            
            if ea_response.status_code == 200:
                existing_eas = {ea['name']: ea for ea in ea_response.json()}
                # Also create a list for dropdown
                existing_ea_list = [{'name': ea['name'], 'type': ea.get('type', 'STRING')} 
                                   for ea in ea_response.json()]
            else:
                existing_eas = {}
                existing_ea_list = []
        except:
            existing_eas = {}
            existing_ea_list = []
        
        # Analyze each network
        for _, row in aws_df.iterrows():
            cidr = row.get('cidr', '')
            
            # AWS attributes to map
            aws_attrs = {
                'VPC_ID': row.get('vpc_id', ''),
                'VPC_Name': row.get('vpc_name', ''),
                'Account': row.get('account', ''),
                'Region': row.get('region', ''),
                'Environment': row.get('environment', ''),
                'Application': row.get('application', ''),
                'Owner': row.get('owner', ''),
                'Cost_Center': row.get('cost_center', '')
            }
            
            # Remove empty attributes
            aws_attrs = {k: v for k, v in aws_attrs.items() if v and str(v) != 'nan'}
            
            if cidr in infoblox_networks:
                # Network exists - check for updates
                ib_net = infoblox_networks[cidr]
                ib_attrs = ib_net.get('extattrs', {})
                
                updates_needed = {}
                for attr, value in aws_attrs.items():
                    ib_value = ib_attrs.get(attr, {}).get('value', '') if isinstance(ib_attrs.get(attr), dict) else ''
                    if str(value) != str(ib_value):
                        updates_needed[attr] = {
                            'aws_value': value,
                            'infoblox_value': ib_value,
                            'action': 'update' if ib_value else 'add'
                        }
                
                if updates_needed:
                    analysis['networks_to_update'].append({
                        'cidr': cidr,
                        'vpc_name': row.get('vpc_name', ''),
                        'updates': updates_needed
                    })
            else:
                # Network doesn't exist - will be created
                analysis['networks_to_create'].append({
                    'cidr': cidr,
                    'vpc_name': row.get('vpc_name', ''),
                    'attributes': aws_attrs
                })
            
            # Check for missing EAs
            for attr in aws_attrs:
                if attr not in existing_eas and attr not in analysis['missing_eas']:
                    analysis['missing_eas'].append({
                        'name': attr,
                        'suggested_type': 'STRING',
                        'description': f'AWS attribute: {attr}'
                    })
        
        # Generate summary
        analysis['summary'] = {
            'total_networks': len(aws_df),
            'networks_to_create': len(analysis['networks_to_create']),
            'networks_to_update': len(analysis['networks_to_update']),
            'missing_eas': len(analysis['missing_eas']),
            'total_changes': len(analysis['networks_to_create']) + len(analysis['networks_to_update'])
        }
        
        # Get all unique AWS tags/fields from the CSV
        aws_fields = set()
        for _, row in aws_df.iterrows():
            for col in aws_df.columns:
                if col not in ['cidr'] and pd.notna(row[col]):
                    aws_fields.add(col)
        
        # Import enhanced matching logic
        from enhanced_dry_run_analysis import generate_ea_mappings
        
        # Generate smart EA mappings
        case_sensitive = import_options.get('case_sensitive', False)
        analysis['ea_mappings'] = generate_ea_mappings(aws_fields, existing_eas, case_sensitive)
        
        # Add list of existing EAs for dropdown
        analysis['existing_eas'] = existing_ea_list
        
        # Add all discovered AWS fields
        analysis['aws_fields'] = list(aws_fields)
        
        return analysis
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Send job updates
            if job_id in jobs:
                await websocket.send_json(jobs[job_id].model_dump(mode='json'))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Background task functions
async def run_aws_import(job_id: str, file_path: str, params: dict, temp_dir: str):
    """Run AWS import in background"""
    try:
        jobs[job_id].status = "running"
        jobs[job_id].message = "Starting AWS import..."
        
        # Build command
        cmd = [sys.executable, "aws_infoblox_vpc_manager_complete.py"]
        cmd.extend(["--csv-file", file_path])
        cmd.extend(["--network-view", params['network_view']])
        
        if params['dry_run']:
            cmd.append("--dry-run")
        if params['create_missing']:
            cmd.append("--create-missing")
        # Note: update_discrepant and sync_all are not supported by aws_infoblox_vpc_manager_complete.py
        # These parameters will be ignored for now
        
        # Run the import
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path(__file__).parent.parent  # Run from the main project directory
        )
        
        # Monitor progress
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            # Update progress based on output
            line_str = line.decode().strip()
            if "Processing" in line_str:
                jobs[job_id].message = line_str
            elif "Progress:" in line_str:
                # Extract progress percentage if available
                try:
                    progress = int(line_str.split(":")[1].strip().rstrip("%"))
                    jobs[job_id].progress = progress
                except:
                    pass
        
        await process.wait()
        
        if process.returncode == 0:
            jobs[job_id].status = "completed"
            jobs[job_id].progress = 100
            jobs[job_id].message = "AWS import completed successfully"
            
            # Find generated reports
            reports_dir = Path(__file__).parent.parent / "reports"
            recent_reports = []
            if reports_dir.exists():
                for file in reports_dir.glob("*.md"):
                    if file.stat().st_mtime > jobs[job_id].created_at.timestamp():
                        recent_reports.append(file.name)
            
            jobs[job_id].result = {"reports": recent_reports}
        else:
            stderr = await process.stderr.read()
            jobs[job_id].status = "failed"
            jobs[job_id].message = f"Import failed: {stderr.decode()}"
        
    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].message = f"Error: {str(e)}"
    finally:
        jobs[job_id].completed_at = datetime.now()
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)

async def run_property_import(job_id: str, file_path: str, params: dict, temp_dir: str):
    """Run property import in background"""
    try:
        jobs[job_id].status = "running"
        jobs[job_id].message = "Starting property import..."
        
        # Build command
        cmd = [sys.executable, "prop_infoblox_import.py"]
        cmd.extend(["--csv-file", file_path])
        cmd.extend(["--network-view", params['network_view']])
        
        if params['dry_run']:
            cmd.append("--dry-run")
        if params['create_missing']:
            cmd.append("--create-missing")
        # Note: update_discrepant and sync_all are not supported by aws_infoblox_vpc_manager_complete.py
        # These parameters will be ignored for now
        
        # Run the import
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path(__file__).parent.parent  # Run from the main project directory
        )
        
        # Monitor progress
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            # Update progress based on output
            line_str = line.decode().strip()
            if "Processing" in line_str:
                jobs[job_id].message = line_str
            elif "Progress:" in line_str:
                # Extract progress percentage if available
                try:
                    progress = int(line_str.split(":")[1].strip().rstrip("%"))
                    jobs[job_id].progress = progress
                except:
                    pass
        
        await process.wait()
        
        if process.returncode == 0:
            jobs[job_id].status = "completed"
            jobs[job_id].progress = 100
            jobs[job_id].message = "Property import completed successfully"
            
            # Find generated reports
            reports_dir = Path(__file__).parent.parent / "reports"
            recent_reports = []
            if reports_dir.exists():
                for file in reports_dir.glob("*.md"):
                    if file.stat().st_mtime > jobs[job_id].created_at.timestamp():
                        recent_reports.append(file.name)
            
            jobs[job_id].result = {"reports": recent_reports}
        else:
            stderr = await process.stderr.read()
            jobs[job_id].status = "failed"
            jobs[job_id].message = f"Import failed: {stderr.decode()}"
        
    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].message = f"Error: {str(e)}"
    finally:
        jobs[job_id].completed_at = datetime.now()
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    import uvicorn
    import socket
    
    # Find available port starting from 8000
    def find_available_port(start_port=8000, max_attempts=10):
        for port in range(start_port, start_port + max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('', port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"No available ports found between {start_port} and {start_port + max_attempts}")
    
    port = find_available_port()
    print(f"Starting InfoBlox Web App on port {port}")
    print(f"Access the app at: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)