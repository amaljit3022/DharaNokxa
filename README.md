# DharaNokxa

DharaNokxa turns household locations and an ESR location into a documented candidate water distribution network. It estimates synthetic demo demand and terrain, builds a road-like topology, selects HDPE pipe sizes, runs EPANET 2.2 through WNTR, corrects low pressure through targeted pipe changes, attempts safe downsizing, and exports the model, GIS, tables, maps, design basis, optimization history, and PDF report.

> Current scope: working offline synthetic vertical slice. The included Assam/JJM profile and HDPE catalog are demonstration assumptions pending verification against authoritative departmental standards. Generated output is a preliminary candidate awaiting engineer review.

## Verified demo

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py demo
```

The deterministic fixture creates 100 households, starts with deliberately undersized pipes, records every optimization attempt, verifies DDA endpoint pressure and PDD demand delivery, and writes `results/demo_jjm_scheme.zip`.

## Web application

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

In a second terminal:

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. See [RUN_COMMANDS.md](RUN_COMMANDS.md) for build and test commands.

## Engineering rules in the demo

- Domestic demand: 55 LPCD with a 15% uplift, giving 63.25 LPCD/person.
- Hard endpoint requirement: pressure strictly greater than 7 m.
- Optimization target: pressure at least 8 m.
- Hydraulic diameters use HDPE internal diameter.
- Hydraulic compliance and engineer approval are separate states.
- Synthetic and assumed data remain visibly labeled in the interface and exports.
- The demo network shape is calibrated from the preserved Jorhat aggregate reference profile; source coordinates and raw project files are not copied.

## Project layout

```text
src/dharanokxa/    engineering core and exports
api/               FastAPI job interface
web/               Next.js and MapLibre engineering workspace
standards/         labeled demonstration profiles/catalog and Jorhat-derived aggregate profile
tests/             threshold, catalog, topology, hydraulic, export and HTTP tests
docs/              product and implementation design
legacy/             preserved Jorhat reference scripts and local archive
```

The real Jorhat WaterGEMS/GIS files and its historical virtual environment remain preserved locally but are intentionally excluded from the public repository because they are large and have not been cleared for public distribution.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd web
npm audit
npm run lint
npm run build
```

## License

MIT. EPANET, WNTR, MapLibre, Next.js and other dependencies retain their respective licenses.
