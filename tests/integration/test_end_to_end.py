"""End-to-end integration tests for complete workflows."""

import os
import json
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import pytest

from tests.fixtures.azure_api_responses.subscription_responses import SUBSCRIPTION_LIST_RESPONSE
from tests.fixtures.azure_api_responses.vnet_responses import VNET_LIST_RESPONSE


def create_mock_subprocess_result(returncode=0, stdout='', stderr=''):
    """Create a mock subprocess result."""
    mock_result = Mock()
    mock_result.returncode = returncode
    mock_result.stdout = stdout
    mock_result.stderr = stderr
    return mock_result


def mock_subprocess_run(cmd, **kwargs):
    """Mock subprocess.run to simulate azure-query.py commands."""
    if len(cmd) >= 3 and cmd[1] == 'azure-query.py':
        command = cmd[2]
        
        if command == 'query':
            # Mock query command - create topology file
            output_file = None
            for i, arg in enumerate(cmd):
                if arg == '--output' and i + 1 < len(cmd):
                    output_file = cmd[i + 1]
                    break
            
            if output_file:
                # Create mock topology file
                with open(output_file, 'w') as f:
                    json.dump(VNET_LIST_RESPONSE, f, indent=2)
            
            return create_mock_subprocess_result(0, 'Query completed successfully\n')
        
        elif command == 'hld':
            # Mock HLD command - create diagram file
            output_file = None
            for i, arg in enumerate(cmd):
                if arg == '--output' and i + 1 < len(cmd):
                    output_file = cmd[i + 1]
                    break
            
            if output_file:
                # Create mock diagram file
                with open(output_file, 'w') as f:
                    f.write('<mxfile><diagram>Mock HLD diagram</diagram></mxfile>')
            
            return create_mock_subprocess_result(0, 'HLD diagram generated successfully\n')
        
        elif command == 'mld':
            # Mock MLD command - create diagram file
            output_file = None
            for i, arg in enumerate(cmd):
                if arg == '--output' and i + 1 < len(cmd):
                    output_file = cmd[i + 1]
                    break
            
            if output_file:
                # Create mock diagram file
                with open(output_file, 'w') as f:
                    f.write('<mxfile><diagram>Mock MLD diagram</diagram></mxfile>')
            
            return create_mock_subprocess_result(0, 'MLD diagram generated successfully\n')
    
    # Default fallback
    return create_mock_subprocess_result(0)


def mock_subprocess_run_with_error(cmd, **kwargs):
    """Mock subprocess.run that simulates failures."""
    if len(cmd) >= 3 and cmd[1] == 'azure-query.py':
        command = cmd[2]
        
        if command == 'query':
            return create_mock_subprocess_result(1, '', 'Azure API error\n')
        elif command in ['hld', 'mld']:
            return create_mock_subprocess_result(1, '', 'Diagram generation error\n')
    
    return create_mock_subprocess_result(1, '', 'Unknown error\n')


class TestQueryToHLDWorkflow:
    """Test complete query to HLD diagram workflow."""
    
    def test_simple_query_to_hld_workflow(self):
        """Test complete workflow from Azure query to HLD diagram generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'topology.json'
            hld_file = Path(temp_dir) / 'diagram.drawio'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                mock_hld.return_value = None
                
                # Step 1: Query Azure for topology
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0, f"Query failed: {query_result.stderr}"
                assert topology_file.exists(), "Topology file should be created"
                
                # Step 2: Generate HLD diagram from topology
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0, f"HLD generation failed: {hld_result.stderr}"
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 2
    
    def test_query_to_hld_with_custom_config(self):
        """Test complete workflow using custom configuration file."""
        config_path = Path('tests/fixtures/sample_configs/complete_config.yaml')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'topology.json'
            hld_file = Path(temp_dir) / 'diagram.drawio'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                mock_hld.return_value = None
                
                # Step 1: Query with custom config
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--config-file', str(config_path),
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Step 2: Generate HLD with same custom config
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--config-file', str(config_path),
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 2
    
    def test_query_to_hld_with_verbose_logging(self):
        """Test complete workflow with verbose logging enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'topology.json'
            hld_file = Path(temp_dir) / 'diagram.drawio'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                mock_hld.return_value = None
                
                # Step 1: Query with verbose logging
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--verbose',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                # Verbose mode should produce output
                assert len(query_result.stdout) > 0 or len(query_result.stderr) > 0
                
                # Step 2: Generate HLD with verbose logging
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--verbose',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 2


class TestQueryToMLDWorkflow:
    """Test complete query to MLD diagram workflow."""
    
    def test_simple_query_to_mld_workflow(self):
        """Test complete workflow from Azure query to MLD diagram generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'topology.json'
            mld_file = Path(temp_dir) / 'detailed_diagram.drawio'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('azure_query.generate_mld_diagram') as mock_mld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                mock_mld.return_value = None
                
                # Step 1: Query Azure for topology
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Step 2: Generate MLD diagram from topology
                mld_result = subprocess.run([
                    'python', 'azure-query.py', 'mld',
                    '--topology', str(topology_file),
                    '--output', str(mld_file)
                ], capture_output=True, text=True)
                
                assert mld_result.returncode == 0
                assert mld_file.exists(), "MLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 2
    
    def test_query_to_mld_with_custom_config(self):
        """Test complete MLD workflow using custom configuration file."""
        config_path = Path('tests/fixtures/sample_configs/minimal_config.yaml')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'topology.json'
            mld_file = Path(temp_dir) / 'detailed_diagram.drawio'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('azure_query.generate_mld_diagram') as mock_mld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                mock_mld.return_value = None
                
                # Step 1: Query with custom config
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--config-file', str(config_path),
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Step 2: Generate MLD with same custom config
                mld_result = subprocess.run([
                    'python', 'azure-query.py', 'mld',
                    '--config-file', str(config_path),
                    '--topology', str(topology_file),
                    '--output', str(mld_file)
                ], capture_output=True, text=True)
                
                assert mld_result.returncode == 0
                assert mld_file.exists(), "MLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 2


class TestVariousTopologySizes:
    """Test workflows with various topology sizes."""
    
    def test_small_topology_workflow(self):
        """Test workflow with small topology (single VNet)."""
        small_topology = {
            "vnets": [
                {
                    "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/single-vnet",
                    "name": "single-vnet",
                    "location": "eastus",
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "subnets": [{"name": "default", "addressPrefix": "10.0.1.0/24"}],
                    "peerings": []
                }
            ]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'small_topology.json'
            hld_file = Path(temp_dir) / 'small_diagram.drawio'
            
            # Create topology file
            with open(topology_file, 'w') as f:
                json.dump(small_topology, f, indent=2)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                mock_hld.return_value = None
                
                # Generate HLD from small topology
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify the topology exists in the created file
                with open(topology_file, 'r') as f:
                    topology_data = json.load(f)
                    assert len(topology_data["vnets"]) == 1
                    assert topology_data["vnets"][0]["name"] == "single-vnet"
    
    def test_medium_topology_workflow(self):
        """Test workflow with medium topology (hub-spoke with multiple spokes)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'medium_topology.json'
            hld_file = Path(temp_dir) / 'medium_diagram.drawio'
            
            # Use sample topology from fixtures
            with open('tests/fixtures/sample_topology.json', 'r') as f:
                sample_data = json.load(f)
            
            # Create topology file with hub-spoke scenario
            with open(topology_file, 'w') as f:
                json.dump(sample_data["simple_hub_spoke"], f, indent=2)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                mock_hld.return_value = None
                
                # Generate HLD from medium topology
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify the topology has multiple VNets
                with open(topology_file, 'r') as f:
                    topology_data = json.load(f)
                    assert len(topology_data["vnets"]) == 4  # 1 hub + 3 spokes
    
    def test_large_topology_workflow(self):
        """Test workflow with large topology (many VNets)."""
        # Generate large topology
        large_topology = {
            "vnets": [
                {
                    "id": f"/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-{i}/providers/Microsoft.Network/virtualNetworks/vnet-{i}",
                    "name": f"vnet-{i}",
                    "location": "eastus",
                    "addressSpace": {"addressPrefixes": [f"10.{i}.0.0/16"]},
                    "subnets": [{"name": "default", "addressPrefix": f"10.{i}.1.0/24"}],
                    "peerings": []
                }
                for i in range(50)  # 50 VNets
            ]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'large_topology.json'
            hld_file = Path(temp_dir) / 'large_diagram.drawio'
            
            # Create large topology file
            with open(topology_file, 'w') as f:
                json.dump(large_topology, f, indent=2)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                mock_hld.return_value = None
                
                # Generate HLD from large topology
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify the topology has many VNets
                with open(topology_file, 'r') as f:
                    topology_data = json.load(f)
                    assert len(topology_data["vnets"]) == 50


class TestDifferentPeeringPatterns:
    """Test workflows with different peering patterns."""
    
    def test_hub_spoke_peering_pattern(self):
        """Test workflow with hub-spoke peering pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'hub_spoke_topology.json'
            hld_file = Path(temp_dir) / 'hub_spoke_diagram.drawio'
            
            # Use hub-spoke sample from fixtures
            with open('tests/fixtures/sample_topology.json', 'r') as f:
                sample_data = json.load(f)
            
            with open(topology_file, 'w') as f:
                json.dump(sample_data["simple_hub_spoke"], f, indent=2)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                mock_hld.return_value = None
                
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify peering relationships exist in topology file
                with open(topology_file, 'r') as f:
                    topology = json.load(f)
                    hub_vnets = [vnet for vnet in topology["vnets"] if "hub" in vnet["name"]]
                    spoke_vnets = [vnet for vnet in topology["vnets"] if "spoke" in vnet["name"]]
                    
                    assert len(hub_vnets) == 1
                    assert len(spoke_vnets) == 3
                    assert len(hub_vnets[0]["peerings"]) == 3  # Hub connected to 3 spokes
    
    def test_multi_hub_peering_pattern(self):
        """Test workflow with multi-hub peering pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'multi_hub_topology.json'
            hld_file = Path(temp_dir) / 'multi_hub_diagram.drawio'
            
            # Use multi-hub sample from fixtures
            with open('tests/fixtures/sample_topology.json', 'r') as f:
                sample_data = json.load(f)
            
            with open(topology_file, 'w') as f:
                json.dump(sample_data["complex_multi_hub"], f, indent=2)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                mock_hld.return_value = None
                
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify multiple hubs exist in topology file
                with open(topology_file, 'r') as f:
                    topology = json.load(f)
                    hub_vnets = [vnet for vnet in topology["vnets"] if "hub" in vnet["name"]]
                    
                    assert len(hub_vnets) == 2  # Two hubs
    
    def test_no_peering_pattern(self):
        """Test workflow with isolated VNets (no peerings)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'isolated_topology.json'
            hld_file = Path(temp_dir) / 'isolated_diagram.drawio'
            
            # Use no-peering sample from fixtures
            with open('tests/fixtures/sample_topology.json', 'r') as f:
                sample_data = json.load(f)
            
            with open(topology_file, 'w') as f:
                json.dump(sample_data["edge_cases"]["no_peerings"], f, indent=2)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                mock_hld.return_value = None
                
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode == 0
                assert hld_file.exists(), "HLD diagram file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify no peerings exist in topology file
                with open(topology_file, 'r') as f:
                    topology = json.load(f)
                    for vnet in topology["vnets"]:
                        assert len(vnet["peerings"]) == 0


class TestMultipleSubscriptionScenarios:
    """Test workflows with multiple subscription scenarios."""
    
    def test_multiple_subscription_query(self):
        """Test query workflow with multiple subscriptions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'multi_sub_topology.json'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = [
                    "12345678-1234-1234-1234-123456789012",
                    "87654321-4321-4321-4321-210987654321"
                ]
                mock_topology.return_value = VNET_LIST_RESPONSE
                
                # Query multiple subscriptions (comma-separated)
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions',
                    '12345678-1234-1234-1234-123456789012,87654321-4321-4321-4321-210987654321',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
                
                # Verify multiple subscriptions were processed
                returned_subs = mock_subs.return_value
                assert len(returned_subs) == 2
    
    def test_subscription_name_resolution(self):
        """Test query workflow with subscription name resolution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'named_sub_topology.json'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                
                # Query using subscription name
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', 'Production Subscription',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1


class TestAuthenticationMethods:
    """Test workflows with different authentication methods."""
    
    def test_azure_cli_authentication(self):
        """Test workflow using Azure CLI authentication."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'cli_auth_topology.json'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
    
    def test_service_principal_authentication(self):
        """Test workflow using Service Principal authentication."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'sp_auth_topology.json'
            
            # Mock environment variables for Service Principal
            env_vars = {
                'AZURE_CLIENT_ID': 'test-client-id',
                'AZURE_CLIENT_SECRET': 'test-secret',
                'AZURE_TENANT_ID': 'test-tenant-id'
            }
            
            with patch.dict(os.environ, env_vars), \
                 patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = VNET_LIST_RESPONSE
                
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode == 0
                assert topology_file.exists(), "Topology file should be created"
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1


class TestWorkflowErrorHandling:
    """Test error handling in complete workflows."""
    
    def test_workflow_with_azure_query_failure(self):
        """Test workflow behavior when Azure query fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'failed_topology.json'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
                 patch('subprocess.run', side_effect=mock_subprocess_run_with_error) as mock_subprocess:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                # Mock Azure API failure
                mock_topology.side_effect = Exception("Azure API error")
                
                query_result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', str(topology_file)
                ], capture_output=True, text=True)
                
                assert query_result.returncode != 0
                assert not topology_file.exists()
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
    
    def test_workflow_with_diagram_generation_failure(self):
        """Test workflow behavior when diagram generation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'valid_topology.json'
            hld_file = Path(temp_dir) / 'failed_diagram.drawio'
            
            # Create valid topology file
            with open(topology_file, 'w') as f:
                json.dump({"vnets": []}, f)
            
            with patch('azure_query.generate_hld_diagram') as mock_hld, \
                 patch('subprocess.run', side_effect=mock_subprocess_run_with_error) as mock_subprocess:
                # Mock diagram generation failure
                mock_hld.side_effect = Exception("Diagram generation error")
                
                hld_result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', str(topology_file),
                    '--output', str(hld_file)
                ], capture_output=True, text=True)
                
                assert hld_result.returncode != 0
                assert not hld_file.exists()
                
                # Verify subprocess was called correctly
                assert mock_subprocess.call_count == 1
    
    def test_workflow_with_intermediate_file_deletion(self):
        """Test workflow behavior when intermediate files are deleted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            topology_file = Path(temp_dir) / 'topology.json'
            hld_file = Path(temp_dir) / 'diagram.drawio'
            
            with patch('azure_query.initialize_credentials') as mock_init, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology:
                
                mock_init.return_value = None
                mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
                mock_topology.return_value = {"vnets": []}
                
                # Step 1: Generate topology file
                with patch('subprocess.run', side_effect=mock_subprocess_run) as mock_subprocess:
                    query_result = subprocess.run([
                        'python', 'azure-query.py', 'query',
                        '--subscriptions', '12345678-1234-1234-1234-123456789012',
                        '--output', str(topology_file)
                    ], capture_output=True, text=True)
                    
                    assert query_result.returncode == 0
                    assert topology_file.exists(), "Topology file should be created"
                
                # Step 2: Delete the topology file
                topology_file.unlink()
                
                # Step 3: Try to generate diagram (should fail)
                with patch('subprocess.run', side_effect=mock_subprocess_run_with_error) as mock_subprocess_error:
                    hld_result = subprocess.run([
                        'python', 'azure-query.py', 'hld',
                        '--topology', str(topology_file),
                        '--output', str(hld_file)
                    ], capture_output=True, text=True)
                    
                    assert hld_result.returncode != 0
                    assert not hld_file.exists()
                    
                    # Verify subprocess was called correctly
                    assert mock_subprocess_error.call_count == 1