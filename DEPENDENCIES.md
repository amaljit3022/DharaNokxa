# Dependencies

## Purpose

This file describes the dependencies for the new generalized toolkit at the repository root.

The archived Jorhat environment remains inside:

- `legacy/jorhat_project`

and includes its own dependency snapshot.

## Python Version

Recommended:

- Python `3.12+`

## Core Dependencies

| Package | Purpose |
|---|---|
| `PyYAML` | Scheme configuration parsing |
| `pandas` | Tabular data handling |
| `geopandas` | GIS vector data handling |
| `shapely` | Geometry construction and processing |
| `fiona` | GIS file I/O backend |
| `pyproj` | Coordinate transformation support |
| `networkx` | Network graph analysis |
| `matplotlib` | Plotting and map rendering |
| `wntr` | Hydraulic network modeling and simulation |
| `numpy` | Numeric support |
| `pyogrio` | Fast vector GIS reads with GeoPandas |

## Optional Dependencies

| Package | Purpose |
|---|---|
| `openpyxl` | Reading `.xlsx` design sheets |
| `jupyter` | Notebook experimentation |
| `rasterio` | Raster / DEM processing if added later |
| `scipy` | Numerical support used by WNTR workflows |

## Install

```powershell
pip install -r requirements.txt
```

## Legacy Dependency Note

For the archived Jorhat project, see:

- `legacy/jorhat_project/requirements_recreated.txt`
