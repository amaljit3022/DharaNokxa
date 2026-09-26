# Project Reference

## Project Overview

This repository is now the starting point for a general-purpose water supply scheme analysis toolkit.

The previous Jorhat implementation has been preserved without deletion in:

- `legacy/jorhat_project`

The root project is intended to evolve into a reusable system that can support:

- GIS-only schemes
- EPANET-only schemes
- WaterGEMS-supported schemes
- mixed-data water distribution projects

## Repository Modes

### 1. Legacy archive mode

The archived Jorhat scheme is preserved exactly for:

- rerunning historical analysis
- comparing future generalized outputs
- reusing real engineering source data as a test case

### 2. General toolkit mode

The repository root now contains:

- generic docs
- generic dependency definitions
- generic run commands
- sample scheme configuration
- Python package scaffold under `src`

## Root Folder Structure

```text
C:\Automation\WNTR
├── configs\schemes
├── data\raw
├── data\processed
├── docs
├── legacy\jorhat_project
├── models
├── results
├── src\water_scheme_toolkit
└── templates
```

## Purpose of Each Root Folder

- `configs/schemes`
  Per-scheme YAML configuration files.
- `data/raw`
  Input data for new generalized schemes.
- `data/processed`
  Standardized or preprocessed data products.
- `docs`
  Space for future design notes, examples, and user guides.
- `legacy/jorhat_project`
  Archived Jorhat implementation and data.
- `models`
  Generated EPANET / WNTR or intermediate model files.
- `results`
  Reports, CSVs, figures, and exported outputs.
- `src/water_scheme_toolkit`
  Python package for generalized ingestion, validation, modeling, analysis, mapping, and reporting.
- `templates`
  Config templates and data templates for onboarding new schemes.

## Source Code Modules

### `src/water_scheme_toolkit/config.py`

Loads and normalizes scheme YAML configuration.

### `src/water_scheme_toolkit/validation.py`

Validates that required input paths and configuration sections exist.

### `src/water_scheme_toolkit/pipeline.py`

Provides command handlers for:

- validate
- build-model
- simulate
- analyze
- map
- report

At this stage the handlers are scaffolded and intentionally minimal.

### `src/water_scheme_toolkit/cli.py`

Command-line entry point for generalized workflows.

## Configuration Strategy

Each new water scheme should be described by a YAML file in:

- `configs/schemes`

That file should define:

- project metadata
- input paths
- field mappings
- unit assumptions
- simulation options
- output directories

## Templates Included

- `templates/scheme.template.yaml`
- `templates/field_mapping.template.yaml`
- `templates/data_template.csv`
- `configs/schemes/sample_scheme.yaml`

## Legacy Preservation Note

The Jorhat work was moved into a folder instead of a Git branch because this workspace is not currently a Git repository.

If versioned branch-based preservation is required later, initialize Git and commit:

1. the archive state
2. the new generalized scaffold

## Rebuild Intent

The long-term goal is that a new engineer can:

1. drop raw scheme data into `data/raw/...`
2. create a scheme YAML config
3. run the CLI
4. generate model, results, and maps without editing project code
