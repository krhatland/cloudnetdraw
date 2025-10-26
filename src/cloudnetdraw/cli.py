"""
CLI interface for CloudNet Draw
Handles argument parsing and command dispatching
"""
import argparse
import logging
import sys
import shutil
import os
from typing import List

from . import __version__
from .azure_client import initialize_credentials, get_vnet_topology_for_selected_subscriptions
from .topology import get_filtered_vnet_topology, get_filtered_vnets_topology
from .utils import save_to_json
from .config import Config


def query_command(args: argparse.Namespace) -> None:
    """Execute the query command to collect VNet topology from Azure"""
    from .azure_client import (
        list_and_select_subscriptions, 
        get_subscriptions_non_interactive
    )
    
    # Validate file arguments - they should not be empty strings
    file_args = [
        ('--output', args.output),
        ('--subscriptions-file', getattr(args, 'subscriptions_file', None)),
        ('--config-file', getattr(args, 'config_file', None))
    ]
    
    empty_file_args = [arg_name for arg_name, arg_value in file_args if arg_value is not None and not arg_value.strip()]
    
    if empty_file_args:
        logging.error(f"Empty file path provided for: {', '.join(empty_file_args)}")
        logging.error("File arguments cannot be empty strings in non-interactive scenarios")
        logging.error("Either provide valid file paths or omit the arguments to use defaults")
        sys.exit(1)
    
    # Initialize credentials based on service principal flag
    initialize_credentials(args.service_principal)
    
    # Validate mutually exclusive arguments
    exclusive_args = [
        ('--subscriptions', args.subscriptions),
        ('--subscriptions-file', args.subscriptions_file),
        ('--vnets', args.vnets)
    ]
    
    # Check for arguments that are provided (not None) and not empty
    # For comma-separated arguments like vnets, we need to check if there are any valid values after parsing
    provided_args = []
    empty_args = []
    
    for arg_name, arg_value in exclusive_args:
        if arg_value is not None:
            if not arg_value.strip():
                # Completely empty argument
                empty_args.append(arg_name)
            elif arg_name == '--vnets':
                # Special handling for comma-separated vnets - check if any valid identifiers exist
                vnet_identifiers = [vnet.strip() for vnet in arg_value.split(',') if vnet.strip()]
                if not vnet_identifiers:
                    empty_args.append(arg_name)
                else:
                    provided_args.append(arg_name)
            elif arg_name == '--subscriptions':
                # Special handling for comma-separated subscriptions - check if any valid values exist
                subscription_values = [sub.strip() for sub in arg_value.split(',') if sub.strip()]
                if not subscription_values:
                    empty_args.append(arg_name)
                else:
                    provided_args.append(arg_name)
            else:
                # For other arguments (like --subscriptions-file), just check if not empty after strip
                provided_args.append(arg_name)
    
    if empty_args:
        logging.error(f"Empty values provided for: {', '.join(empty_args)}")
        logging.error("Empty argument values are not allowed in non-interactive scenarios like GitHub Actions")
        logging.error("Either provide valid values or omit the arguments entirely to use interactive mode")
        sys.exit(1)
    
    if len(provided_args) > 1:
        logging.error(f"The following arguments are mutually exclusive: {', '.join(provided_args)}")
        logging.error("Please specify only one of: --subscriptions, --subscriptions-file, or --vnets")
        logging.error("Use --help for more information about these options")
        sys.exit(1)
    
    # Determine subscription selection mode
    if args.vnets:
        # VNet filtering mode - parse comma-separated VNet identifiers
        vnet_identifiers = [vnet.strip() for vnet in args.vnets.split(',') if vnet.strip()]
        
        if not vnet_identifiers:
            logging.error("No valid VNet identifiers provided after parsing --vnets argument")
            logging.error("Please provide valid VNet identifiers in the format: subscription/resource_group/vnet_name or resource_group/vnet_name")
            sys.exit(1)
            
        # Collect all subscriptions needed for the VNets
        all_subscriptions = set()
        
        from .utils import parse_vnet_identifier
        from .azure_client import is_subscription_id, resolve_subscription_names_to_ids
        
        for vnet_identifier in vnet_identifiers:
            try:
                subscription_id, resource_group, vnet_name = parse_vnet_identifier(vnet_identifier)
                
                # Subscription specified in vnet identifier (resource ID or path format)
                # Check if it's a subscription name or ID and resolve if needed
                if is_subscription_id(subscription_id):
                    all_subscriptions.add(subscription_id)
                else:
                    # It's a subscription name, resolve to ID
                    resolved_subs = resolve_subscription_names_to_ids([subscription_id])
                    all_subscriptions.update(resolved_subs)
            except ValueError as e:
                logging.error(f"Invalid VNet identifier format '{vnet_identifier}': {e}")
                sys.exit(1)
        
        selected_subscriptions = list(all_subscriptions)
        logging.info(f"Filtering topology for hub VNets: {args.vnets}")
        topology = get_filtered_vnets_topology(vnet_identifiers, selected_subscriptions)
    else:
        # Original behavior for non-VNet filtering
        if (args.subscriptions and args.subscriptions.strip()) or (args.subscriptions_file and args.subscriptions_file.strip()):
            # Non-interactive mode
            selected_subscriptions = get_subscriptions_non_interactive(args)
        else:
            # Interactive mode (existing behavior)
            logging.info("Listing available subscriptions...")
            selected_subscriptions = list_and_select_subscriptions()
        
        logging.info("Collecting VNets and topology...")
        topology = get_vnet_topology_for_selected_subscriptions(selected_subscriptions)
    
    output_file = args.output if args.output else "network_topology.json"
    save_to_json(topology, output_file)


def hld_command(args: argparse.Namespace) -> None:
    """Execute the HLD command to generate high-level diagrams"""
    # Validate file arguments - they should not be empty strings
    file_args = [
        ('--output', args.output),
        ('--topology', args.topology),
        ('--config-file', getattr(args, 'config_file', None))
    ]
    
    empty_file_args = [arg_name for arg_name, arg_value in file_args if arg_value is not None and not arg_value.strip()]
    
    if empty_file_args:
        logging.error(f"Empty file path provided for: {', '.join(empty_file_args)}")
        logging.error("File arguments cannot be empty strings in non-interactive scenarios")
        logging.error("Either provide valid file paths or omit the arguments to use defaults")
        sys.exit(1)
    
    topology_file = args.topology if args.topology else "network_topology.json"
    output_file = args.output if args.output else "network_hld.drawio"
    config_file = args.config_file
    
    # Create config instance with specified file
    config = Config(config_file)
    
    from .diagram_generator import generate_hld_diagram
    
    logging.info("Starting HLD diagram generation...")
    generate_hld_diagram(output_file, topology_file, config)
    logging.info("HLD diagram generation complete.")
    logging.info(f"HLD diagram saved to {output_file}")


def mld_command(args: argparse.Namespace) -> None:
    """Execute the MLD command to generate mid-level diagrams"""
    # Validate file arguments - they should not be empty strings
    file_args = [
        ('--output', args.output),
        ('--topology', args.topology),
        ('--config-file', getattr(args, 'config_file', None))
    ]
    
    empty_file_args = [arg_name for arg_name, arg_value in file_args if arg_value is not None and not arg_value.strip()]
    
    if empty_file_args:
        logging.error(f"Empty file path provided for: {', '.join(empty_file_args)}")
        logging.error("File arguments cannot be empty strings in non-interactive scenarios")
        logging.error("Either provide valid file paths or omit the arguments to use defaults")
        sys.exit(1)
    
    topology_file = args.topology if args.topology else "network_topology.json"
    output_file = args.output if args.output else "network_mld.drawio"
    config_file = args.config_file
    
    # Create config instance with specified file
    config = Config(config_file)
    
    from .diagram_generator import generate_mld_diagram
    
    logging.info("Starting MLD diagram generation...")
    generate_mld_diagram(output_file, topology_file, config)
    logging.info("MLD diagram generation complete.")
    logging.info(f"MLD diagram saved to {output_file}")


def init_config_command(args: argparse.Namespace) -> None:
    """Initialize configuration file in current directory"""
    from .config import Config
    
    output_file = args.output if args.output else "config.yaml"
    
    if os.path.exists(output_file) and not args.force:
        logging.error(f"Configuration file '{output_file}' already exists.")
        logging.error("Use --force to overwrite existing file.")
        sys.exit(1)
    
    try:
        # Get the bundled config path
        config_instance = Config.__new__(Config)
        bundled_config_path = config_instance._get_bundled_config_path()
        
        # Copy bundled config to current directory
        shutil.copy2(bundled_config_path, output_file)
        
        logging.info(f"Configuration file created: {output_file}")
        logging.info("You can now customize the configuration settings.")
        logging.info("Use --config-file to specify this file in other commands.")
        
    except Exception as e:
        logging.error(f"Failed to create configuration file: {e}")
        sys.exit(1)


class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter to prevent help text from wrapping to multiple lines"""
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=70, width=180)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="CloudNet Draw - Azure VNet topology visualization tool",
        formatter_class=CustomHelpFormatter
    )
    
    parser.add_argument('--version', action='version', version=f'CloudNet Draw {__version__}')
    
    subparsers = parser.add_subparsers(dest='command')
    # Don't require subcommands to allow --version to work at top level
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query Azure and collect VNet topology',
                                        formatter_class=CustomHelpFormatter)
    query_parser.add_argument('-o', '--output', default='network_topology.json',
                             help='Output JSON file (default: network_topology.json)')
    query_parser.add_argument('-p', '--service-principal', action='store_true',
                             help='Use Service Principal authentication')
    query_parser.add_argument('-s', '--subscriptions',
                             help='Comma separated list of subscriptions (names or IDs), or "all" to include all subscriptions')
    query_parser.add_argument('-f', '--subscriptions-file',
                             help='File containing subscriptions (one per line)')
    query_parser.add_argument('-c', '--config-file',
                             help='Configuration file (uses bundled default if not specified)')
    query_parser.add_argument('-n', '--vnets',
                             help='Specify hub VNets as comma-separated resource_ids (starting with /) or paths (subscription/resource_group/vnet_name) to filter topology')
    query_parser.add_argument('-v', '--verbose', action='store_true',
                             help='Enable verbose logging')
    query_parser.set_defaults(func=query_command)
    
    # HLD command
    hld_parser = subparsers.add_parser('hld', help='Generate high-level diagram (VNets only)',
                                      formatter_class=CustomHelpFormatter)
    hld_parser.add_argument('-o', '--output', default='network_hld.drawio',
                           help='Output diagram file (default: network_hld.drawio)')
    hld_parser.add_argument('-t', '--topology', default='network_topology.json',
                           help='Input topology JSON file (default: network_topology.json)')
    hld_parser.add_argument('-c', '--config-file',
                           help='Configuration file (uses bundled default if not specified)')
    hld_parser.add_argument('-v', '--verbose', action='store_true',
                           help='Enable verbose logging')
    hld_parser.set_defaults(func=hld_command)
    
    # MLD command
    mld_parser = subparsers.add_parser('mld', help='Generate mid-level diagram (VNets + subnets)',
                                      formatter_class=CustomHelpFormatter)
    mld_parser.add_argument('-o', '--output', default='network_mld.drawio',
                           help='Output diagram file (default: network_mld.drawio)')
    mld_parser.add_argument('-t', '--topology', default='network_topology.json',
                           help='Input topology JSON file (default: network_topology.json)')
    mld_parser.add_argument('-c', '--config-file',
                           help='Configuration file (uses bundled default if not specified)')
    mld_parser.add_argument('-v', '--verbose', action='store_true',
                           help='Enable verbose logging')
    mld_parser.set_defaults(func=mld_command)
    
    # Init-config command
    init_parser = subparsers.add_parser('init-config', help='Generate configuration file in current directory',
                                       formatter_class=CustomHelpFormatter)
    init_parser.add_argument('-o', '--output', default='config.yaml',
                           help='Output configuration file (default: config.yaml)')
    init_parser.add_argument('-f', '--force', action='store_true',
                           help='Overwrite existing configuration file')
    init_parser.add_argument('-v', '--verbose', action='store_true',
                           help='Enable verbose logging')
    init_parser.set_defaults(func=init_config_command)
    
    return parser


def main() -> None:
    """Main CLI entry point with subcommand dispatch"""
    parser = create_parser()
    
    # Parse arguments and dispatch to appropriate function
    args = parser.parse_args()
    
    # Check if no command was provided (but --version was handled automatically by argparse)
    if not hasattr(args, 'func') or args.func is None:
        parser.error("the following arguments are required: command")
    
    # Configure logging based on verbose flag (only exists when subcommand is provided)
    log_level = logging.INFO if getattr(args, 'verbose', False) else logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        args.func(args)
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()