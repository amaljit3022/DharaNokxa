# Dependencies

## Purpose

This file describes the dependencies for the new generalized toolkit at the repository root.

Private training environments are kept outside the first-design dependency contract.

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

## Training Dependency Note

Training-only environments are not required to build or export the first design.
