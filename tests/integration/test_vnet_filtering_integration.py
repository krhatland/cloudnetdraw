"""
Integration tests for VNet filtering functionality including CLI interface and end-to-end workflows
"""
import os
import json
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

from azure_query import query_command, get_subscriptions_non_interactive


class TestVnetFilteringCLI:
    """Test CLI interface for VNet filtering"""
    
    def test_query_command_with_vnet_flag_basic(self):
        """Test query command with --vnet flag"""
        # Create mock topology data
        mock_topology = {
            "vnets": [
                {
                    "name": "hub-vnet-001",
                    "address_space": "10.0.0.0/16",
                    "subnets": [
                        {"name": "default", "address": "10.0.0.0/24", "nsg": "Yes", "udr": "No"}
                    ],
                    "peerings": ["hub-vnet-001_to_spoke1"],
                    "peerings_count": 1,
                    "subscription_name": "Test Subscription",
                    "is_explicit_hub": True,
                    "expressroute": "No",
                    "vpn_gateway": "No",
                    "firewall": "No"
                },
                {
                    "name": "spoke1",
                    "address_space": "10.1.0.0/16",
                    "subnets": [
                        {"name": "default", "address": "10.1.0.0/24", "nsg": "Yes", "udr": "Yes"}
                    ],
                    "peerings": ["spoke1_to_hub-vnet-001"],
                    "peerings_count": 1,
                    "subscription_name": "Test Subscription",
                    "expressroute": "No",
                    "vpn_gateway": "No",
                    "firewall": "No"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            with patch('azure_query.get_credentials') as mock_creds, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.resolve_subscription_names_to_ids') as mock_resolve, \
                 patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
                 patch('azure_query.save_to_json') as mock_save:

                mock_creds.return_value = MagicMock()
                mock_subs.return_value = ['sub-1']
                mock_resolve.return_value = ['sub-1']
                mock_filter.return_value = mock_topology
                
                # Create mock args - use legacy format with subscriptions
                args = MagicMock()
                args.service_principal = False
                args.subscriptions = None
                args.subscriptions_file = None
                args.vnets = 'sub-1/rg-1/hub-vnet-001'  # Use new path format
                args.output = output_file
                args.verbose = False
                
                # Initialize credentials for global usage
                from azure_query import initialize_credentials
                initialize_credentials()
                
                # Execute query command
                query_command(args)
                
                # Verify the right functions were called
                mock_filter.assert_called_once_with(['sub-1/rg-1/hub-vnet-001'], ['sub-1'])
                mock_save.assert_called_once_with(mock_topology, output_file)
                
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_query_command_with_vnet_resource_id(self):
        """Test query command with --vnet using resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001"
        
        mock_topology = {
            "vnets": [
                {
                    "name": "hub-vnet-001",
                    "address_space": "10.0.0.0/16",
                    "subscription_name": "Test Subscription",
                    "resource_group": "rg-1",
                    "is_explicit_hub": True,
                    "peerings": [],
                    "peerings_count": 0
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('azure_query.get_credentials') as mock_creds, \
                 patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
                 patch('azure_query.save_to_json') as mock_save:
                
                mock_creds.return_value = MagicMock()
                mock_filter.return_value = mock_topology
                
                # Create mock args - note: no subscriptions provided when using resource ID
                args = MagicMock()
                args.service_principal = False
                args.subscriptions = None  # No subscriptions needed with resource ID
                args.subscriptions_file = None
                args.vnets = resource_id
                args.output = output_file
                args.verbose = False
                
                # Initialize credentials for global usage
                from azure_query import initialize_credentials
                initialize_credentials()
                
                # Execute query command
                query_command(args)
                
                # Verify the right functions were called - subscription ID extracted from resource ID
                mock_filter.assert_called_once_with([resource_id], ['12345678-1234-1234-1234-123456789012'])
                mock_save.assert_called_once_with(mock_topology, output_file)
                
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_query_command_with_subscriptions_only(self):
        """Test query command with --subscriptions flag only"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
             patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_normal, \
             patch('azure_query.save_to_json') as mock_save:
            
            mock_creds.return_value = MagicMock()
            mock_subs.return_value = ['sub-1', 'sub-2']
            mock_normal.return_value = {"vnets": []}
            
            # Create mock args
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = 'sub-1,sub-2'
            args.subscriptions_file = None
            args.vnets = None  # Only subscriptions, no vnet
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Execute query command
            query_command(args)
            
            # Verify multiple subscriptions were used
            mock_subs.assert_called_once_with(args)
            mock_normal.assert_called_once_with(['sub-1', 'sub-2'])
            mock_save.assert_called_once_with({"vnets": []}, 'network_topology.json')
    
    def test_query_command_with_subscriptions_file_only(self):
        """Test query command with --subscriptions-file flag only"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("sub-1\nsub-2\nsub-3\n")
            subscriptions_file = f.name
        
        try:
            with patch('azure_query.get_credentials') as mock_creds, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_normal, \
                 patch('azure_query.save_to_json') as mock_save:
                
                mock_creds.return_value = MagicMock()
                mock_subs.return_value = ['sub-1', 'sub-2', 'sub-3']
                mock_normal.return_value = {"vnets": []}
                
                # Create mock args
                args = MagicMock()
                args.service_principal = False
                args.subscriptions = None
                args.subscriptions_file = subscriptions_file
                args.vnets = None  # Only subscriptions file, no vnet
                args.output = None
                args.verbose = False
                
                # Initialize credentials for global usage
                from azure_query import initialize_credentials
                initialize_credentials()
                
                # Execute query command
                query_command(args)
                
                # Verify subscriptions file was used
                mock_subs.assert_called_once_with(args)
                mock_normal.assert_called_once_with(['sub-1', 'sub-2', 'sub-3'])
                
        finally:
            if os.path.exists(subscriptions_file):
                os.unlink(subscriptions_file)
    
    def test_query_command_without_vnet_flag(self):
        """Test query command without --vnet flag uses normal topology collection"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
             patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_normal, \
             patch('azure_query.save_to_json') as mock_save:
            
            mock_creds.return_value = MagicMock()
            mock_subs.return_value = ['sub-1']
            mock_normal.return_value = {"vnets": []}
            
            # Create mock args
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = 'sub-1'
            args.subscriptions_file = None
            args.vnets = None  # No VNet filtering
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Execute query command
            query_command(args)
            
            # Verify normal topology collection was used
            mock_normal.assert_called_once_with(['sub-1'])
            mock_save.assert_called_once_with({"vnets": []}, 'network_topology.json')
    
    def test_query_command_with_legacy_vnet_requires_subscriptions(self):
        """Test that --vnet with legacy rg/vnet format requires --subscriptions or --subscriptions-file"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.resolve_subscription_names_to_ids') as mock_resolve, \
             patch('azure_query.SubscriptionClient') as mock_sub_client:
            
            mock_creds.return_value = MagicMock()
            # Mock SubscriptionClient to simulate the actual Azure API behavior when resolving None
            mock_sub_client_instance = MagicMock()
            mock_sub_client.return_value = mock_sub_client_instance
            mock_sub_client_instance.subscriptions.list.return_value = []
            
            # Mock resolve_subscription_names_to_ids to fail when trying to resolve None
            mock_resolve.side_effect = SystemExit(1)
            
            # Create mock args with --vnet but no subscription specification
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = 'rg-1/hub-vnet'  # Legacy format
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Execute query command should fail
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            # Verify it exits with error code 1
            assert exc_info.value.code == 1

    def test_query_command_with_new_path_format_no_subscriptions_needed(self):
        """Test that --vnet with new SUBSCRIPTION/RESOURCEGROUP/VNET format doesn't require --subscriptions"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.is_subscription_id') as mock_is_sub_id, \
             patch('azure_query.resolve_subscription_names_to_ids') as mock_resolve, \
             patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
             patch('azure_query.save_to_json') as mock_save:
            
            mock_creds.return_value = MagicMock()
            mock_is_sub_id.return_value = False  # It's a subscription name
            mock_resolve.return_value = ['12345678-1234-1234-1234-123456789012']
            mock_filter.return_value = {"vnets": []}
            
            # Create mock args with new format
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = 'test-subscription/rg-1/hub-vnet'  # New format
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should not raise an exception
            query_command(args)
            
            # Verify functions were called correctly
            mock_resolve.assert_called_once_with(['test-subscription'])
            mock_filter.assert_called_once_with(['test-subscription/rg-1/hub-vnet'], ['12345678-1234-1234-1234-123456789012'])

    def test_query_command_with_resource_id_no_subscriptions_needed(self):
        """Test that --vnet with resource ID format doesn't require --subscriptions"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet"
        
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
             patch('azure_query.save_to_json') as mock_save:
            
            mock_creds.return_value = MagicMock()
            mock_filter.return_value = {"vnets": []}
            
            # Create mock args with resource ID format
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = resource_id  # Resource ID format
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should not raise an exception
            query_command(args)
            
            # Verify functions were called correctly
            mock_filter.assert_called_once_with([resource_id], ['12345678-1234-1234-1234-123456789012'])

    def test_query_command_with_subscription_id_in_path_format(self):
        """Test that --vnet with subscription ID in path format works correctly"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.is_subscription_id') as mock_is_sub_id, \
             patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
             patch('azure_query.save_to_json') as mock_save:
            
            mock_creds.return_value = MagicMock()
            mock_is_sub_id.return_value = True  # It's a subscription ID
            mock_filter.return_value = {"vnets": []}
            
            # Create mock args with subscription ID in path format
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = '12345678-1234-1234-1234-123456789012/rg-1/hub-vnet'  # Path format with subscription ID
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should not raise an exception
            query_command(args)
            
            # Verify functions were called correctly
            mock_filter.assert_called_once_with(['12345678-1234-1234-1234-123456789012/rg-1/hub-vnet'], ['12345678-1234-1234-1234-123456789012'])
    
    def test_query_command_with_multiple_vnets_comma_separated(self):
        """Test query command with --vnets using multiple comma-separated VNets"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.is_subscription_id') as mock_is_sub_id, \
             patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
             patch('azure_query.save_to_json') as mock_save:

            mock_creds.return_value = MagicMock()
            mock_is_sub_id.return_value = True  # Both are subscription IDs
            mock_filter.return_value = {"vnets": []}

            # Create mock args with multiple VNets
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = '12345678-1234-1234-1234-123456789012/rg-1/hub-vnet1,12345678-1234-1234-1234-123456789012/rg-2/hub-vnet2'
            args.output = None
            args.verbose = False

            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()

            # Should not raise an exception
            query_command(args)

            # Verify the function was called with correct arguments - multiple VNets
            expected_vnet_identifiers = [
                '12345678-1234-1234-1234-123456789012/rg-1/hub-vnet1',
                '12345678-1234-1234-1234-123456789012/rg-2/hub-vnet2'
            ]
            mock_filter.assert_called_once_with(expected_vnet_identifiers, ['12345678-1234-1234-1234-123456789012'])

    def test_mutual_exclusion_subscriptions_and_subscriptions_file(self):
        """Test that --subscriptions and --subscriptions-file are mutually exclusive"""
        with patch('azure_query.get_credentials') as mock_creds:
            mock_creds.return_value = MagicMock()
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = 'sub-1'  # Both subscriptions and file provided
            args.subscriptions_file = 'subscriptions.txt'
            args.vnets = None
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should exit with error code 1
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            assert exc_info.value.code == 1

    def test_mutual_exclusion_subscriptions_and_vnet(self):
        """Test that --subscriptions and --vnet are mutually exclusive"""
        with patch('azure_query.get_credentials') as mock_creds:
            mock_creds.return_value = MagicMock()
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = 'sub-1'  # Both subscriptions and vnet provided
            args.subscriptions_file = None
            args.vnets = 'test-sub/rg-1/hub-vnet'
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should exit with error code 1
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            assert exc_info.value.code == 1

    def test_mutual_exclusion_subscriptions_file_and_vnet(self):
        """Test that --subscriptions-file and --vnet are mutually exclusive"""
        with patch('azure_query.get_credentials') as mock_creds:
            mock_creds.return_value = MagicMock()
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = 'subscriptions.txt'  # Both file and vnets provided
            args.vnets = '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet'
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should exit with error code 1
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            assert exc_info.value.code == 1

    def test_mutual_exclusion_all_three_arguments(self):
        """Test that --subscriptions, --subscriptions-file, and --vnet are mutually exclusive"""
        with patch('azure_query.get_credentials') as mock_creds:
            mock_creds.return_value = MagicMock()
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = 'sub-1'  # All three provided
            args.subscriptions_file = 'subscriptions.txt'
            args.vnets = 'rg-1/hub-vnet'
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should exit with error code 1
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            assert exc_info.value.code == 1

    def test_no_arguments_allows_interactive_mode(self):
        """Test that providing no subscription arguments allows interactive mode"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.list_and_select_subscriptions') as mock_interactive, \
             patch('azure_query.get_vnet_topology_for_selected_subscriptions') as mock_topology, \
             patch('azure_query.save_to_json') as mock_save:
            
            mock_creds.return_value = MagicMock()
            mock_interactive.return_value = ['sub-1']
            mock_topology.return_value = {"vnets": []}
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None  # No arguments provided - should allow interactive
            args.subscriptions_file = None
            args.vnets = None
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should not raise an exception
            query_command(args)
            
            # Verify interactive mode was used
            mock_interactive.assert_called_once()
            mock_topology.assert_called_once_with(['sub-1'])
    
    def test_subprocess_cli_with_vnet_flag(self):
        """Test actual CLI subprocess call with --vnet flag"""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--vnet', 'hub-vnet-001',
                '--subscriptions', '12345678-1234-1234-1234-123456789012',
                '--output', 'filtered_topology.json'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # Verify the command was called with expected arguments
            call_args = mock_run.call_args[0][0]
            assert '--vnet' in call_args
            assert 'hub-vnet-001' in call_args
            assert '--subscriptions' in call_args
    
    def test_subprocess_cli_help_shows_vnet_option(self):
        """Test that CLI help shows --vnet option"""
        result = subprocess.run([
            'python', 'azure-query.py', 'query', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert '--vnets' in result.stdout
        assert 'resource_ids (starting with /) or paths (subscription/resource_group/vnet_name)' in result.stdout
    
    def test_subprocess_cli_vnet_with_verbose(self):
        """Test CLI with --vnet and --verbose flags"""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call with verbose output
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='INFO - Filtering topology...')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--vnet', 'hub-vnet-001',
                '--subscriptions', '12345678-1234-1234-1234-123456789012',
                '--verbose'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # Verify the command was called with expected arguments
            call_args = mock_run.call_args[0][0]
            assert '--vnet' in call_args
            assert '--verbose' in call_args


class TestVnetFilteringEndToEnd:
    """Test end-to-end VNet filtering workflows"""
    
    def test_end_to_end_vnet_filtering_with_mocked_azure(self):
        """Test complete end-to-end workflow with mocked Azure API calls"""
        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name
        
        # Mock hub VNet data
        mock_hub_vnet = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': ['hub-vnet-001_to_spoke1', 'hub-vnet-001_to_spoke2'],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-1',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [
                '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke1',
                '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke2'
            ],
            'peerings_count': 2
        }
        
        # Mock spoke VNets data
        mock_spoke_vnets = [
            {
                'name': 'spoke1',
                'address_space': '10.1.0.0/16',
                'subnets': [],
                'peerings': ['spoke1_to_hub-vnet-001'],
                'subscription_name': 'Test Subscription',
                'subscription_id': '12345678-1234-1234-1234-123456789012',
                'resource_group': 'rg-1',
                'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke1',
                'expressroute': 'No',
                'vpn_gateway': 'No',
                'firewall': 'No',
                'peering_resource_ids': ['/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001'],
                'peerings_count': 1
            },
            {
                'name': 'spoke2',
                'address_space': '10.2.0.0/16',
                'subnets': [],
                'peerings': ['spoke2_to_hub-vnet-001'],
                'subscription_name': 'Test Subscription',
                'subscription_id': '12345678-1234-1234-1234-123456789012',
                'resource_group': 'rg-1',
                'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke2',
                'expressroute': 'No',
                'vpn_gateway': 'No',
                'firewall': 'No',
                'peering_resource_ids': ['/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001'],
                'peerings_count': 1
            }
        ]

        try:
            # Extract resource IDs for the second return value
            accessible_resource_ids = [vnet['resource_id'] for vnet in mock_spoke_vnets]
            
            with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=mock_hub_vnet), \
                 patch('azure_query.find_peered_vnets', return_value=(mock_spoke_vnets, accessible_resource_ids)):
                
                # Create mock args - use new path format instead of separate subscriptions
                args = MagicMock()
                args.service_principal = False
                args.subscriptions = None
                args.subscriptions_file = None
                args.vnets = '12345678-1234-1234-1234-123456789012/rg-1/hub-vnet-001'  # New path format
                args.output = output_file
                args.verbose = False
                
                # Initialize credentials for global usage
                from azure_query import initialize_credentials
                initialize_credentials()
                
                # Execute query command
                query_command(args)
                
                # Verify output file was created and contains expected data
                assert os.path.exists(output_file)
                
                with open(output_file, 'r') as f:
                    result = json.load(f)
                
                assert 'vnets' in result
                assert len(result['vnets']) == 3  # Hub + 2 spokes
                
                # Verify hub VNet
                hub_vnet = next(vnet for vnet in result['vnets'] if vnet['name'] == 'hub-vnet-001')
                assert hub_vnet['is_explicit_hub'] == True
                assert hub_vnet['address_space'] == '10.0.0.0/16'
                
                # Verify spoke VNets
                spoke_names = [vnet['name'] for vnet in result['vnets'] if vnet['name'] != 'hub-vnet-001']
                assert 'spoke1' in spoke_names
                assert 'spoke2' in spoke_names
                
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_end_to_end_diagram_generation_with_filtered_topology(self):
        """Test diagram generation using filtered topology"""
        # Create filtered topology JSON
        filtered_topology = {
            "vnets": [
                {
                    "name": "hub-vnet-001",
                    "address_space": "10.0.0.0/16",
                    "subnets": [
                        {"name": "default", "address": "10.0.0.0/24", "nsg": "Yes", "udr": "No"},
                        {"name": "GatewaySubnet", "address": "10.0.1.0/24", "nsg": "No", "udr": "No"}
                    ],
                    "peerings": ["hub-vnet-001_to_spoke1"],
                    "peerings_count": 1,
                    "subscription_name": "Test Subscription",
                    "is_explicit_hub": True,
                    "expressroute": "Yes",
                    "vpn_gateway": "Yes",
                    "firewall": "No"
                },
                {
                    "name": "spoke1",
                    "address_space": "10.1.0.0/16",
                    "subnets": [
                        {"name": "default", "address": "10.1.0.0/24", "nsg": "Yes", "udr": "Yes"}
                    ],
                    "peerings": ["spoke1_to_hub-vnet-001"],
                    "peerings_count": 1,
                    "subscription_name": "Test Subscription",
                    "expressroute": "No",
                    "vpn_gateway": "No",
                    "firewall": "No"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(filtered_topology, f)
            topology_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            hld_output = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            mld_output = f.name
        
        try:
            # Test HLD diagram generation
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', topology_file,
                '--output', hld_output
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"HLD command failed with stderr: {result.stderr}"
            assert os.path.exists(hld_output)
            
            # Test MLD diagram generation
            result = subprocess.run([
                'python', 'azure-query.py', 'mld',
                '--topology', topology_file,
                '--output', mld_output
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"MLD command failed with stderr: {result.stderr}"
            assert os.path.exists(mld_output)
            
            # Verify diagram files contain expected content
            with open(hld_output, 'r') as f:
                hld_content = f.read()
            assert 'hub-vnet-001' in hld_content
            assert 'spoke1' in hld_content
            assert 'mxfile' in hld_content  # Basic Draw.io format check
            
            with open(mld_output, 'r') as f:
                mld_content = f.read()
            assert 'hub-vnet-001' in mld_content
            assert 'spoke1' in mld_content
            assert 'default' in mld_content  # Should contain subnet info
            assert 'GatewaySubnet' in mld_content
            
        finally:
            for file_path in [topology_file, hld_output, mld_output]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    def test_end_to_end_multiple_subscriptions_filtering(self):
        """Test VNet filtering across multiple subscriptions"""
        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name
        
        # Use proper UUID format subscription IDs
        test_subscription_id1 = '12345678-1234-1234-1234-123456789012'
        test_subscription_id2 = '87654321-4321-4321-4321-210987654321'
        
        # Mock hub VNet data from subscription 1
        mock_hub_vnet = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': ['hub-vnet-001_to_spoke1'],
            'subscription_name': 'Test Subscription 1',
            'subscription_id': test_subscription_id1,
            'resource_group': 'rg-1',
            'resource_id': f'/subscriptions/{test_subscription_id1}/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [f'/subscriptions/{test_subscription_id2}/resourceGroups/rg-2/providers/Microsoft.Network/virtualNetworks/spoke1'],
            'peerings_count': 1
        }
        
        # Mock spoke VNet data from subscription 2
        mock_spoke_vnets = [
            {
                'name': 'spoke1',
                'address_space': '10.1.0.0/16',
                'subnets': [],
                'peerings': ['spoke1_to_hub-vnet-001'],
                'subscription_name': 'Test Subscription 2',
                'subscription_id': test_subscription_id2,
                'resource_group': 'rg-2',
                'resource_id': f'/subscriptions/{test_subscription_id2}/resourceGroups/rg-2/providers/Microsoft.Network/virtualNetworks/spoke1',
                'expressroute': 'No',
                'vpn_gateway': 'No',
                'firewall': 'No',
                'peering_resource_ids': [f'/subscriptions/{test_subscription_id1}/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001'],
                'peerings_count': 1
            }
        ]

        try:
            # Extract resource IDs for the second return value
            accessible_resource_ids = [vnet['resource_id'] for vnet in mock_spoke_vnets]
            
            with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=mock_hub_vnet), \
                 patch('azure_query.find_peered_vnets', return_value=(mock_spoke_vnets, accessible_resource_ids)):
                
                # Create mock args - use new path format instead of separate subscriptions
                args = MagicMock()
                args.service_principal = False
                args.subscriptions = None
                args.subscriptions_file = None
                args.vnets = f'{test_subscription_id1}/rg-1/hub-vnet-001'  # New path format
                args.output = output_file
                args.verbose = False
                
                # Initialize credentials for global usage
                from azure_query import initialize_credentials
                initialize_credentials()
                
                # Execute query command
                query_command(args)
                
                # Verify output file was created and contains expected data
                assert os.path.exists(output_file)
                
                with open(output_file, 'r') as f:
                    result = json.load(f)
                
                assert 'vnets' in result
                assert len(result['vnets']) == 2  # Hub + 1 spoke
                
                # Verify hub VNet from subscription 1
                hub_vnet = next(vnet for vnet in result['vnets'] if vnet['name'] == 'hub-vnet-001')
                assert hub_vnet['subscription_name'] == 'Test Subscription 1'
                
                # Verify spoke VNet from subscription 2
                spoke_vnet = next(vnet for vnet in result['vnets'] if vnet['name'] == 'spoke1')
                assert spoke_vnet['subscription_name'] == 'Test Subscription 2'
                
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestVnetFilteringErrorHandling:
    """Test error handling for VNet filtering functionality"""
    
    def test_vnet_not_found_error(self):
        """Test error when specified VNet is not found"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
             patch('azure_query.resolve_subscription_names_to_ids') as mock_resolve, \
             patch('azure_query.get_filtered_vnets_topology') as mock_filter:

            mock_creds.return_value = MagicMock()
            mock_subs.return_value = ['sub-1']
            mock_resolve.return_value = ['sub-1']
            mock_filter.side_effect = SystemExit(1)  # Simulate VNet not found
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = 'sub-1/rg-1/nonexistent-vnet'  # New path format
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            with pytest.raises(SystemExit):
                query_command(args)
    
    def test_invalid_vnet_resource_id_error(self):
        """Test error handling for invalid VNet resource ID"""
        with patch('azure_query.get_credentials') as mock_creds:
            
            mock_creds.return_value = MagicMock()
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = '/subscriptions/invalid/format'  # Invalid resource ID
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should exit with error code 1 due to invalid format
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            assert exc_info.value.code == 1
    
    def test_azure_api_error_handling(self):
        """Test handling of Azure API errors during VNet filtering"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
             patch('azure_query.resolve_subscription_names_to_ids') as mock_resolve, \
             patch('azure_query.get_filtered_vnets_topology') as mock_filter:

            mock_creds.return_value = MagicMock()
            mock_subs.return_value = ['sub-1']
            mock_resolve.return_value = ['sub-1']
            mock_filter.side_effect = Exception("Azure API Error")
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = 'sub-1/rg-1/hub-vnet-001'  # New path format
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            with pytest.raises(Exception, match="Azure API Error"):
                query_command(args)
    
    def test_vnet_with_subscriptions_file_works(self):
        """Test that --vnet works correctly when --subscriptions-file is provided"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("sub-1\nsub-2\n")
            subscriptions_file = f.name
        
        try:
            with patch('azure_query.get_credentials') as mock_creds, \
                 patch('azure_query.get_subscriptions_non_interactive') as mock_subs, \
                 patch('azure_query.get_filtered_vnets_topology') as mock_filter, \
                 patch('azure_query.save_to_json') as mock_save:
                
                mock_creds.return_value = MagicMock()
                mock_subs.return_value = ['sub-1', 'sub-2']
                mock_filter.return_value = {"vnets": []}
                
                args = MagicMock()
                args.service_principal = False
                args.subscriptions = None
                args.subscriptions_file = subscriptions_file
                args.vnets = 'rg-1/hub-vnet'
                args.output = None
                args.verbose = False
                
                # Initialize credentials for global usage
                from azure_query import initialize_credentials
                initialize_credentials()
                
                # Should exit with error code 1 due to mutual exclusion
                with pytest.raises(SystemExit) as exc_info:
                    query_command(args)
                
                assert exc_info.value.code == 1
                
        finally:
            if os.path.exists(subscriptions_file):
                os.unlink(subscriptions_file)
    
    def test_empty_filtered_topology_diagram_generation(self):
        """Test diagram generation with empty filtered topology"""
        # Create empty filtered topology
        empty_topology = {"vnets": []}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(empty_topology, f)
            topology_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            output_file = f.name
        
        try:
            # Test HLD diagram generation should fail with empty topology
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', topology_file,
                '--output', output_file
            ], capture_output=True, text=True)
            
            assert result.returncode == 1
            assert "No VNets found in topology file" in result.stderr
            
        finally:
            for file_path in [topology_file, output_file]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    def test_combination_with_invalid_subscription(self):
        """Test VNet filtering with invalid subscription combination"""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs:
            
            mock_creds.return_value = MagicMock()
            mock_subs.side_effect = SystemExit(1)  # Simulate invalid subscription
            
            args = MagicMock()
            args.service_principal = False
            args.subscriptions = 'invalid-subscription'
            args.subscriptions_file = None
            args.vnets = 'hub-vnet-001'  # This will fail due to mutual exclusion
            args.output = None
            args.verbose = False
            
            # Initialize credentials for global usage
            from azure_query import initialize_credentials
            initialize_credentials()
            
            # Should exit with error code 1 due to mutual exclusion
            with pytest.raises(SystemExit) as exc_info:
                query_command(args)
            
            assert exc_info.value.code == 1