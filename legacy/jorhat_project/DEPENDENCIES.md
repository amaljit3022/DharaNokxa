# Dependencies

## Purpose

This document records the dependencies required to run the repository at `C:\Automation\WNTR`.

There is no native `requirements.txt` or `pyproject.toml` in the repository, so this file is derived from:

- the Python imports in project scripts
- the active virtual environment package versions
- the runtime behavior of the project

## Python Version

- Python `3.12.10`

## Core Runtime Dependencies

These packages are required by the current scripts:

| Package | Version Seen | Purpose |
|---|---:|---|
| `wntr` | `1.4.0` | EPANET/WNTR network model creation, simulation, and resilience analysis |
| `geopandas` | `1.1.3` | Reading shapefiles and building GIS layers |
| `pandas` | `3.0.1` | Tabular processing and CSV export |
| `shapely` | `2.1.2` | Geometry handling and line / point construction |
| `fiona` | `1.10.1` | GIS file backend used by GeoPandas |
| `pyproj` | `3.7.2` | Coordinate reference support used by GIS stack |
| `networkx` | `3.6.1` | Graph analysis for criticality and redundancy |
| `matplotlib` | `3.10.8` | Plot and map export |
| `numpy` | `2.4.3` | Numeric support used by Pandas / GeoPandas / WNTR |

## Supporting / Optional Dependencies

These are useful or indirectly required:

| Package | Version Seen | Purpose |
|---|---:|---|
| `pyogrio` | `0.12.1` | Fast GIS I/O backend in the GeoPandas stack |
| `scipy` | `1.17.1` | Scientific computing dependency used by WNTR |
| `rasterio` | `1.5.0` | Raster / GIS support present in the environment |
| `jupyter` | `1.1.1` | Notebook environment, not required by current scripts |
| `openpyxl` | not installed in current venv | Recommended if `.xlsx` design sheets need to be parsed directly |

## Non-Python Tools / File Ecosystem

The repository also depends on external engineering data ecosystems:

- ESRI Shapefile datasets
- Bentley WaterGEMS `.wtg` and `.wtg.sqlite`
- EPANET `.inp`
- PDF engineering reports
- Excel spreadsheets
- ArcMap `.mxd`

## Imports Found in Project Scripts

### `analyze_project.py`

Standard library:

- `json`
- `math`
- `re`
- `sqlite3`
- `dataclasses`
- `pathlib`

Third-party:

- `geopandas`
- `matplotlib`
- `matplotlib.pyplot`
- `networkx`
- `pandas`
- `wntr`

### `create_comprehensive_map.py`

Standard library:

- `json`
- `pathlib`

Third-party:

- `geopandas`
- `matplotlib`
- `matplotlib.pyplot`
- `pandas`
- `matplotlib.lines`
- `matplotlib.patches`
- `mpl_toolkits.axes_grid1.inset_locator`
- `shapely.geometry`

## Recommended Minimal Installation

```powershell
pip install wntr geopandas pandas shapely fiona pyproj networkx matplotlib pyogrio numpy scipy rasterio
```

Recommended additional package:

```powershell
pip install openpyxl
```

## Current Environment Snapshot

Packages observed in the active `venv` that are most relevant to this project:

```text
wntr==1.4.0
geopandas==1.1.3
pandas==3.0.1
shapely==2.1.2
fiona==1.10.1
pyproj==3.7.2
networkx==3.6.1
matplotlib==3.10.8
numpy==2.4.3
scipy==1.17.1
pyogrio==0.12.1
rasterio==1.5.0
jupyter==1.1.1
```

## Dependency Notes

- `openpyxl` was missing when Excel inspection was attempted; install it if spreadsheet parsing is needed.
- Matplotlib may try to write cache files to the user profile. Use:

```powershell
$env:MPLCONFIGDIR='C:\Automation\WNTR\results\mplcache'
```

- GeoPandas depends on compiled GIS packages such as Fiona, PyProj, and Shapely. Install all of them in the same environment.

## Recommended Next Step

Generate and commit a repository-native dependency file:

```powershell
pip freeze > requirements_recreated.txt
```

or create a curated manual file such as:

- `requirements.txt`

to make rebuilds reproducible.
