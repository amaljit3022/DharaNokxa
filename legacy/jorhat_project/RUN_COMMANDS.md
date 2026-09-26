# Run Commands

## Purpose

This document lists the commands needed to recreate the environment and execute the project at `C:\Automation\WNTR`.

## 1. Open the Project

```powershell
cd C:\Automation\WNTR
```

## 2. Create a Virtual Environment

```powershell
python -m venv venv
```

## 3. Activate the Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

## 4. Upgrade Pip

```powershell
python -m pip install --upgrade pip
```

## 5. Install Required Packages

### Minimal runtime set

```powershell
pip install wntr geopandas pandas shapely fiona pyproj networkx matplotlib pyogrio numpy scipy rasterio
```

### Optional extras

```powershell
pip install jupyter openpyxl
```

## 6. Configure Local Matplotlib Cache

This avoids cache write issues outside the repository.

```powershell
$env:MPLCONFIGDIR='C:\Automation\WNTR\results\mplcache'
```

## 7. Run the Main Hydraulic Analysis

This script scans the repository, builds the EPANET/WNTR model, runs hydraulics, calculates metrics, and exports results.

```powershell
python analyze_project.py
```

## 8. Run the Comprehensive GIS Map Generation

This script uses the outputs from `analyze_project.py` and creates the final critical pipe / ESR / transmitter map.

```powershell
python create_comprehensive_map.py
```

## 9. Recommended Full Execution Sequence

Run the project in this exact order:

```powershell
cd C:\Automation\WNTR
.\venv\Scripts\Activate.ps1
$env:MPLCONFIGDIR='C:\Automation\WNTR\results\mplcache'
python analyze_project.py
python create_comprehensive_map.py
```

## 10. Verify Key Outputs

### EPANET model

```powershell
Get-ChildItem .\models\inp_files\
```

### Main results

```powershell
Get-ChildItem .\results\
```

### Confirm main deliverables

```powershell
Get-ChildItem `
  .\models\inp_files\jorhat_combined_distribution.inp, `
  .\results\hydraulic_results.csv, `
  .\results\node_pressure.csv, `
  .\results\pipe_flow.csv, `
  .\results\network_metrics.csv, `
  .\results\critical_pipe_comprehensive_map.png, `
  .\results\critical_pipe_comprehensive_map.pdf
```

## 11. Optional: Export Current Environment

```powershell
pip freeze > requirements_recreated.txt
```

## 12. Optional: Inspect Installed Versions

```powershell
python -c "import sys; print(sys.version)"
python -c "import wntr, geopandas, pandas, shapely, fiona, pyproj, networkx, matplotlib; print('wntr', wntr.__version__); print('geopandas', geopandas.__version__); print('pandas', pandas.__version__); print('shapely', shapely.__version__); print('fiona', fiona.__version__); print('pyproj', pyproj.__version__); print('networkx', networkx.__version__); print('matplotlib', matplotlib.__version__)"
```

## 13. Optional: Re-run Only Map Production

If results already exist and only the detailed map must be recreated:

```powershell
python create_comprehensive_map.py
```

## 14. Optional: Re-run Only Hydraulic Processing

If the GIS or source model changes and outputs need to be regenerated:

```powershell
python analyze_project.py
```

## 15. Notes

- Run `analyze_project.py` before `create_comprehensive_map.py`.
- The map script depends on:
  - `results\node_pressure.csv`
  - `results\pipe_flow.csv`
  - `results\data_inventory.json`
- The repository currently has no built-in `requirements.txt`.
- `temp.bin` and `temp.rpt` may appear after simulation runs.
