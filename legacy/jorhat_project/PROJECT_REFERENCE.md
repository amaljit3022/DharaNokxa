# Project Reference

## Project Overview

This repository contains a GIS-to-EPANET/WNTR workflow for the Jorhat water distribution system. The project uses distribution-zone shapefiles and WaterGEMS design files to:

- scan and inventory available hydraulic / GIS data
- convert GIS-based network geometry into an EPANET `.inp` model
- run hydraulic simulation in WNTR
- calculate pressures, flows, headloss, and resilience metrics
- generate tabular outputs and map-based visualizations

The repository is partly data-driven and partly script-driven. The original repository mostly contains engineering source data. The executable pipeline currently depends on two Python scripts created in the repository root:

- `analyze_project.py`
- `create_comprehensive_map.py`

There is no existing `requirements.txt`, `pyproject.toml`, `setup.py`, `environment.yml`, or Jupyter notebook in the repository root. Rebuild instructions therefore rely on the active virtual environment and the imports used in the scripts.

## Technology Stack

### Core runtime

- Python `3.12.10`
- Windows / PowerShell workflow
- Local virtual environment in `venv`

### Python libraries confirmed in the active environment

- `wntr==1.4.0`
- `geopandas==1.1.3`
- `pandas==3.0.1`
- `shapely==2.1.2`
- `fiona==1.10.1`
- `pyproj==3.7.2`
- `networkx==3.6.1`
- `matplotlib==3.10.8`
- `jupyter==1.1.1`
- `pyogrio==0.12.1`
- `numpy==2.4.3`
- `rasterio==1.5.0`
- `scipy==1.17.1`

### GIS / hydraulic modeling technologies detected

- ESRI Shapefile: primary GIS network source
- WaterGEMS / Bentley `.wtg` and `.wtg.sqlite`: hydraulic design source
- EPANET `.inp`: generated network model format
- WNTR: hydraulic simulation and resilience analysis
- Matplotlib + GeoPandas: map generation
- SQLite: direct inspection of WaterGEMS databases
- ArcMap `.mxd`: one legacy map document was found under distribution GIS

### Standard-library modules used by the scripts

- `json`
- `math`
- `re`
- `sqlite3`
- `dataclasses`
- `pathlib`

## Folder Structure

```text
C:\Automation\WNTR
├── JORHAT
│   └── GIS FILE
│       ├── DIST
│       │   ├── GIS FILE 1
│       │   ├── GIS FILE 2
│       │   ├── GIS FILE 3
│       │   ├── GIS FILE 5
│       │   ├── GIS FILE 6
│       │   └── GIS FILE 7
│       └── Jorhat project area
│           └── Jorhat project area
├── JORHAT DESIGN FILE
│   ├── JORHAT CLEAR WATER MAIN
│   ├── zone-1
│   ├── ZONE-2
│   ├── ZONE-3
│   ├── ZONE-5
│   ├── ZONE-6
│   └── ZONE-7
├── models
│   └── inp_files
├── results
│   └── mplcache
├── venv
├── analyze_project.py
├── create_comprehensive_map.py
├── temp.bin
└── temp.rpt
```

### Folder purposes

- `JORHAT`
  Raw GIS inputs for the distribution system and project-area context layers.
- `JORHAT/GIS FILE/DIST`
  Zone-specific distribution network GIS layers used for conversion to EPANET/WNTR.
- `JORHAT/GIS FILE/Jorhat project area/Jorhat project area`
  Context GIS layers such as ESRs, ward boundaries, zoning, roads, pipelines, and crossings.
- `JORHAT DESIGN FILE`
  WaterGEMS design databases, reports, and spreadsheets for each zone and for clear-water main systems.
- `models/inp_files`
  Generated EPANET model output.
- `results`
  Generated CSV outputs, JSON inventory, markdown analysis, plots, maps, and recommendation tables.
- `venv`
  Local Python virtual environment used to execute the project.

### Runtime-generated temporary files

- `temp.bin`
- `temp.rpt`

These are EPANET/WNTR simulator side-products. They are not source data.

## Data Inputs

### Primary input formats

- `.shp`, `.dbf`, `.shx`
  Distribution GIS and project-area GIS layers.
- `.sqlite`
  WaterGEMS SQLite-backed models.
- `.wtg`
  WaterGEMS project files.
- `.xlsx`
  WaterGEMS export spreadsheets and clear-water-main reports.
- `.pdf`
  Engineering report exports.
- `.mxd`
  Legacy ArcMap document.

### Distribution-zone GIS inputs used directly by the scripts

- Zone 1:
  `JORHAT\GIS FILE\DIST\GIS FILE 1\Node Details.shp`
  `JORHAT\GIS FILE\DIST\GIS FILE 1\Pipe Details.shp`
- Zone 2:
  `JORHAT\GIS FILE\DIST\GIS FILE 2\Node Details Z-2.shp`
  `JORHAT\GIS FILE\DIST\GIS FILE 2\Pipe Details Z-2.shp`
- Zone 3:
  `JORHAT\GIS FILE\DIST\GIS FILE 3\JUNCTION DETAILS.shp`
  `JORHAT\GIS FILE\DIST\GIS FILE 3\PIPE DETAILS.shp`
- Zone 5:
  `JORHAT\GIS FILE\DIST\GIS FILE 5\Junction Details Z-5.shp`
  `JORHAT\GIS FILE\DIST\GIS FILE 5\Pipe Details Z-5.shp`
- Zone 6:
  `JORHAT\GIS FILE\DIST\GIS FILE 6\GIS FILE\Junction details.shp`
  `JORHAT\GIS FILE\DIST\GIS FILE 6\GIS FILE\Pipe details.shp`
- Zone 7:
  `JORHAT\GIS FILE\DIST\GIS FILE 7\NODE DETAILS Z-7.shp`
  `JORHAT\GIS FILE\DIST\GIS FILE 7\PIPE DETAILS Z-7.shp`

### Project-area GIS context layers

- `Existing & Proposed ESR.shp`
- `RWM_&_CWM.shp`
- `Ward map.shp`
- `zoning.shp`
- `ROAD.shp`
- `CROSSING.shp`
- `Point_Load.shp`
- `sample.shp`

### WaterGEMS / design source files

- Clear water main:
  `JORHAT DESIGN FILE\JORHAT CLEAR WATER MAIN\*.wtg`
  `JORHAT DESIGN FILE\JORHAT CLEAR WATER MAIN\*.wtg.sqlite`
- Zone design databases:
  each zone folder contains `.wtg`, `.wtg.sqlite`, `.xlsx`, `.out`, `.rpc`, `.bak`, `.dwh`

### Important input attributes used by the scripts

#### Junction shapefiles

- `DEMAND`
- `ELEV`
- `HGL`
- `ID`
- `LABEL`
- `P`
- `geometry`

#### Pipe shapefiles

- `D`
- `Q`
- `C`
- `L`
- `USER_L`
- `MATERIAL`
- `START_NODE`
- `STOP_NODE`
- `ID`
- `LABEL`
- `geometry`

## Processing Pipeline

### 1. Data ingestion

`analyze_project.py` recursively scans the repository for supported source formats and inventories them.

Main functions:

- `list_data_sources()`
- `inventory_project_area_layers()`
- `inventory_design_sources()`
- `sqlite_counts()`

### 2. GIS preprocessing

The script locates one junction shapefile and one pipe shapefile for each distribution zone and standardizes labels:

- node labels are coerced to string
- pipe start / stop nodes are coerced to string
- safe EPANET IDs are generated with `safe_id()`
- zone IDs are parsed with `zone_code()`

Main functions:

- `load_zone_layers()`
- `safe_id()`
- `zone_code()`
- `source_endpoint_coords()`

### 3. Network creation

For each zone:

- each GIS point becomes a WNTR junction
- demands are converted from L/s-style values to m3/s for WNTR
- elevations and coordinates are assigned to junctions
- each GIS line becomes a WNTR pipe
- diameter, length, and Hazen-Williams roughness are taken from GIS attributes

If a pipe endpoint is not found in the node layer, the script infers a source tank at that endpoint using:

- mean connected-node HGL
- mean connected-node elevation
- endpoint geometry from the line feature

Main function:

- `build_model()`

### 4. EPANET / WNTR model generation

The script creates a `wntr.network.WaterNetworkModel`, configures hydraulic options, then writes:

- `models\inp_files\jorhat_combined_distribution.inp`

Hydraulic options set in the script:

- headloss method: `H-W`
- demand model: `PDD`
- required pressure: `15.0 m`
- minimum pressure: `0.0 m`
- pressure exponent: `0.5`
- hydraulic timestep: `3600 s`
- report timestep: `3600 s`
- units: `LPS`

### 5. Hydraulic simulation

Simulation is run by attempting:

1. `wntr.sim.EpanetSimulator`
2. fallback to `wntr.sim.WNTRSimulator`

Main function:

- `run_simulation(inp_path)`

### 6. Pressure, flow, and headloss extraction

The script reads the final reporting timestep and exports:

- node pressure
- node head
- node delivered demand
- pipe flowrate
- pipe velocity
- pipe headloss

Main function:

- `write_outputs(...)`

### 7. Resilience metric calculation

The script computes:

- network reliability
- pressure deficiency
- pipe criticality
- supply redundancy

Main functions:

- `compute_pipe_criticality()`
- `compute_supply_redundancy()`
- `build_multigraph()`

### 8. Visualization and map generation

Two visualization flows exist:

- WNTR network plots from `analyze_project.py`
- GIS-composed map layout from `create_comprehensive_map.py`

The second script overlays critical pipes, ESRs, ward boundaries, zone boundaries, source tanks, low-pressure nodes, and recommended transmitter sites.

## Hydraulic Analysis Workflow

### Script sequence

1. Create output folders with `ensure_dirs()`
2. Scan all supported source files
3. Inventory project-area GIS layers
4. Inventory WaterGEMS SQLite and spreadsheet design sources
5. Convert six GIS distribution zones into a unified WNTR model
6. Infer missing source tanks where GIS node layers omit one source endpoint per zone
7. Write a consolidated EPANET `.inp`
8. Simulate hydraulics in WNTR / EPANET
9. Export node and pipe result tables
10. Compute resilience metrics
11. Save inventory JSON/CSV and data-gap template
12. Generate basic pressure, flow, and criticality network plots

### Metric definitions used

- `network_reliability`
  Delivered junction demand divided by expected junction demand under the steady-state PDD run.
- `pressure_deficiency`
  Sum of pressure deficits below the required pressure threshold of 15 m.
- `pipe_criticality_score`
  Disconnected demand after removing one pipe divided by total expected demand.
- `supply_redundancy`
  Average edge-connectivity from each junction to the set of source nodes.

## Map Generation Workflow

### GIS layers used

- Ward boundaries from `Ward map.shp`
- Zone boundaries from `zoning.shp`
- ESR points from `Existing & Proposed ESR.shp`
- Main transmission pipelines from `RWM_&_CWM.shp`
- Distribution nodes and pipes from zone shapefiles
- Analysis outputs from:
  `results\node_pressure.csv`
  `results\pipe_flow.csv`
  `results\data_inventory.json`

### Mapping logic

`create_comprehensive_map.py`:

- reloads the original distribution geometries
- joins simulated pressure and criticality outputs
- highlights low-pressure nodes where `pressure_m < 12`
- highlights critical pipes where `criticality_score >= 0.05`
- draws recommended pressure transmitter points
- exports:
  - `critical_pipe_comprehensive_map.png`
  - `critical_pipe_comprehensive_map.pdf`
  - `pressure_transmitter_recommendations.csv`

### Cartographic elements added

- legend
- labels for ESRs
- labels for recommended pressure transmitters
- north arrow
- scale bar
- inset map focusing on Zone 1 low-pressure area

## Scripts and Their Roles

### `analyze_project.py`

Purpose:

- master pipeline for data inventory, GIS-to-WNTR conversion, simulation, metrics, and tabular / plot outputs

Important functions:

- `ensure_dirs()`
  Creates `models\inp_files` and `results`.
- `list_data_sources()`
  Inventories supported input formats.
- `inventory_project_area_layers()`
  Scans project-area GIS layers and extracts ESR metadata.
- `sqlite_counts()`
  Counts key WaterGEMS elements from SQLite databases.
- `inventory_design_sources()`
  Collects spreadsheet and SQLite design sources.
- `load_zone_layers()`
  Identifies zone-level pipe and node shapefile pairs.
- `build_model()`
  Constructs the WNTR network and inferred tanks from GIS.
- `run_simulation()`
  Executes EPANET/WNTR hydraulics.
- `build_multigraph()`
  Builds a graph representation of the water network.
- `compute_pipe_criticality()`
  Calculates single-pipe outage impact by disconnected demand fraction.
- `compute_supply_redundancy()`
  Estimates average source-to-node edge connectivity.
- `save_plots()`
  Writes WNTR-based pressure, flow, and critical-pipe figures.
- `write_outputs()`
  Exports CSV, JSON, summary tables, plots, and the data template.
- `main()`
  Orchestrates the full pipeline and writes the consolidated `.inp`.

### `create_comprehensive_map.py`

Purpose:

- produces a publication-style GIS map using source GIS layers plus analysis outputs

Important functions:

- `load_distribution_layers()`
  Reloads raw zone shapefile geometry.
- `load_analysis_layers()`
  Loads `node_pressure.csv`, `pipe_flow.csv`, and `data_inventory.json`, then reconstructs map-ready layers.
- `recommendation_points()`
  Builds the recommended pressure-transmitter layer.
- `add_north_arrow()`
  Draws a north arrow.
- `add_scale_bar()`
  Draws a 1 km scale bar.
- `create_map()`
  Builds the full map layout and exports PNG/PDF/CSV.

## Environment Setup

### Existing environment in the repository

The repository already contains a local virtual environment:

- `C:\Automation\WNTR\venv`

### Recreate a fresh environment

In PowerShell:

```powershell
cd C:\Automation\WNTR
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Minimum package installation

Because no dependency file exists in the repository, install the packages inferred from the active environment:

```powershell
pip install wntr geopandas pandas shapely fiona pyproj networkx matplotlib pyogrio numpy scipy rasterio jupyter
```

Recommended if spreadsheet inspection is needed later:

```powershell
pip install openpyxl
```

`openpyxl` is not required by the current scripts, but it is useful for reading the `.xlsx` design files directly.

### Optional: reproduce the current environment more closely

The active `venv` contains many Jupyter-related packages. A full reproduction can be captured with:

```powershell
pip freeze > requirements_recreated.txt
```

## Execution Steps

### Standard run order

1. Activate the virtual environment
2. Run hydraulic conversion and analysis
3. Run the detailed GIS map generation
4. Review outputs under `results`

### Commands

```powershell
cd C:\Automation\WNTR
.\venv\Scripts\Activate.ps1
$env:MPLCONFIGDIR='C:\Automation\WNTR\results\mplcache'
python analyze_project.py
python create_comprehensive_map.py
```

### Why `MPLCONFIGDIR` is set

Matplotlib attempted to write cache files to the user profile during execution. Setting `MPLCONFIGDIR` to `results\mplcache` keeps cache writes local to the project and avoids permission errors.

### Expected execution order

Run `analyze_project.py` first because `create_comprehensive_map.py` depends on:

- `results\node_pressure.csv`
- `results\pipe_flow.csv`
- `results\data_inventory.json`

## Output Files

### Model output

- `models\inp_files\jorhat_combined_distribution.inp`

### Analysis tables

- `results\hydraulic_results.csv`
- `results\node_pressure.csv`
- `results\pipe_flow.csv`
- `results\network_metrics.csv`
- `results\data_inventory_summary.csv`
- `results\data_sources.csv`
- `results\data_template.csv`
- `results\pressure_transmitter_recommendations.csv`

### Analysis metadata

- `results\data_inventory.json`

### Plots and maps

- `results\pressure_map.png`
- `results\pipe_flow_map.png`
- `results\critical_pipes.png`
- `results\critical_pipe_comprehensive_map.png`
- `results\critical_pipe_comprehensive_map.pdf`

### Markdown reports

- `results\project_analysis.md`
- `PROJECT_REFERENCE.md`

## Rebuild Project From Scratch

This section is intended to preserve the project even if prior AI conversation context is lost.

### 1. Recover the raw source data

Ensure these source folders exist:

- `JORHAT`
- `JORHAT DESIGN FILE`

The project depends on the distribution GIS shapefiles and the WaterGEMS design databases inside those folders.

### 2. Create a Python environment

```powershell
cd C:\Automation\WNTR
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install wntr geopandas pandas shapely fiona pyproj networkx matplotlib pyogrio numpy scipy rasterio jupyter openpyxl
```

### 3. Restore or recreate the main scripts

The pipeline logic lives in:

- `analyze_project.py`
- `create_comprehensive_map.py`

If these are missing, rebuild them from version control or from this reference document plus the generated outputs.

### 4. Run the main analysis

```powershell
$env:MPLCONFIGDIR='C:\Automation\WNTR\results\mplcache'
python analyze_project.py
```

This will:

- scan the repository
- build the WNTR model
- write the EPANET `.inp`
- run hydraulics
- export CSV and JSON outputs
- create basic plots

### 5. Run the GIS map generation

```powershell
python create_comprehensive_map.py
```

This will:

- reload GIS layers
- join simulation results
- highlight critical pipes and low-pressure nodes
- export the comprehensive critical-pipe map

### 6. Validate that key outputs exist

At minimum, confirm the presence of:

- `models\inp_files\jorhat_combined_distribution.inp`
- `results\hydraulic_results.csv`
- `results\network_metrics.csv`
- `results\node_pressure.csv`
- `results\pipe_flow.csv`
- `results\critical_pipe_comprehensive_map.png`

### 7. Preserve the recreated environment

After a successful rebuild, capture the exact dependency set:

```powershell
pip freeze > requirements_recreated.txt
```

That file should be committed if long-term reproducibility is required.

## Notes for Future Development

- Add a proper `requirements.txt` or `pyproject.toml` to remove dependence on environment inspection.
- Commit a reproducible environment export such as `requirements_recreated.txt`.
- Add direct support for WaterGEMS `.xlsx` inspection; current scripts do not parse spreadsheets.
- Consider extracting reservoir, valve, and pump geometry directly from WaterGEMS SQLite tables instead of relying mainly on shapefiles.
- Add explicit CRS handling because several shapefiles return `CRS None`.
- Add demand-pattern support for extended-period simulation; the current model is steady-state.
- Consider splitting the project into:
  - `src/` for reusable code
  - `data/` for raw inputs
  - `models/` for generated INP
  - `results/` for derived outputs
- Add automated tests for:
  - data-source detection
  - GIS field validation
  - EPANET model creation
  - resilience metric calculations
- Decide whether `temp.bin` and `temp.rpt` should be gitignored or retained.
- If notebook-based workflows are introduced later, store them under a dedicated `notebooks/` folder and document their execution order.
