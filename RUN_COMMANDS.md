# Run Commands

## Create Environment

```powershell
cd C:\Automation\WNTR
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Validate a Scheme Config

```powershell
python main.py validate --config configs\schemes\sample_scheme.yaml
```

## Planned Workflow Commands

```powershell
python main.py build-model --config configs\schemes\sample_scheme.yaml
python main.py simulate --config configs\schemes\sample_scheme.yaml
python main.py analyze --config configs\schemes\sample_scheme.yaml
python main.py map --config configs\schemes\sample_scheme.yaml
python main.py report --config configs\schemes\sample_scheme.yaml
```

## Run Legacy Jorhat Workflow

All Jorhat-specific files are preserved under:

- `legacy/jorhat_project`

Legacy commands should be executed from that folder using its preserved scripts and environment snapshot.
# DharaNokxa quick start

```powershell
cd C:\Automation\WNTR
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py demo
```

Use field-official tentative road lines and approved crossings when available:

```powershell
.\.venv\Scripts\python.exe main.py demo `
  --road-corridors templates\road_corridors.template.csv `
  --road-crossings templates\road_crossings.template.csv
```

Start the HTTP interface:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

Start the web workspace in a second terminal:

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. The HTTP interface listens at `http://127.0.0.1:8000`.

Run verification:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd web
npm run lint
npm run build
```
