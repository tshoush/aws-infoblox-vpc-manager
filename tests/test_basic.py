"""
Basic tests to verify test infrastructure
"""
import pytest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBasicSetup:
    """Test basic setup and imports"""
    
    def test_imports_infoblox_client(self):
        """Test that InfoBlox client can be imported"""
        from aws_infoblox_vpc_manager_complete import InfoBloxClient
        assert InfoBloxClient is not None
    
    def test_imports_vpc_manager(self):
        """Test that VPC Manager can be imported"""
        from aws_infoblox_vpc_manager_complete import VPCManager
        assert VPCManager is not None
    
    def test_imports_property_importer(self):
        """Test that Property Importer can be imported"""
        from prop_infoblox_import import PropertyImporter
        assert PropertyImporter is not None
    
    def test_imports_web_app(self):
        """Test that web app can be imported"""
        from web_app.app import app
        assert app is not None
    
    def test_fixture_temp_dir(self, temp_dir):
        """Test temp_dir fixture"""
        assert Path(temp_dir).exists()
        assert Path(temp_dir).is_dir()
    
    def test_fixture_sample_vpc_csv(self, sample_vpc_csv):
        """Test sample VPC CSV fixture"""
        assert Path(sample_vpc_csv).exists()
        content = Path(sample_vpc_csv).read_text()
        assert "VPC ID" in content
        assert "CIDR Block" in content
    
    def test_fixture_sample_property_csv(self, sample_property_csv):
        """Test sample property CSV fixture"""
        assert Path(sample_property_csv).exists()
        content = Path(sample_property_csv).read_text()
        assert "Property Code" in content
        assert "Network" in content
    
    def test_configuration_constants(self):
        """Test configuration constants are defined"""
        from tests.conftest import (
            TEST_GRID_MASTER,
            TEST_USERNAME,
            TEST_PASSWORD,
            TEST_NETWORK_VIEW
        )
        
        assert TEST_GRID_MASTER == "192.168.1.222"
        assert TEST_USERNAME == "admin"
        assert TEST_PASSWORD == "infoblox"
        assert TEST_NETWORK_VIEW == "default"