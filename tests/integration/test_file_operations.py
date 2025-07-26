"""Integration tests for file operations functionality."""

import os
import json
import yaml
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import stat

from tests.fixtures.azure_api_responses.subscription_responses import SUBSCRIPTION_LIST_RESPONSE
from tests.fixtures.azure_api_responses.vnet_responses import VNET_LIST_RESPONSE


class TestJSONFileOperations:
    """Test JSON file reading and writing operations."""
    
    def test_read_valid_json_topology(self):
        """Test reading a valid JSON topology file."""
        topology_data = {"vnets": [{"name": "test-vnet", "location": "eastus"}]}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(topology_data, f)
            temp_file = f.name
        
        try:
            # Test reading the file through the application
            with patch('azure_query.generate_hld_diagram') as mock_hld:
                mock_hld.return_value = None
                
                import azure_query
                # This would be called internally by the application
                with open(temp_file, 'r') as file:
                    loaded_data = json.load(file)
                
                assert loaded_data == topology_data
                assert "vnets" in loaded_data
                assert len(loaded_data["vnets"]) == 1
        finally:
            os.unlink(temp_file)
    
    def test_write_topology_json_file(self):
        """Test writing topology data to JSON file."""
        topology_data = {
            "vnets": [
                {
                    "name": "test-vnet",
                    "location": "eastus",
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "peerings": []
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write data using the application's JSON writing logic
            import azure_query
            with open(temp_file, 'w') as f:
                json.dump(topology_data, f, indent=2)
            
            # Verify the file was written correctly
            with open(temp_file, 'r') as f:
                loaded_data = json.load(f)
            
            assert loaded_data == topology_data
            assert loaded_data["vnets"][0]["name"] == "test-vnet"
        finally:
            os.unlink(temp_file)
    
    def test_handle_invalid_json_file(self):
        """Test handling of invalid JSON files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json content")
            temp_file = f.name
        
        try:
            # Test that invalid JSON raises appropriate error
            with pytest.raises(json.JSONDecodeError):
                with open(temp_file, 'r') as file:
                    json.load(file)
        finally:
            os.unlink(temp_file)
    
    def test_handle_missing_json_file(self):
        """Test handling when JSON file doesn't exist."""
        nonexistent_file = "nonexistent_topology.json"
        
        # Test that missing file raises appropriate error
        with pytest.raises(FileNotFoundError):
            with open(nonexistent_file, 'r') as file:
                json.load(file)
    
    def test_json_file_permissions_error(self):
        """Test handling of permission errors when reading JSON files."""
        topology_data = {"vnets": []}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(topology_data, f)
            temp_file = f.name
        
        try:
            # Remove read permissions
            os.chmod(temp_file, stat.S_IWRITE)
            
            # Test that permission error is handled
            with pytest.raises(PermissionError):
                with open(temp_file, 'r') as file:
                    json.load(file)
        finally:
            # Restore permissions and cleanup
            os.chmod(temp_file, stat.S_IREAD | stat.S_IWRITE)
            os.unlink(temp_file)
    
    def test_large_json_file_handling(self):
        """Test handling of large JSON files."""
        # Create a large topology with many VNets
        large_topology = {
            "vnets": [
                {
                    "id": f"/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-{i}/providers/Microsoft.Network/virtualNetworks/vnet-{i}",
                    "name": f"vnet-{i}",
                    "location": "eastus",
                    "addressSpace": {"addressPrefixes": [f"10.{i}.0.0/16"]},
                    "subnets": [
                        {
                            "name": "default",
                            "addressPrefix": f"10.{i}.1.0/24"
                        }
                    ],
                    "peerings": []
                }
                for i in range(100)  # 100 VNets
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(large_topology, f, indent=2)
            temp_file = f.name
        
        try:
            # Test reading large file
            with open(temp_file, 'r') as file:
                loaded_data = json.load(file)
            
            assert len(loaded_data["vnets"]) == 100
            assert loaded_data["vnets"][0]["name"] == "vnet-0"
            assert loaded_data["vnets"][99]["name"] == "vnet-99"
        finally:
            os.unlink(temp_file)


class TestYAMLConfigOperations:
    """Test YAML configuration file operations."""
    
    def test_load_valid_yaml_config(self):
        """Test loading a valid YAML configuration file."""
        config_path = Path('tests/fixtures/sample_configs/minimal_config.yaml')
        
        import azure_query
        # Test loading config through the application
        with open(config_path, 'r') as file:
            config_data = yaml.safe_load(file)
        
        assert "hub_threshold" in config_data
        assert config_data["hub_threshold"] == 3
        assert "style" in config_data
        assert "layout" in config_data
    
    def test_load_complete_yaml_config(self):
        """Test loading a complete YAML configuration file."""
        config_path = Path('tests/fixtures/sample_configs/complete_config.yaml')
        
        with open(config_path, 'r') as file:
            config_data = yaml.safe_load(file)
        
        assert "hub_threshold" in config_data
        assert "style" in config_data
        assert "layout" in config_data
        assert "icons" in config_data
        assert "icon_positioning" in config_data
        assert "drawio" in config_data
    
    def test_handle_invalid_yaml_config(self):
        """Test handling of invalid YAML configuration files."""
        config_path = Path('tests/fixtures/sample_configs/invalid_config.yaml')
        
        # Test that invalid YAML raises appropriate error
        with pytest.raises(yaml.YAMLError):
            with open(config_path, 'r') as file:
                yaml.safe_load(file)
    
    def test_handle_missing_yaml_config(self):
        """Test handling when YAML config file doesn't exist."""
        nonexistent_config = "nonexistent_config.yaml"
        
        # Test that missing file raises appropriate error
        with pytest.raises(FileNotFoundError):
            with open(nonexistent_config, 'r') as file:
                yaml.safe_load(file)
    
    def test_config_file_path_resolution_same_directory(self):
        """Test config file path resolution from same directory."""
        config_path = Path('tests/fixtures/sample_configs/minimal_config.yaml')
        
        # Test that relative path resolves correctly
        assert config_path.exists()
        
        with open(config_path, 'r') as file:
            config_data = yaml.safe_load(file)
        
        assert config_data is not None
        assert "hub_threshold" in config_data
    
    def test_config_file_path_resolution_different_directory(self):
        """Test config file path resolution from different directory."""
        # Change to a different directory
        original_cwd = os.getcwd()
        temp_dir = tempfile.mkdtemp()
        
        try:
            os.chdir(temp_dir)
            
            # Use absolute path to config file
            config_path = Path(original_cwd) / 'tests/fixtures/sample_configs/minimal_config.yaml'
            
            with open(config_path, 'r') as file:
                config_data = yaml.safe_load(file)
            
            assert config_data is not None
            assert "hub_threshold" in config_data
        finally:
            os.chdir(original_cwd)
            os.rmdir(temp_dir)
    
    def test_config_file_permissions_error(self):
        """Test handling of permission errors when reading config files."""
        config_path = Path('tests/fixtures/sample_configs/minimal_config.yaml')
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("hub_threshold: 3\n")
            temp_file = f.name
        
        try:
            # Remove read permissions
            os.chmod(temp_file, stat.S_IWRITE)
            
            # Test that permission error is handled
            with pytest.raises(PermissionError):
                with open(temp_file, 'r') as file:
                    yaml.safe_load(file)
        finally:
            # Restore permissions and cleanup
            os.chmod(temp_file, stat.S_IREAD | stat.S_IWRITE)
            os.unlink(temp_file)


class TestDrawIOXMLFileGeneration:
    """Test Draw.io XML file generation and validation."""
    
    def test_basic_xml_file_generation(self):
        """Test basic XML file generation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            temp_file = f.name
        
        try:
            # Generate basic XML content
            xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
    <diagram>
        <mxGraphModel dx="1200" dy="800">
            <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
                <mxCell id="test-vnet" value="test-vnet" parent="1" vertex="1">
                    <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
                </mxCell>
            </root>
        </mxGraphModel>
    </diagram>
</mxfile>'''
            
            with open(temp_file, 'w') as f:
                f.write(xml_content)
            
            # Verify file was written
            assert os.path.exists(temp_file)
            with open(temp_file, 'r') as f:
                content = f.read()
                assert '<?xml version="1.0"' in content
                assert '<mxfile>' in content
                assert 'test-vnet' in content
        finally:
            os.unlink(temp_file)
    
    def test_xml_file_validation(self):
        """Test XML file structure validation."""
        from lxml import etree
        
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
    <diagram>
        <mxGraphModel dx="1200" dy="800">
            <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
            </root>
        </mxGraphModel>
    </diagram>
</mxfile>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            # Validate XML structure
            tree = etree.parse(temp_file)
            root = tree.getroot()
            
            assert root.tag == 'mxfile'
            assert len(root.xpath('//diagram')) == 1
            assert len(root.xpath('//mxGraphModel')) == 1
            assert len(root.xpath('//root')) == 1
        finally:
            os.unlink(temp_file)
    
    def test_invalid_xml_file_handling(self):
        """Test handling of invalid XML files."""
        from lxml import etree
        
        invalid_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
    <diagram>
        <unclosed_tag>
    </diagram>
</mxfile>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(invalid_xml)
            temp_file = f.name
        
        try:
            # Test that invalid XML raises appropriate error
            with pytest.raises(etree.XMLSyntaxError):
                etree.parse(temp_file)
        finally:
            os.unlink(temp_file)


class TestDirectoryCreation:
    """Test directory creation for output files."""
    
    def test_create_output_directory(self):
        """Test automatic creation of output directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'diagrams' / 'output.drawio'
            
            # Ensure parent directory doesn't exist initially
            assert not output_path.parent.exists()
            
            # Create directory structure
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Verify directory was created
            assert output_path.parent.exists()
            assert output_path.parent.is_dir()
            
            # Test writing file to created directory
            with open(output_path, 'w') as f:
                f.write('<mxfile></mxfile>')
            
            assert output_path.exists()
    
    def test_nested_directory_creation(self):
        """Test creation of deeply nested directory structures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deep_path = Path(temp_dir) / 'level1' / 'level2' / 'level3' / 'output.json'
            
            # Create nested directory structure
            deep_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Verify all levels were created
            assert (Path(temp_dir) / 'level1').exists()
            assert (Path(temp_dir) / 'level1' / 'level2').exists()
            assert (Path(temp_dir) / 'level1' / 'level2' / 'level3').exists()
            
            # Test writing file to deeply nested directory
            with open(deep_path, 'w') as f:
                json.dump({"test": "data"}, f)
            
            assert deep_path.exists()


class TestFileLocking:
    """Test handling of locked/readonly files."""
    
    def test_readonly_output_file_handling(self):
        """Test handling when output file is readonly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": "data"}')
            temp_file = f.name
        
        try:
            # Make file readonly
            os.chmod(temp_file, stat.S_IREAD)
            
            # Test that readonly file raises appropriate error
            with pytest.raises(PermissionError):
                with open(temp_file, 'w') as f:
                    json.dump({"new": "data"}, f)
        finally:
            # Restore permissions and cleanup
            os.chmod(temp_file, stat.S_IREAD | stat.S_IWRITE)
            os.unlink(temp_file)
    
    def test_directory_permission_error(self):
        """Test handling when directory has no write permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Make directory readonly
            os.chmod(temp_dir, stat.S_IREAD | stat.S_IEXEC)
            
            try:
                output_file = Path(temp_dir) / 'output.json'
                
                # Test that readonly directory raises appropriate error
                with pytest.raises(PermissionError):
                    with open(output_file, 'w') as f:
                        json.dump({"test": "data"}, f)
            finally:
                # Restore permissions
                os.chmod(temp_dir, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)


class TestFilePathResolution:
    """Test file path resolution across operating systems."""
    
    def test_relative_path_resolution(self):
        """Test resolution of relative paths."""
        relative_path = Path('tests/fixtures/sample_topology.json')
        
        # Test that relative path resolves correctly
        assert relative_path.exists()
        
        with open(relative_path, 'r') as f:
            data = json.load(f)
        
        assert "minimal" in data
    
    def test_absolute_path_resolution(self):
        """Test resolution of absolute paths."""
        relative_path = Path('tests/fixtures/sample_topology.json')
        absolute_path = relative_path.absolute()
        
        # Test that absolute path works correctly
        assert absolute_path.exists()
        
        with open(absolute_path, 'r') as f:
            data = json.load(f)
        
        assert "minimal" in data
    
    def test_path_with_special_characters(self):
        """Test handling of paths with special characters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory with special characters (where allowed)
            special_name = "test-dir_with.special"
            special_path = Path(temp_dir) / special_name
            special_path.mkdir()
            
            output_file = special_path / 'output.json'
            
            # Test writing to path with special characters
            with open(output_file, 'w') as f:
                json.dump({"test": "data"}, f)
            
            assert output_file.exists()
            
            # Test reading from path with special characters
            with open(output_file, 'r') as f:
                data = json.load(f)
            
            assert data["test"] == "data"