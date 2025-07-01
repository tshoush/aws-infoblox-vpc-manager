"""
Tests for Web Application (FastAPI)
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from pathlib import Path
import sys
import asyncio
from fastapi.testclient import TestClient
import tempfile

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web_app.app import app, jobs, load_config, save_config


class TestWebApp:
    """Test Web Application functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_config(self, temp_dir):
        """Mock configuration"""
        config_path = Path(temp_dir) / "config.env"
        config_content = """
GRID_MASTER=192.168.1.222
USERNAME=admin
PASSWORD=infoblox
NETWORK_VIEW=default
API_VERSION=v2.13.1
"""
        config_path.write_text(config_content)
        
        with patch('web_app.app.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(temp_dir)
            yield config_path
    
    def test_root_endpoint(self, client):
        """Test root endpoint serves HTML"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_get_config(self, client, mock_config):
        """Test getting configuration"""
        with patch('web_app.app.load_config') as mock_load:
            mock_load.return_value = {
                "GRID_MASTER": "192.168.1.222",
                "USERNAME": "admin",
                "NETWORK_VIEW": "default",
                "API_VERSION": "v2.13.1"
            }
            
            response = client.get("/api/config")
            assert response.status_code == 200
            
            data = response.json()
            assert data["GRID_MASTER"] == "192.168.1.222"
            assert data["USERNAME"] == "admin"
    
    def test_update_config(self, client):
        """Test updating configuration"""
        with patch('web_app.app.save_config') as mock_save:
            config_data = {
                "grid_master": "192.168.1.100",
                "network_view": "test_view",
                "username": "testuser",
                "password": "testpass",
                "api_version": "v2.13.1"
            }
            
            response = client.post("/api/config", json=config_data)
            assert response.status_code == 200
            assert response.json()["message"] == "Configuration updated successfully"
            
            mock_save.assert_called_once()
    
    def test_update_config_preserve_password(self, client):
        """Test updating config preserves password if not provided"""
        with patch('web_app.app.load_config') as mock_load, \
             patch('web_app.app.save_config') as mock_save:
            
            mock_load.return_value = {"PASSWORD": "existing_password"}
            
            config_data = {
                "grid_master": "192.168.1.100",
                "network_view": "test_view",
                "username": "testuser",
                "api_version": "v2.13.1"
                # No password provided
            }
            
            response = client.post("/api/config", json=config_data)
            assert response.status_code == 200
            
            # Check that existing password was preserved
            saved_config = mock_save.call_args[0][0]
            assert saved_config["PASSWORD"] == "existing_password"
    
    @patch('subprocess.run')
    def test_test_connection_success(self, mock_run, client):
        """Test successful connection test"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Connection successful"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        response = client.post("/api/test-connection")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "successful" in data["message"]
    
    @patch('subprocess.run')
    def test_test_connection_failure(self, mock_run, client):
        """Test failed connection test"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Connection failed"
        mock_run.return_value = mock_result
        
        response = client.post("/api/test-connection")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is False
        assert "failed" in data["message"]
    
    @patch('requests.get')
    def test_get_network_views_success(self, mock_get, client):
        """Test getting network views from InfoBlox"""
        with patch('web_app.app.load_config') as mock_load:
            mock_load.return_value = {
                "GRID_MASTER": "192.168.1.222",
                "USERNAME": "admin",
                "PASSWORD": "infoblox",
                "API_VERSION": "v2.13.1",
                "NETWORK_VIEW": "default"
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"name": "default"},
                {"name": "Test_view"},
                {"name": "MyView"}
            ]
            mock_get.return_value = mock_response
            
            response = client.get("/api/network-views")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is True
            assert len(data["views"]) == 3
            assert "default" in data["views"]
            assert data["current"] == "default"
    
    @patch('requests.get')
    def test_get_network_views_failure(self, mock_get, client):
        """Test network views retrieval failure"""
        with patch('web_app.app.load_config') as mock_load:
            mock_load.return_value = {
                "GRID_MASTER": "192.168.1.222",
                "USERNAME": "admin",
                "PASSWORD": "infoblox"
            }
            
            mock_get.side_effect = Exception("Connection error")
            
            response = client.get("/api/network-views")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is False
            assert "error" in data["message"].lower()
    
    def test_aws_import_missing_file(self, client):
        """Test AWS import without file"""
        response = client.post("/api/aws-import")
        assert response.status_code == 422  # Validation error
    
    def test_aws_import_with_file(self, client, sample_vpc_csv):
        """Test AWS import with valid file"""
        with patch('web_app.app.run_aws_import') as mock_run:
            with open(sample_vpc_csv, 'rb') as f:
                files = {'file': ('vpc_data.csv', f, 'text/csv')}
                data = {
                    'request': json.dumps({
                        'network_view': 'default',
                        'dry_run': False,
                        'create_missing': True,
                        'update_discrepant': False,
                        'sync_all': False
                    })
                }
                
                response = client.post("/api/aws-import", files=files, data=data)
                
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["job_id"].startswith("aws_")
    
    def test_property_import_with_file(self, client, sample_property_csv):
        """Test property import with valid file"""
        with patch('web_app.app.run_property_import') as mock_run:
            with open(sample_property_csv, 'rb') as f:
                files = {'file': ('property_data.csv', f, 'text/csv')}
                data = {
                    'request': json.dumps({
                        'network_view': 'MyView',
                        'dry_run': True,
                        'create_missing': True,
                        'update_discrepant': False,
                        'sync_all': False
                    })
                }
                
                response = client.post("/api/property-import", files=files, data=data)
                
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["job_id"].startswith("property_")
    
    def test_get_jobs_empty(self, client):
        """Test getting jobs when none exist"""
        jobs.clear()  # Clear any existing jobs
        
        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_jobs_with_data(self, client):
        """Test getting jobs with existing jobs"""
        from web_app.app import JobStatus
        from datetime import datetime
        
        # Add test jobs
        jobs.clear()
        jobs["test_job_1"] = JobStatus(
            job_id="test_job_1",
            status="completed",
            progress=100,
            message="Job completed",
            created_at=datetime.now()
        )
        jobs["test_job_2"] = JobStatus(
            job_id="test_job_2",
            status="running",
            progress=50,
            message="Processing...",
            created_at=datetime.now()
        )
        
        response = client.get("/api/jobs")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 2
        assert any(job["job_id"] == "test_job_1" for job in data)
        assert any(job["status"] == "running" for job in data)
    
    def test_get_specific_job(self, client):
        """Test getting specific job details"""
        from web_app.app import JobStatus
        from datetime import datetime
        
        jobs.clear()
        jobs["test_job"] = JobStatus(
            job_id="test_job",
            status="completed",
            progress=100,
            message="Test job completed",
            created_at=datetime.now()
        )
        
        response = client.get("/api/jobs/test_job")
        assert response.status_code == 200
        
        data = response.json()
        assert data["job_id"] == "test_job"
        assert data["status"] == "completed"
    
    def test_get_nonexistent_job(self, client):
        """Test getting non-existent job"""
        response = client.get("/api/jobs/nonexistent")
        assert response.status_code == 404
    
    def test_get_reports_empty(self, client):
        """Test getting reports when none exist"""
        with patch('os.listdir') as mock_listdir:
            mock_listdir.return_value = []
            
            response = client.get("/api/reports")
            assert response.status_code == 200
            assert response.json() == []
    
    def test_get_reports_with_files(self, client):
        """Test getting reports with existing files"""
        with patch('os.listdir') as mock_listdir, \
             patch('os.path.getmtime') as mock_getmtime, \
             patch('os.path.getsize') as mock_getsize:
            
            mock_listdir.return_value = ["report1.csv", "report2.md", "not_report.txt"]
            mock_getmtime.return_value = 1234567890
            mock_getsize.return_value = 1024
            
            response = client.get("/api/reports")
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 2  # Only .csv and .md files
            assert any(r["filename"] == "report1.csv" for r in data)
            assert any(r["filename"] == "report2.md" for r in data)
    
    def test_download_report(self, client, temp_dir):
        """Test downloading a report file"""
        report_content = "test,report,content\n1,2,3"
        report_path = Path(temp_dir) / "test_report.csv"
        report_path.write_text(report_content)
        
        with patch('web_app.app.REPORTS_DIR', temp_dir):
            response = client.get("/api/reports/test_report.csv")
            assert response.status_code == 200
            assert response.content.decode() == report_content
    
    def test_download_nonexistent_report(self, client):
        """Test downloading non-existent report"""
        response = client.get("/api/reports/nonexistent.csv")
        assert response.status_code == 404
    
    def test_websocket_connection(self):
        """Test WebSocket connection for job updates"""
        from web_app.app import JobStatus
        from datetime import datetime
        
        jobs["test_ws_job"] = JobStatus(
            job_id="test_ws_job",
            status="running",
            progress=0,
            message="Starting...",
            created_at=datetime.now()
        )
        
        with TestClient(app) as client:
            with client.websocket_connect("/ws/test_ws_job") as websocket:
                # Simulate job update
                jobs["test_ws_job"].progress = 50
                jobs["test_ws_job"].message = "Processing..."
                
                # In real app, this would be sent by the job runner
                # For testing, we just verify connection works
                assert websocket is not None