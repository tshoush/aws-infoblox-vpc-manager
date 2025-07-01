"""
Tests for Property Importer functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prop_infoblox_import_base import PropertyManager as PropertyImporter


class TestPropertyImporter:
    """Test Property Importer functionality"""
    
    def test_property_importer_initialization(self, mock_infoblox_client):
        """Test property importer initialization"""
        importer = PropertyImporter(
            mock_infoblox_client, 
            network_view="MyView",
            dry_run=True
        )
        
        assert importer.infoblox_client == mock_infoblox_client
        assert importer.network_view == "MyView"
        assert importer.dry_run is True
        assert importer.created_count == 0
        assert importer.failed_count == 0
        assert importer.skipped_count == 0
    
    def test_load_property_data_success(self, sample_property_csv):
        """Test successful property data loading"""
        importer = PropertyImporter(Mock())
        df = importer.load_property_data(str(sample_property_csv))
        
        assert df is not None
        assert len(df) == 3
        assert "Property Code" in df.columns
        assert "Network" in df.columns
    
    def test_load_property_data_missing_columns(self, temp_dir):
        """Test loading data with missing required columns"""
        csv_path = Path(temp_dir) / "bad_property.csv"
        csv_content = """Code,Name,IP
ATLCP,Atlanta,10.0.1.0/24
"""
        csv_path.write_text(csv_content)
        
        importer = PropertyImporter(Mock())
        df = importer.load_property_data(str(csv_path))
        
        assert df is None  # Should return None for missing columns
    
    def test_create_network_success(self, mock_infoblox_client):
        """Test successful network creation"""
        mock_infoblox_client.get_network.return_value = None
        mock_infoblox_client.create_network.return_value = {
            "_ref": "network/ZG5z:10.50.1.0/24/MyView"
        }
        
        importer = PropertyImporter(mock_infoblox_client, network_view="MyView")
        
        result = importer.create_network(
            network="10.50.1.0/24",
            property_code="ATLCP",
            property_name="Atlanta City Point",
            comment="Test network"
        )
        
        assert result is True
        assert importer.created_count == 1
        mock_infoblox_client.create_network.assert_called_once()
    
    def test_create_network_already_exists(self, mock_infoblox_client):
        """Test network creation when network already exists"""
        existing_network = {
            "_ref": "network/ZG5z:10.50.1.0/24/MyView",
            "network": "10.50.1.0/24"
        }
        mock_infoblox_client.get_network.return_value = existing_network
        
        importer = PropertyImporter(mock_infoblox_client, network_view="MyView")
        
        result = importer.create_network(
            network="10.50.1.0/24",
            property_code="ATLCP",
            property_name="Atlanta City Point"
        )
        
        assert result is True
        assert importer.skipped_count == 1
        mock_infoblox_client.create_network.assert_not_called()
    
    def test_create_network_dry_run(self, mock_infoblox_client):
        """Test network creation in dry run mode"""
        mock_infoblox_client.get_network.return_value = None
        
        importer = PropertyImporter(
            mock_infoblox_client, 
            network_view="MyView",
            dry_run=True
        )
        
        result = importer.create_network(
            network="10.50.1.0/24",
            property_code="ATLCP",
            property_name="Atlanta City Point"
        )
        
        assert result is True
        assert importer.created_count == 0  # Not incremented in dry run
        mock_infoblox_client.create_network.assert_not_called()
    
    def test_create_network_invalid_cidr(self, mock_infoblox_client):
        """Test network creation with invalid CIDR"""
        importer = PropertyImporter(mock_infoblox_client)
        
        result = importer.create_network(
            network="invalid-cidr",
            property_code="ATLCP",
            property_name="Atlanta City Point"
        )
        
        assert result is False
        assert importer.failed_count == 1
        mock_infoblox_client.create_network.assert_not_called()
    
    def test_update_network_extended_attributes(self, mock_infoblox_client):
        """Test updating network extended attributes"""
        existing_network = {
            "_ref": "network/ZG5z:10.50.1.0/24/MyView",
            "network": "10.50.1.0/24",
            "extattrs": {
                "Property_Code": {"value": "OLD"},
                "Property_Name": {"value": "Old Name"}
            }
        }
        mock_infoblox_client.get_network.return_value = existing_network
        mock_infoblox_client.update_network.return_value = True
        
        importer = PropertyImporter(
            mock_infoblox_client,
            network_view="MyView",
            update_existing=True
        )
        
        result = importer.create_network(
            network="10.50.1.0/24",
            property_code="ATLCP",
            property_name="Atlanta City Point"
        )
        
        assert result is True
        assert importer.updated_count == 1
        mock_infoblox_client.update_network.assert_called_once()
    
    def test_check_network_overlap(self, mock_infoblox_client):
        """Test network overlap detection"""
        mock_infoblox_client.check_network_overlap.return_value = (
            True,
            [{"network": "10.50.0.0/16", "network_view": "MyView"}]
        )
        
        importer = PropertyImporter(mock_infoblox_client, network_view="MyView")
        
        has_overlap, overlapping = importer.check_network_overlap("10.50.1.0/24")
        
        assert has_overlap is True
        assert len(overlapping) == 1
        assert overlapping[0]["network"] == "10.50.0.0/16"
    
    def test_import_properties_full_process(self, mock_infoblox_client, sample_property_csv):
        """Test full property import process"""
        mock_infoblox_client.get_network.return_value = None
        mock_infoblox_client.create_network.return_value = {
            "_ref": "network/ZG5z:10.50.1.0/24/MyView"
        }
        mock_infoblox_client.check_network_overlap.return_value = (False, [])
        
        importer = PropertyImporter(mock_infoblox_client, network_view="MyView")
        
        summary = importer.import_properties(str(sample_property_csv))
        
        assert summary["total_properties"] == 2  # 2 unique properties
        assert summary["total_networks"] == 3  # 3 networks total
        assert summary["networks_created"] == 3
        assert summary["networks_failed"] == 0
    
    def test_create_extended_attributes(self, mock_infoblox_client):
        """Test creating missing extended attributes"""
        mock_infoblox_client.get_extensibleattributedef.side_effect = [
            None,  # Property_Code doesn't exist
            None,  # Property_Name doesn't exist
        ]
        mock_infoblox_client.create_extensibleattributedef.return_value = {
            "_ref": "ea/new"
        }
        
        importer = PropertyImporter(mock_infoblox_client)
        importer.create_extended_attributes()
        
        assert mock_infoblox_client.create_extensibleattributedef.call_count == 2
    
    def test_validate_network_format(self, mock_infoblox_client):
        """Test network format validation"""
        importer = PropertyImporter(mock_infoblox_client)
        
        # Valid formats
        assert importer._validate_network("10.0.0.0/24") is True
        assert importer._validate_network("192.168.1.0/24") is True
        assert importer._validate_network("172.16.0.0/16") is True
        
        # Invalid formats
        assert importer._validate_network("10.0.0.0") is False
        assert importer._validate_network("invalid") is False
        assert importer._validate_network("10.0.0.0/33") is False
        assert importer._validate_network("256.0.0.0/24") is False
    
    @patch('pandas.DataFrame.to_csv')
    def test_generate_reports(self, mock_to_csv, mock_infoblox_client, temp_dir):
        """Test report generation"""
        importer = PropertyImporter(mock_infoblox_client)
        
        # Add test data
        importer.created_count = 10
        importer.failed_count = 2
        importer.skipped_count = 3
        importer.overlap_warnings.append({
            "network": "10.0.1.0/24",
            "overlapping": ["10.0.0.0/16"]
        })
        
        reports = importer.generate_reports(temp_dir)
        
        assert "summary" in reports
        assert "overlap_warnings" in reports
    
    def test_quiet_mode(self, mock_infoblox_client, capsys):
        """Test quiet mode operation"""
        importer = PropertyImporter(
            mock_infoblox_client,
            quiet=True
        )
        
        importer.create_network("10.0.1.0/24", "ATLCP", "Atlanta")
        
        captured = capsys.readouterr()
        assert captured.out == ""  # No output in quiet mode
    
    def test_handle_duplicate_networks(self, mock_infoblox_client, temp_dir):
        """Test handling of duplicate networks in input"""
        csv_path = Path(temp_dir) / "duplicate_property.csv"
        csv_content = """Property Code,Property Name,Network,Comment
ATLCP,Atlanta City Point,10.50.1.0/24,Primary
ATLCP,Atlanta City Point,10.50.1.0/24,Duplicate
"""
        csv_path.write_text(csv_content)
        
        mock_infoblox_client.get_network.return_value = None
        mock_infoblox_client.create_network.return_value = {
            "_ref": "network/ZG5z:10.50.1.0/24/MyView"
        }
        
        importer = PropertyImporter(mock_infoblox_client)
        summary = importer.import_properties(str(csv_path))
        
        # Should only create the network once
        assert summary["networks_created"] == 1
        assert mock_infoblox_client.create_network.call_count == 1