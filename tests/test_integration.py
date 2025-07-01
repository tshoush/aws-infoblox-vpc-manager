"""
Integration tests for the complete InfoBlox Management system
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from pathlib import Path
import sys
import json
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aws_infoblox_vpc_manager_complete import VPCManager
from prop_infoblox_import_base import InfoBloxClient, PropertyManager as PropertyImporter


class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.fixture
    def mock_infoblox_server(self):
        """Mock a complete InfoBlox server response pattern"""
        with patch('requests.Session') as mock_session:
            session_instance = Mock()
            mock_session.return_value = session_instance
            
            # Network storage
            networks = {}
            network_views = {
                "default": {"name": "default", "_ref": "networkview/ZG5z:default/true"},
                "MyView": {"name": "MyView", "_ref": "networkview/ZG5z:MyView/false"}
            }
            extended_attributes = {}
            
            def mock_get(url, **kwargs):
                response = Mock()
                
                if "networkview" in url and "name=" not in url:
                    # Get all network views
                    response.status_code = 200
                    response.json.return_value = list(network_views.values())
                elif "networkview" in url and "name=" in url:
                    # Get specific network view
                    view_name = url.split("name=")[1].split("&")[0]
                    if view_name in network_views:
                        response.status_code = 200
                        response.json.return_value = [network_views[view_name]]
                    else:
                        response.status_code = 200
                        response.json.return_value = []
                elif "network?" in url:
                    # Get network
                    response.status_code = 200
                    matching_networks = []
                    for key, net in networks.items():
                        if "network=" in url:
                            search_net = url.split("network=")[1].split("&")[0]
                            if net["network"] == search_net:
                                matching_networks.append(net)
                    response.json.return_value = matching_networks
                elif "extensibleattributedef" in url:
                    # Get EA definition
                    response.status_code = 200
                    if "name=" in url:
                        ea_name = url.split("name=")[1].split("&")[0]
                        if ea_name in extended_attributes:
                            response.json.return_value = [extended_attributes[ea_name]]
                        else:
                            response.json.return_value = []
                    else:
                        response.json.return_value = list(extended_attributes.values())
                else:
                    response.status_code = 404
                    response.json.return_value = {"Error": "Not found"}
                
                return response
            
            def mock_post(url, json=None, **kwargs):
                response = Mock()
                
                if "network" in url and json:
                    # Create network
                    network_data = json
                    network_key = f"{network_data['network']}_{network_data.get('network_view', 'default')}"
                    if network_key not in networks:
                        ref = f"network/ZG5z:{network_data['network']}/{network_data.get('network_view', 'default')}"
                        networks[network_key] = {
                            "_ref": ref,
                            "network": network_data["network"],
                            "network_view": network_data.get("network_view", "default"),
                            "comment": network_data.get("comment", ""),
                            "extattrs": network_data.get("extattrs", {})
                        }
                        response.status_code = 201
                        response.json.return_value = {"_ref": ref}
                    else:
                        response.status_code = 400
                        response.text = "Network already exists"
                elif "extensibleattributedef" in url and json:
                    # Create EA definition
                    ea_data = json
                    ea_name = ea_data["name"]
                    ref = f"extensibleattributedef/ZG5z:{ea_name}"
                    extended_attributes[ea_name] = {
                        "_ref": ref,
                        "name": ea_name,
                        "type": ea_data.get("type", "STRING")
                    }
                    response.status_code = 201
                    response.json.return_value = {"_ref": ref}
                else:
                    response.status_code = 400
                    response.text = "Bad request"
                
                return response
            
            def mock_put(url, json=None, **kwargs):
                response = Mock()
                
                # Update network
                for key, net in networks.items():
                    if net["_ref"] in url:
                        if json:
                            net.update(json)
                        response.status_code = 200
                        response.json.return_value = net
                        return response
                
                response.status_code = 404
                response.text = "Not found"
                return response
            
            session_instance.get = mock_get
            session_instance.post = mock_post
            session_instance.put = mock_put
            
            yield session_instance
    
    def test_end_to_end_vpc_import(self, mock_infoblox_server, sample_vpc_csv, temp_dir):
        """Test complete VPC import workflow"""
        # Create client and manager
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        manager = VPCManager(client, network_view="default")
        
        # Test connection
        assert client.test_connection() is True
        
        # Get network views
        views = client.get_network_views()
        assert len(views) == 2
        assert any(v["name"] == "default" for v in views)
        
        # Create missing EAs
        manager.create_missing_extended_attributes()
        
        # Process VPC data
        summary = manager.process_all_vpc_networks(str(sample_vpc_csv))
        
        assert summary["total_networks"] == 2
        assert summary["networks_created"] == 2
        assert summary["networks_failed"] == 0
        
        # Verify networks were created
        network1 = client.get_network("10.0.1.0/24", network_view="default")
        assert network1 is not None
        assert network1["extattrs"]["VPC_ID"]["value"] == "vpc-123456"
        
        network2 = client.get_network("10.0.2.0/24", network_view="default")
        assert network2 is not None
        assert network2["extattrs"]["Subnet_ID"]["value"] == "subnet-456"
        
        # Generate report
        report_path = manager.generate_report(temp_dir)
        assert Path(report_path).exists()
    
    def test_end_to_end_property_import(self, mock_infoblox_server, sample_property_csv, temp_dir):
        """Test complete property import workflow"""
        # Create client and importer
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        importer = PropertyImporter(client, network_view="MyView")
        
        # Create extended attributes
        importer.create_extended_attributes()
        
        # Import properties
        summary = importer.import_properties(str(sample_property_csv))
        
        assert summary["total_properties"] == 2
        assert summary["total_networks"] == 3
        assert summary["networks_created"] == 3
        
        # Verify networks were created with correct attributes
        network1 = client.get_network("10.50.1.0/24", network_view="MyView")
        assert network1 is not None
        assert network1["extattrs"]["Property_Code"]["value"] == "ATLCP"
        assert network1["extattrs"]["Property_Name"]["value"] == "Atlanta City Point"
        
        network2 = client.get_network("10.60.1.0/24", network_view="MyView")
        assert network2 is not None
        assert network2["extattrs"]["Property_Code"]["value"] == "NYCMQ"
        
        # Generate reports
        reports = importer.generate_reports(temp_dir)
        assert "summary" in reports
        assert Path(reports["summary"]).exists()
    
    def test_duplicate_network_handling(self, mock_infoblox_server):
        """Test handling of duplicate network creation attempts"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        manager = VPCManager(client, network_view="default")
        
        vpc_data = {
            "VPC ID": "vpc-123456",
            "VPC Name": "TestVPC",
            "CIDR Block": "10.0.1.0/24"
        }
        
        # First creation should succeed
        result1 = manager.process_vpc_network(vpc_data)
        assert result1 is True
        assert manager.networks_created == 1
        
        # Second creation should skip
        result2 = manager.process_vpc_network(vpc_data)
        assert result2 is True
        assert manager.networks_created == 1  # Still 1, not incremented
    
    def test_update_existing_network(self, mock_infoblox_server):
        """Test updating existing network with new attributes"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        
        # Create initial network
        client.create_network(
            network="10.0.1.0/24",
            network_view="default",
            comment="Initial",
            extattrs={"VPC_ID": {"value": "vpc-old"}}
        )
        
        # Update with new data
        manager = VPCManager(client, network_view="default", update_existing=True)
        
        vpc_data = {
            "VPC ID": "vpc-new",
            "VPC Name": "UpdatedVPC",
            "CIDR Block": "10.0.1.0/24"
        }
        
        result = manager.process_vpc_network(vpc_data)
        assert result is True
        assert manager.networks_updated == 1
        
        # Verify update
        network = client.get_network("10.0.1.0/24", network_view="default")
        assert network["extattrs"]["VPC_ID"]["value"] == "vpc-new"
    
    def test_network_view_switching(self, mock_infoblox_server):
        """Test creating networks in different network views"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        
        # Create in default view
        manager1 = VPCManager(client, network_view="default")
        vpc_data = {
            "VPC ID": "vpc-123",
            "CIDR Block": "10.0.1.0/24"
        }
        manager1.process_vpc_network(vpc_data)
        
        # Create same network in different view
        manager2 = VPCManager(client, network_view="MyView")
        manager2.process_vpc_network(vpc_data)
        
        # Both should exist
        net1 = client.get_network("10.0.1.0/24", network_view="default")
        net2 = client.get_network("10.0.1.0/24", network_view="MyView")
        
        assert net1 is not None
        assert net2 is not None
        assert net1["_ref"] != net2["_ref"]
    
    def test_error_recovery(self, mock_infoblox_server, temp_dir):
        """Test system behavior with mixed success and failures"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        manager = VPCManager(client, network_view="default")
        
        # Create CSV with mixed valid and invalid data
        csv_path = Path(temp_dir) / "mixed_data.csv"
        csv_content = """VPC ID,VPC Name,CIDR Block,Region
vpc-valid1,ValidVPC1,10.0.1.0/24,us-east-1
vpc-invalid,InvalidVPC,invalid-cidr,us-east-1
vpc-valid2,ValidVPC2,10.0.2.0/24,us-east-1
vpc-valid3,ValidVPC3,10.0.3.0/24,us-east-1
"""
        csv_path.write_text(csv_content)
        
        summary = manager.process_all_vpc_networks(str(csv_path))
        
        assert summary["total_networks"] == 4
        assert summary["networks_created"] == 3
        assert summary["networks_failed"] == 1
        
        # Verify error was logged
        assert len(manager.failed_networks) == 1
        assert "invalid-cidr" in manager.failed_networks[0]["error"]
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mock_infoblox_server):
        """Test concurrent network operations"""
        client = InfoBloxClient("192.168.1.222", "admin", "infoblox")
        
        async def create_network_async(cidr, vpc_id):
            manager = VPCManager(client, network_view="default")
            vpc_data = {
                "VPC ID": vpc_id,
                "CIDR Block": cidr
            }
            return manager.process_vpc_network(vpc_data)
        
        # Create multiple networks concurrently
        tasks = [
            create_network_async(f"10.0.{i}.0/24", f"vpc-{i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)
        
        # Verify all networks exist
        for i in range(10):
            network = client.get_network(f"10.0.{i}.0/24", network_view="default")
            assert network is not None
            assert network["extattrs"]["VPC_ID"]["value"] == f"vpc-{i}"