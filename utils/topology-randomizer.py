#!/usr/bin/env python3
"""
Parallelized stress test script for CloudNet Draw topology generation
Generates random topologies and validates them to find edge cases
"""

import argparse
import json
import multiprocessing
import os
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class IterationResult:
    """Result from a single stress test iteration"""
    iteration: int
    success: bool
    output_line: str
    error_message: Optional[str] = None


class StressTestRunner:
    """Manages parallel stress testing of topology generation"""
    
    def __init__(self, args):
        self.args = args
        self.temp_dir = Path(tempfile.mkdtemp())
        self.error_log = self.temp_dir / "errors.log"
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def run_single_iteration(self, iteration: int) -> IterationResult:
        """Run a single stress test iteration"""
        try:
            # Generate random weights within bounds
            total_vnets = self.args.vnets
            centralization = random.randint(0, self.args.max_centralization)
            connectivity = random.randint(0, self.args.max_connectivity) 
            isolation = random.randint(0, self.args.max_isolation)
            
            # Create unique temporary files
            base_name = f"stress_test_{iteration}_vnt{total_vnets}_cen{centralization}_con{connectivity}_iso{isolation}"
            json_file = self.temp_dir / f"{base_name}.json"
            hld_file = self.temp_dir / f"{base_name}_hld.drawio"
            mld_file = self.temp_dir / f"{base_name}_mld.drawio"
            
            # Build output line progressively
            output_line = f"Iteration {iteration:3d}/{self.args.iterations:3d}: vnt {total_vnets:3d} cen {centralization:2d} con {connectivity:2d} iso {isolation:2d} "
            
            # Build generator command
            generator_cmd = [
                "python3", "topology-generator.py",
                "--vnets", str(total_vnets),
                "--centralization", str(centralization), 
                "--connectivity", str(connectivity),
                "--isolation", str(isolation),
                "--output", str(json_file)
            ]
            
            # Add optional arguments
            if self.args.seed is not None:
                generator_cmd.extend(["--seed", str(self.args.seed)])
                output_line += f"seed {self.args.seed} "
                
            if self.args.ensure_all_edge_types:
                generator_cmd.append("--ensure-all-edge-types")
                output_line += "[EdgeType guarantee] "
            
            # Generate topology JSON
            result = subprocess.run(generator_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return IterationResult(
                    iteration, False, f"{output_line}ERROR: Failed to generate topology JSON",
                    f"Generator failed: {result.stderr}"
                )
            
            # Extract topology info from generator output
            generator_output = result.stdout.strip()
            topology_line = [line for line in generator_output.split('\n') if 'Generated' in line]
            if topology_line:
                line = topology_line[0]
                # Parse hub/spoke/isolated counts from output
                import re
                hubs_match = re.search(r'(\d+) hubs', line)
                spokes_match = re.search(r'(\d+) spokes', line)
                isolated_match = re.search(r'(\d+) isolated', line)
                
                hubs = hubs_match.group(1) if hubs_match else "0"
                spokes = spokes_match.group(1) if spokes_match else "0" 
                isolated = isolated_match.group(1) if isolated_match else "0"
                
                output_line += f"→ {hubs:>3s} hubs, {spokes:>3s} spokes, {isolated:>3s} isolated "
            
            # Validate JSON file
            if not json_file.exists():
                return IterationResult(iteration, False, f"{output_line}ERROR: JSON file not created")
                
            try:
                with open(json_file, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError:
                return IterationResult(iteration, False, f"{output_line}ERROR: Invalid JSON generated")
            
            # Generate HLD diagram
            hld_cmd = ["uv", "run", "cloudnetdraw", "hld", "-t", str(json_file), "-o", str(hld_file)]
            result = subprocess.run(hld_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return IterationResult(
                    iteration, False, f"{output_line}ERROR: Failed to generate HLD diagram",
                    f"HLD generation failed: {result.stderr}"
                )
            
            # Generate MLD diagram
            mld_cmd = ["uv", "run", "cloudnetdraw", "mld", "-t", str(json_file), "-o", str(mld_file)]
            result = subprocess.run(mld_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return IterationResult(
                    iteration, False, f"{output_line}ERROR: Failed to generate MLD diagram", 
                    f"MLD generation failed: {result.stderr}"
                )
            
            # Validate the generated files
            validator_cmd = ["python3", "topology-validator.py", "--topology", str(json_file), "--hld", str(hld_file), "--mld", str(mld_file)]
            result = subprocess.run(validator_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return IterationResult(
                    iteration, False, f"{output_line}ERROR: Validation failed",
                    f"Validation failed: {result.stderr}"
                )
            
            # Extract validation info
            validation_output = result.stdout.strip()
            validation_line = [line for line in validation_output.split('\n') if 'PASSED' in line]
            if validation_line:
                line = validation_line[0]
                # Parse VNet and edge counts
                import re
                vnets_match = re.search(r'(\d+) VNets', line)
                edges_match = re.search(r'(\d+) edges', line)
                
                vnets = vnets_match.group(1) if vnets_match else "0"
                edges = edges_match.group(1) if edges_match else "0"
                
                output_line += f"✓ {vnets:>4s} vnets {edges:>4s} edges"
            
            # Check file sizes
            if not hld_file.exists() or hld_file.stat().st_size == 0 or \
               not mld_file.exists() or mld_file.stat().st_size == 0:
                return IterationResult(iteration, False, f"{output_line} ERROR: Empty diagram files generated")
            
            output_line += " OK"
            return IterationResult(iteration, True, output_line)
            
        except Exception as e:
            return IterationResult(iteration, False, f"Iteration {iteration}: ERROR: {str(e)}", str(e))
    
    def run_all_iterations(self) -> Tuple[int, List[str]]:
        """Run all stress test iterations in parallel"""
        print(f"Starting {self.args.iterations} stress test iterations with up to {self.args.parallel_jobs} parallel jobs...")
        
        errors = []
        failed_count = 0
        
        # Use ProcessPoolExecutor for parallel execution
        with ProcessPoolExecutor(max_workers=self.args.parallel_jobs) as executor:
            # Submit all iterations
            future_to_iteration = {
                executor.submit(self.run_single_iteration, i): i 
                for i in range(1, self.args.iterations + 1)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_iteration):
                try:
                    result = future.result()
                    print(result.output_line)
                    
                    if not result.success:
                        failed_count += 1
                        if result.error_message:
                            errors.append(f"Iteration {result.iteration}: {result.error_message}")
                            
                except Exception as e:
                    iteration = future_to_iteration[future]
                    failed_count += 1
                    error_msg = f"Iteration {iteration} raised exception: {str(e)}"
                    errors.append(error_msg)
                    print(f"Iteration {iteration:3d}/{self.args.iterations:3d}: ERROR: {str(e)}")
        
        return failed_count, errors


def parse_arguments():
    """Parse command line arguments with proper CLI switches"""
    parser = argparse.ArgumentParser(
        description='Parallelized stress test script for CloudNet Draw topology generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --iterations 10 --vnets 100 --parallel-jobs 4
  %(prog)s -i 50 -v 200 -p 8 --seed 42 --ensure-all-edge-types
  %(prog)s --iterations 20 --vnets 150 --max-centralization 8 --max-connectivity 8 --max-isolation 5
        """
    )
    
    # Core test parameters
    core_group = parser.add_argument_group('core test parameters')
    core_group.add_argument('-i', '--iterations', type=int, default=10,
                           help='Number of stress test iterations (default: 10)')
    core_group.add_argument('-v', '--vnets', type=int, default=100,
                           help='Fixed number of VNets for all iterations (default: 100)')
    core_group.add_argument('-p', '--parallel-jobs', type=int, default=4,
                           help='Maximum number of parallel jobs (default: 4)')
    
    # Topology generation bounds
    bounds_group = parser.add_argument_group('topology generation bounds')
    bounds_group.add_argument('--max-centralization', type=int, default=10,
                             help='Upper bound for centralization weight (default: 10)')
    bounds_group.add_argument('--max-connectivity', type=int, default=10,
                             help='Upper bound for connectivity weight (default: 10)')  
    bounds_group.add_argument('--max-isolation', type=int, default=10,
                             help='Upper bound for isolation weight (default: 10)')
    
    # Generator options
    generator_group = parser.add_argument_group('generator options')
    generator_group.add_argument('--seed', type=int,
                                help='Random seed for reproducible generation')
    generator_group.add_argument('--ensure-all-edge-types', action='store_true',
                                help='Ensure all 6 EdgeTypes are present in generated topologies')
    
    return parser.parse_args()


def main():
    """Main stress test function"""
    args = parse_arguments()
    
    # Validate arguments
    if args.iterations <= 0:
        print("ERROR: iterations must be positive")
        sys.exit(1)
    if args.vnets <= 0:
        print("ERROR: vnets must be positive") 
        sys.exit(1)
    if args.parallel_jobs <= 0:
        print("ERROR: parallel-jobs must be positive")
        sys.exit(1)
    
    try:
        with StressTestRunner(args) as runner:
            failed_count, errors = runner.run_all_iterations()
            
            # Show any errors that occurred
            if errors:
                print("\n=== ERRORS ===")
                for error in errors:
                    print(error)
            
            # Final summary
            if failed_count > 0:
                print(f"\nFAILED: {failed_count} out of {args.iterations} iterations failed")
                sys.exit(1)
            else:
                print(f"\nSUCCESS: All {args.iterations} iterations completed without errors")
                print(f"Parameters used: vnets={args.vnets}, max_centralization={args.max_centralization}, max_connectivity={args.max_connectivity}, max_isolation={args.max_isolation}")
                print(f"Parallel jobs: {args.parallel_jobs}")
                if args.seed is not None:
                    print(f"Seed: {args.seed}")
                if args.ensure_all_edge_types:
                    print("EdgeType guarantee system: enabled")
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()