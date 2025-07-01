"""
Pytest configuration and fixtures for InfoBlox Management Portal tests
"""
import pytest
import sys
import os
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
TEST_GRID_MASTER = "192.168.1.222"
TEST_USERNAME = "admin"
TEST_PASSWORD = "infoblox"
TEST_NETWORK_VIEW = "default"
TEST_API_VERSION = "v2.13.1"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_config(temp_dir):
    """Create a mock config.env file"""
    config_path = Path(temp_dir) / "config.env"
    config_content = f"""
GRID_MASTER={TEST_GRID_MASTER}
USERNAME={TEST_USERNAME}
PASSWORD={TEST_PASSWORD}
NETWORK_VIEW={TEST_NETWORK_VIEW}
API_VERSION={TEST_API_VERSION}
"""
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def sample_vpc_csv(temp_dir):
    """Create a sample VPC CSV file"""
    csv_path = Path(temp_dir) / "vpc_data.csv"
    csv_content = """VPC ID,VPC Name,Account ID,Account Name,Subnet ID,Subnet Name,CIDR Block,Availability Zone,Region
vpc-123456,TestVPC,123456789012,TestAccount,subnet-123,TestSubnet,10.0.1.0/24,us-east-1a,us-east-1
vpc-123456,TestVPC,123456789012,TestAccount,subnet-456,TestSubnet2,10.0.2.0/24,us-east-1b,us-east-1
"""
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def sample_property_csv(temp_dir):
    """Create a sample property CSV file"""
    csv_path = Path(temp_dir) / "property_data.csv"
    csv_content = """Property Code,Property Name,Network,Comment
ATLCP,Atlanta City Point,10.50.1.0/24,Primary network
ATLCP,Atlanta City Point,10.50.2.0/24,Secondary network
NYCMQ,New York Marquis,10.60.1.0/24,Main network
"""
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def mock_infoblox_client():
    """Create a mock InfoBlox client"""
    with patch('aws_infoblox_vpc_manager_complete.InfoBloxClient') as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        
        # Mock common methods
        mock_instance.test_connection.return_value = True
        mock_instance.get_network_views.return_value = [
            {"name": "default", "_ref": "networkview/ZG5zLm5ldHdvcmtfdmlldyQw:default/true"},
            {"name": "Test_view", "_ref": "networkview/ZG5zLm5ldHdvcmtfdmlldyQx:Test_view/false"}
        ]
        mock_instance.get_network.return_value = None
        mock_instance.create_network.return_value = {"_ref": "network/ZG5zLm5ldHdvcmskMTAuMC4xLjAvMjQvMA:10.0.1.0/24/default"}
        mock_instance.get_extensibleattributedef.return_value = {"_ref": "extensibleattributedef/b25lLnZpcnR1YWxfbm9kZSQw:VPC_ID"}
        
        yield mock_instance


@pytest.fixture
def mock_requests():
    """Mock requests library"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('requests.put') as mock_put:
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"name": "default"}]
        mock_response.text = "Success"
        
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        mock_put.return_value = mock_response
        
        yield {
            'get': mock_get,
            'post': mock_post,
            'put': mock_put
        }


@pytest.fixture
async def test_client():
    """Create a test client for the FastAPI app"""
    from httpx import AsyncClient
    from web_app.app import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_websocket():
    """Mock WebSocket for testing"""
    mock_ws = Mock()
    mock_ws.send_json = Mock()
    mock_ws.receive_json = Mock()
    return mock_ws