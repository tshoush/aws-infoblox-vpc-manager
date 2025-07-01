"""
Tests for VPC Manager functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import pandas as pd
from pathlib import Path
import sys
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aws_infoblox_vpc_manager_complete import VPCManager


class TestVPCManager:
    """Test VPC Manager functionality"""
    
    def test_vpc_manager_initialization(self, mock_infoblox_client):
        """Test VPC manager initialization"""
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        assert manager.client == mock_infoblox_client
        assert manager.network_view == "default"
        assert manager.dry_run is False
        assert manager.networks_created == 0
        assert manager.networks_updated == 0
        assert manager.networks_failed == 0
    
    def test_load_vpc_data_success(self, sample_vpc_csv):
        """Test successful VPC data loading"""
        manager = VPCManager(Mock(), network_view="default")
        df = manager.load_vpc_data(str(sample_vpc_csv))
        
        assert df is not None
        assert len(df) == 2
        assert "VPC ID" in df.columns
        assert "CIDR Block" in df.columns
    
    def test_load_vpc_data_file_not_found(self):
        """Test VPC data loading with missing file"""
        manager = VPCManager(Mock(), network_view="default")
        df = manager.load_vpc_data("nonexistent.csv")
        
        assert df is None
    
    def test_process_vpc_network_dry_run(self, mock_infoblox_client):
        """Test processing network in dry run mode"""
        manager = VPCManager(mock_infoblox_client, network_view="default", dry_run=True)
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "VPC Name": "TestVPC",
            "Account ID": "123456789012",
            "Account Name": "TestAccount",
            "Subnet ID": "subnet-123",
            "Subnet Name": "TestSubnet",
            "CIDR Block": "10.0.1.0/24",
            "Availability Zone": "us-east-1a",
            "Region": "us-east-1"
        }
        
        result = manager.process_vpc_network(vpc_data)
        
        assert result is True
        assert manager.networks_created == 0  # No actual creation in dry run
        mock_infoblox_client.create_network.assert_not_called()
    
    def test_process_vpc_network_create_new(self, mock_infoblox_client):
        """Test creating new network"""
        mock_infoblox_client.get_network.return_value = None
        mock_infoblox_client.create_network.return_value = {"_ref": "network/ZG5z:10.0.1.0/24/default"}
        
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "VPC Name": "TestVPC",
            "Account ID": "123456789012",
            "Account Name": "TestAccount",
            "Subnet ID": "subnet-123",
            "Subnet Name": "TestSubnet",
            "CIDR Block": "10.0.1.0/24",
            "Availability Zone": "us-east-1a",
            "Region": "us-east-1"
        }
        
        result = manager.process_vpc_network(vpc_data)
        
        assert result is True
        assert manager.networks_created == 1
        mock_infoblox_client.create_network.assert_called_once()
    
    def test_process_vpc_network_update_existing(self, mock_infoblox_client):
        """Test updating existing network"""
        existing_network = {
            "_ref": "network/ZG5z:10.0.1.0/24/default",
            "network": "10.0.1.0/24",
            "extattrs": {
                "VPC_ID": {"value": "vpc-old"},
                "VPC_Name": {"value": "OldVPC"}
            }
        }
        mock_infoblox_client.get_network.return_value = existing_network
        mock_infoblox_client.update_network.return_value = True
        
        manager = VPCManager(mock_infoblox_client, network_view="default", update_existing=True)
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "VPC Name": "TestVPC",
            "Account ID": "123456789012",
            "Account Name": "TestAccount",
            "Subnet ID": "subnet-123",
            "Subnet Name": "TestSubnet",
            "CIDR Block": "10.0.1.0/24",
            "Availability Zone": "us-east-1a",
            "Region": "us-east-1"
        }
        
        result = manager.process_vpc_network(vpc_data)
        
        assert result is True
        assert manager.networks_updated == 1
        mock_infoblox_client.update_network.assert_called_once()
    
    def test_process_vpc_network_skip_existing(self, mock_infoblox_client):
        """Test skipping existing network when update is false"""
        existing_network = {
            "_ref": "network/ZG5z:10.0.1.0/24/default",
            "network": "10.0.1.0/24"
        }
        mock_infoblox_client.get_network.return_value = existing_network
        
        manager = VPCManager(mock_infoblox_client, network_view="default", update_existing=False)
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "CIDR Block": "10.0.1.0/24"
        }
        
        result = manager.process_vpc_network(vpc_data)
        
        assert result is True
        assert manager.networks_created == 0
        assert manager.networks_updated == 0
        mock_infoblox_client.update_network.assert_not_called()
    
    def test_process_vpc_network_invalid_cidr(self, mock_infoblox_client):
        """Test processing network with invalid CIDR"""
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "CIDR Block": "invalid-cidr"
        }
        
        result = manager.process_vpc_network(vpc_data)
        
        assert result is False
        assert manager.networks_failed == 1
    
    def test_create_missing_extended_attributes(self, mock_infoblox_client):
        """Test creating missing extended attributes"""
        # Mock EA checks
        mock_infoblox_client.get_extensibleattributedef.side_effect = [
            None,  # VPC_ID doesn't exist
            {"_ref": "ea/existing"},  # VPC_Name exists
            None,  # Account_ID doesn't exist
        ]
        
        mock_infoblox_client.create_extensibleattributedef.return_value = {"_ref": "ea/new"}
        
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        # Should create VPC_ID and Account_ID
        manager.create_missing_extended_attributes()
        
        # Should be called 2 times for missing EAs
        assert mock_infoblox_client.create_extensibleattributedef.call_count == 2
    
    def test_process_all_vpc_networks(self, mock_infoblox_client, sample_vpc_csv):
        """Test processing all VPC networks from CSV"""
        mock_infoblox_client.get_network.return_value = None
        mock_infoblox_client.create_network.return_value = {"_ref": "network/ZG5z:10.0.1.0/24/default"}
        
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        summary = manager.process_all_vpc_networks(str(sample_vpc_csv))
        
        assert summary["total_networks"] == 2
        assert summary["networks_created"] == 2
        assert summary["networks_failed"] == 0
    
    def test_check_discrepancies(self, mock_infoblox_client):
        """Test checking for discrepancies"""
        existing_attrs = {
            "VPC_ID": {"value": "vpc-old"},
            "VPC_Name": {"value": "OldVPC"},
            "Account_ID": {"value": "123456789012"}
        }
        
        new_attrs = {
            "VPC_ID": "vpc-new",
            "VPC_Name": "NewVPC",
            "Account_ID": "123456789012"  # Same value
        }
        
        manager = VPCManager(mock_infoblox_client, network_view="default")
        has_discrepancies, discrepancies = manager._check_discrepancies(existing_attrs, new_attrs)
        
        assert has_discrepancies is True
        assert "VPC_ID" in discrepancies
        assert "VPC_Name" in discrepancies
        assert "Account_ID" not in discrepancies  # Same value, no discrepancy
    
    def test_validate_cidr(self, mock_infoblox_client):
        """Test CIDR validation"""
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        # Valid CIDRs
        assert manager._validate_cidr("10.0.0.0/24") is True
        assert manager._validate_cidr("192.168.1.0/24") is True
        assert manager._validate_cidr("172.16.0.0/16") is True
        
        # Invalid CIDRs
        assert manager._validate_cidr("invalid") is False
        assert manager._validate_cidr("10.0.0.0") is False  # Missing prefix
        assert manager._validate_cidr("10.0.0.0/33") is False  # Invalid prefix
        assert manager._validate_cidr("256.0.0.0/24") is False  # Invalid IP
    
    @patch('pandas.DataFrame.to_csv')
    def test_generate_report(self, mock_to_csv, mock_infoblox_client, temp_dir):
        """Test report generation"""
        manager = VPCManager(mock_infoblox_client, network_view="default")
        
        # Add some test data
        manager.networks_created = 5
        manager.networks_updated = 3
        manager.networks_failed = 1
        manager.ea_errors = [{"network": "10.0.1.0/24", "error": "EA missing"}]
        
        report_path = manager.generate_report(temp_dir)
        
        assert report_path is not None
        assert "summary" in report_path.lower()
    
    def test_quiet_mode(self, mock_infoblox_client, capsys):
        """Test quiet mode suppresses output"""
        manager = VPCManager(mock_infoblox_client, network_view="default", quiet=True)
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "CIDR Block": "10.0.1.0/24"
        }
        
        manager.process_vpc_network(vpc_data)
        
        captured = capsys.readouterr()
        assert captured.out == ""  # No output in quiet mode
    
    def test_sync_mode(self, mock_infoblox_client):
        """Test sync mode forces updates"""
        existing_network = {
            "_ref": "network/ZG5z:10.0.1.0/24/default",
            "network": "10.0.1.0/24",
            "extattrs": {
                "VPC_ID": {"value": "vpc-123456"}  # Same as new
            }
        }
        mock_infoblox_client.get_network.return_value = existing_network
        mock_infoblox_client.update_network.return_value = True
        
        manager = VPCManager(mock_infoblox_client, network_view="default", sync_all=True)
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "CIDR Block": "10.0.1.0/24"
        }
        
        result = manager.process_vpc_network(vpc_data)
        
        assert result is True
        assert manager.networks_updated == 1
        mock_infoblox_client.update_network.assert_called_once()  # Updated even without changes