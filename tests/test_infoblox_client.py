"""
Tests for InfoBlox client functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aws_infoblox_vpc_manager_complete import InfoBloxClient


class TestInfoBloxClient:
    """Test InfoBlox client functionality"""
    
    def test_client_initialization(self):
        """Test client initialization"""
        client = InfoBloxClient(
            grid_master="192.168.1.222",
            username="admin",
            password="infoblox",
            api_version="v2.13.1"
        )
        
        assert client.grid_master == "192.168.1.222"
        assert client.username == "admin"
        assert client.password == "infoblox"
        assert client.api_version == "v2.13.1"
        assert client.base_url == "https://192.168.1.222/wapi/v2.13.1"
    
    @patch('requests.get')
    def test_connection_success(self, mock_get):
        """Test successful connection"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"name": "default"}]
        mock_get.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        result = client.test_connection()
        
        assert result is True
        mock_get.assert_called_once()
        
    @patch('requests.get')
    def test_connection_failure(self, mock_get):
        """Test connection failure"""
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        result = client.test_connection()
        
        assert result is False
    
    @patch('requests.get')
    def test_get_network_views(self, mock_get):
        """Test getting network views"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "default", "_ref": "networkview/ZG5z:default/true"},
            {"name": "Test_view", "_ref": "networkview/ZG5z:Test_view/false"}
        ]
        mock_get.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        views = client.get_network_views()
        
        assert len(views) == 2
        assert views[0]["name"] == "default"
        assert views[1]["name"] == "Test_view"
    
    @patch('requests.get')
    def test_get_network_not_found(self, mock_get):
        """Test getting network that doesn't exist"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        network = client.get_network("10.0.1.0/24", network_view="default")
        
        assert network is None
    
    @patch('requests.get')
    def test_get_network_found(self, mock_get):
        """Test getting existing network"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "_ref": "network/ZG5z:10.0.1.0/24/default",
            "network": "10.0.1.0/24",
            "network_view": "default"
        }]
        mock_get.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        network = client.get_network("10.0.1.0/24", network_view="default")
        
        assert network is not None
        assert network["network"] == "10.0.1.0/24"
    
    @patch('requests.post')
    def test_create_network_success(self, mock_post):
        """Test successful network creation"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "_ref": "network/ZG5z:10.0.1.0/24/default"
        }
        mock_post.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        result = client.create_network(
            network="10.0.1.0/24",
            network_view="default",
            comment="Test network"
        )
        
        assert result is not None
        assert "_ref" in result
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_create_network_failure(self, mock_post):
        """Test network creation failure"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Network already exists"
        mock_post.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        result = client.create_network(
            network="10.0.1.0/24",
            network_view="default"
        )
        
        assert result is None
    
    @patch('requests.put')
    def test_update_network_success(self, mock_put):
        """Test successful network update"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_ref": "network/ZG5z:10.0.1.0/24/default"
        }
        mock_put.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        result = client.update_network(
            network_ref="network/ZG5z:10.0.1.0/24/default",
            update_data={"comment": "Updated comment"}
        )
        
        assert result is True
        mock_put.assert_called_once()
    
    @patch('requests.get')
    def test_get_extensibleattributedef(self, mock_get):
        """Test getting extensible attribute definition"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "_ref": "extensibleattributedef/b25l:VPC_ID",
            "name": "VPC_ID",
            "type": "STRING"
        }]
        mock_get.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        ea_def = client.get_extensibleattributedef("VPC_ID")
        
        assert ea_def is not None
        assert ea_def["name"] == "VPC_ID"
    
    @patch('requests.post')
    def test_create_extensibleattributedef(self, mock_post):
        """Test creating extensible attribute definition"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "_ref": "extensibleattributedef/b25l:NEW_EA",
            "name": "NEW_EA"
        }
        mock_post.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        result = client.create_extensibleattributedef(
            name="NEW_EA",
            ea_type="STRING",
            comment="New EA for testing"
        )
        
        assert result is not None
        assert result["name"] == "NEW_EA"
    
    def test_prepare_extended_attributes(self):
        """Test extended attributes preparation"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        
        # Test with valid attributes
        attrs = {
            "VPC_ID": "vpc-123456",
            "Account_ID": "123456789012",
            "Empty_Value": "",
            "None_Value": None
        }
        
        prepared = client._prepare_extended_attributes(attrs)
        
        # Should only include non-empty values
        assert "VPC_ID" in prepared
        assert prepared["VPC_ID"]["value"] == "vpc-123456"
        assert "Account_ID" in prepared
        assert prepared["Account_ID"]["value"] == "123456789012"
        assert "Empty_Value" not in prepared
        assert "None_Value" not in prepared
    
    @patch('requests.get')
    def test_check_network_overlap(self, mock_get):
        """Test network overlap detection"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "network": "10.0.0.0/16",
            "network_view": "default"
        }]
        mock_get.return_value = mock_response
        
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        
        # This should overlap with 10.0.0.0/16
        has_overlap, overlapping = client.check_network_overlap(
            "10.0.1.0/24", 
            "default"
        )
        
        assert has_overlap is True
        assert len(overlapping) > 0
    
    def test_session_persistence(self):
        """Test that client uses persistent session"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        
        # Session should be created
        assert hasattr(client, 'session')
        assert client.session is not None
        
        # Auth should be set
        assert client.session.auth is not None
        assert client.session.auth == ("admin", "infoblox")
        
        # SSL verification should be disabled
        assert client.session.verify is False