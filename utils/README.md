# Utility Scripts

CLI tools for generating and testing CloudNet Draw topologies.

## Scripts

### topology-generator.py
Generates Azure network topology JSON files with configurable parameters.
```bash
python3 topology-generator.py --vnets 50 --centralization 8 --connectivity 6 --isolation 2 --output topology.json
```

### topology-validator.py  
Validates JSON topologies and generated diagrams for structural integrity.
```bash
python3 topology-validator.py path/to/files/
```

### topology-randomizer.py
Parallel stress testing with random topology generation and validation.
```bash
python3 topology-randomizer.py --iterations 25 --vnets 100 --parallel-jobs 4
```

All scripts support `--help` for detailed usage information.