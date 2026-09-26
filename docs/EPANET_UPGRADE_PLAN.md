# DharaNokxa EPANET-based upgrade plan

Status: proposed implementation plan, 26 September 2026. This document supersedes the earlier plan where they conflict; application changes have not been implemented by writing this plan.

Basis: local `docs/EPANET Manuals/epanet2.chm` and `tutorial.chm`, summarized in `docs/EPANET_DESIGN_RULES.md`, plus inspection of the current UI, API, model builder, topology validator, and optimizer.

## 1. Product direction and current gaps

Make the product a persistent engineering workspace supporting three equally valid starting points: import an existing hydraulic model, build from field/GIS inputs, or enter a network manually. Keep synthetic demonstrations as an explicit separate example project.

Observed gaps:

- The UI offers scheme name and ESR coordinates but no real upload or asset editor; a saved demo automatically replaces the setup screen.
- The API accepts demo parameters; it has no project input import, mapping, revision, or editing workflow.
- The hydraulic builder creates one fixed-head reservoir named ESR, junctions, and pipes. Duration is zero and head-loss formula is fixed to H-W.
- The map discards intermediate pipe geometry and hardcodes the source coordinates.
- The topology validator requires exactly LEFT and RIGHT runs, uses a universal node-degree cap, and requires two links per crossing. These are overly specific demo assumptions.
- The optimizer selects a shortest graph path and accepts diameter changes using endpoint pressure. It must evaluate the full declared constraint set before claiming compliance, particularly in looped or multi-source networks.
- Downloads use local file URLs; run status is kept in memory despite writing job JSON files.

## 2. Modeling decisions

1. **Separate hydraulic topology from route geometry.** A pipe has endpoint node IDs and an ordered polyline. Road bends use vertices. Split only for a physical junction, modeled demand/elevation evaluation point, equipment boundary, or pipe-property change with an explicit reason.
2. **One node per physical connection.** Two pipes joining at the same elbow share a node; if they constitute one uniform hydraulic link with no modeling reason to split, represent the elbow as a vertex. Never merge separate roadside lines just because they are nearby.
3. **At most two longitudinal runs per road.** Allow one or two according to the selected scheme layout; paired sides remain the default. Count distinct physical runs along each corridor interval, not pipe segments or the number of distinct LEFT/RIGHT labels.
4. **Preserve physical-side continuity.** LEFT/RIGHT is relative to a stored road direction. At a corner, connect external to external and internal to internal using geometry and explicit connection decisions. Reversing digitization direction must not change the physical design.
5. **Crossings do not imply connections.** An X-shaped map intersection can be unconnected. Same-side junction approval and permission to bore across a road are separate records. One physical bore is represented once; one or more hydraulic segments may describe it when an actual intermediate asset requires splitting.
6. **Validate real junction arrangements.** Two roadside runs do not imply at most two or three incident links at every node. A legitimate tee or four-way connection is checked against the approved layout, without a universal degree cap.
7. **Model sources explicitly.** Offer Reservoir / fixed-head boundary and Tank / ESR. Tanks require bottom elevation, operating levels, and storage geometry. A fixed-head approximation is allowed for a declared snapshot; it must not claim to evaluate storage depletion.
8. **Preserve imported networks.** Analyze imported topology before proposing redesign. Parallel hydraulic links can be legitimate; flag accidental duplicates and construction conflicts without banning all parallel pipes.
9. **No hidden synthetic completion.** Missing survey elevations, roads, demands, or source levels remain visible missing inputs. Only an explicit demo uses synthetic values.
10. **Keep private reference models isolated.** Private training data, identifiers, coordinates, and names never seed a public/example design. Use only reviewed general rules and anonymized evaluation metrics in the application.

The previous rule sheet's blanket same-label continuity and duplicate-connection wording must be refined against these decisions during implementation. It is a summary of help topics, not the executable specification.

## 3. UI workflow

Persistent navigation: **Project · Inputs · Network · Operations · Checks · Results · Exports**.

New project presents three cards:

- **Import EPANET model** — upload INP, inspect assets and settings, resolve issues, analyze.
- **Design from field data** — upload roads, households, elevations, sources, and tentative pipe alignments; edit missing fields and generate a candidate.
- **Enter or draw network** — add typed assets on the map or in tables; paste spreadsheet rows or use forms.

Inputs and editing remain accessible after a run. The header shows project, revision, saved state, selected scenario, and whether results match the current revision. Changes mark previous results as out of date.

Desktop layout: layer/object list on the left, map in the center, selected object's form on the right, expandable data table and issue list below. On narrow screens use full-width Map / Data / Details views. Selection stays synchronized between the map, table, and issue list. Show labels and symbols in addition to color; all forms and tables must be keyboard accessible.

Primary actions follow the state: **Review inputs → Validate network → Run analysis → Compare designs → Export**. Saving a partial draft is always allowed. An imported model can be analyzed without requesting automatic redesign.

## 4. Upload options and import review

| Input | Planned formats | Import behavior |
| --- | --- | --- |
| Existing hydraulic network | EPANET `.inp` | Preserve object IDs, geometry, demands, patterns, curves, controls, settings and supported quality data; report unsupported features before editing/export |
| Roads, tentative pipes, nodes, crossings, boundaries | GeoJSON, GeoPackage, zipped Shapefile | Select layer and role; map attributes; inspect geometry, CRS and units |
| Households, node/link registers, source levels | CSV, XLSX | Download templates, map columns, select units, preview rows, edit errors |
| Pump/volume/efficiency curves and patterns | CSV, XLSX, INP | Validate type, axes, units, IDs and references; display chart preview |
| Survey elevations | CSV/XLSX with coordinates or node IDs | Match explicitly; record elevation datum and matching distance |
| Terrain raster | GeoTIFF, later milestone | Confirm CRS, vertical units/datum, coverage and sampling method; label derived elevations |
| Field sketches and supporting documents | PDF/PNG/JPEG, later milestone | Reference attachments; manual tracing/georeferencing requires review, never silently creates hydraulic links |

Initial release priority: INP, CSV, GeoJSON and zipped Shapefile; XLSX and GeoPackage follow within the input milestone. Proprietary WaterGEMS files and EPANET binary NET are not promised as direct imports: offer an INP/GIS export route and a clear unsupported-format message.

Import sequence:

1. Upload to a project-specific staging area; retain the original and its checksum.
2. Inspect contents, supported sections/layers, feature counts, units and CRS. Shapefiles require SHP/SHX/DBF together; request CRS if PRJ is absent.
3. Let the user select field mappings and missing-data treatment. Never silently exchange latitude/longitude, deduplicate rows or discard features.
4. Preview map and editable table with exact row/feature issues. Show any proposed coordinate conversion or node snapping.
5. Commit accepted data as a new revision with an import report. Existing-data merges require an explicit add/update/replace choice and a change preview.

INP coordinates may be a schematic with no CRS. Such models must still analyze successfully in a schematic view; require georeferencing before overlaying roads or deriving geographic lengths.

File handling must cap size and decompressed archive size, reject archive path traversal, verify content, and prevent spreadsheet formulas/macros from executing. Parsing failure leaves the current revision intact.

## 5. Manual data-entry forms

Every value displays its unit, source and confidence; distinguish missing values from zero. Provide Add row, paste rows, duplicate asset with a new ID, bulk edit, undo, autosave, and downloadable templates. Defaults are visible and editable.

| Editor | Essential fields |
| --- | --- |
| Junction | ID, location, elevation/datum, demand categories, base demands, pattern IDs; optional emitter and initial quality |
| Reservoir | ID, location, total head/datum, optional head pattern and quality |
| Tank/ESR | ID, location, bottom elevation, initial/min/max levels, diameter or volume curve, minimum volume, overflow, mixing |
| Pipe | ID, start/end node selectors, route, hydraulic length and source, internal diameter, material/catalog, roughness/formula, minor loss, open/closed/check-valve status |
| Pump | ID, suction/discharge nodes, head curve or power, speed, status, schedule; optional efficiency/energy inputs |
| Valve | ID, endpoints, type, diameter, correctly labeled setting, status and minor loss |
| Road corridor | ID, oriented alignment, width/offset information, one/two-side layout, physical run IDs |
| Connection/crossing | ID, location, connected assets/sides, connection type, construction method, approval and reference |
| Household | ID, coordinates, population or demand, source/confidence, assigned service node |
| Design basis | Demand method, demand factors, applicable pressure/velocity/head-loss constraints, criteria source, catalog, scenarios |

Do not apply household-derived demand on top of imported nodal demand without an explicit allocation decision. Show allocated/unallocated demand totals and prevent double counting. Critical elevation points can require modeled junctions even without branches; record why they exist.

## 6. GIS and network editor

- Render complete pipe polylines in the browser, GIS exports and INP vertices; use actual source coordinates.
- Store native/source CRS and transformations; use a suitable metric coordinate system for routing, offsets and distance checks. Hydraulic length may be surveyed and differ from displayed length; preserve both with provenance.
- Provide separate tools: Move vertex, Add junction, Connect pipes, Split pipe, Merge compatible segments, Approve crossing. Preview consequences for length, demand, controls and IDs.
- Offset road geometry to create candidate roadside runs; handle corners, short segments and self-intersections before generation. A bend never generates a chain of artificial demand nodes.
- Optional open GIS layers provide context and candidate road alignments. Track provider, date, attribution, coverage and confidence. Surveyed alignments and approved field sketches take priority. Basemaps do not establish elevations, buried-pipe positions or crossing approval.
- Lock surveyed/existing assets and approved connections against automatic movement. Review suggested routing changes before applying them.

## 7. Validation and analysis

Use three independent result groups: **Model validity**, **Hydraulic criteria**, **Construction/review status**. Each issue has a stable rule ID, severity, affected asset/row, explanation, source topic or project criterion, and a jump-to-location action.

Model checks include node/link ID namespaces, references, numeric domains, self-links, disconnected assets, source boundaries, tank bounds, pump curves, valve restrictions, patterns, controls and pressure-demand limits. Reconcile conflicting manual wording with the installed EPANET version and executable regression fixtures rather than guessing version limits.

Construction checks include maximum roadside runs, physical-side continuity, duplicate joints, unintended crossings, approved bores, corridor containment and locked assets. A valid imported model can run hydraulically while construction metadata remains incomplete; it cannot be marked construction-approved.

Analysis modes:

- Snapshot DDA and PDA, with explicit minimum/required pressure and exponent.
- Extended-period simulation with duration, pattern/hydraulic/report/quality/rule steps and source/tank operation.
- Scenarios for peak demand, low tank level, average/low demand and relevant outages; fire-flow scenarios only if part of the selected design basis.
- Water age, source tracing and chemical quality after hydraulic and operations support is complete.

Aggregate constraints across all applicable nodes and times, not just the last output row. Preserve signed flow and distinguish head from pressure. Record solver errors, warnings, non-finite results, demand shortfall and tank limit events. Demand delivery under PDA does not alone establish all hydraulic criteria.

Report the evaluated time resolution; test time-step sensitivity where control events could hide short-duration violations. A result must identify the scenario/time of each governing extreme.

Optimization runs after validation and baseline analysis. Respect locked assets, hydraulic diameters and approved geometry; evaluate each candidate against all configured constraints and scenarios, including PDA delivery. Support loops and multiple sources without assuming a shortest graph path represents actual flow. Keep accepted/rejected changes and stop with an explicit infeasibility explanation when the allowed decisions cannot satisfy constraints.

## 8. Outputs and reproducibility

- Map modes: pressure, signed flow/direction, velocity, diameter, head loss, demand shortfall, tank level, construction approval; scenario and time selector.
- Asset tables and time-series charts tied to selected nodes/links; show requested and delivered demand separately.
- Before/after comparison of topology, diameters, criteria, cost where supported, and affected households.
- Export INP, GIS layers, CSV/XLSX asset/results tables, PDF report, design basis, issue report and revision history through HTTP downloads.
- Freeze each run to an immutable input revision, engine version, catalog/criteria versions, settings and input hashes. Export artifacts from that same revision.
- Test INP round trips for semantics and hydraulic outputs within declared tolerances. Preserve supported controls and geometry; keep original uploads and explicitly report lossy/unsupported conversion.

## 9. Implementation structure

Evolve the existing Python/WNTR, FastAPI and Next.js application incrementally:

- Typed canonical records for junction/reservoir/tank and pipe/pump/valve, separate geometry, road runs, crossings, demands, operations, criteria and provenance.
- Separate import adapters, normalized unit conversion, geometry operations, validators, EPANET adapter, simulation evaluation, optimization and export modules.
- Consistent SI values internally with explicit conversion at file/UI boundaries; round-trip original unit preferences where practical.
- Persist projects, revisions, import reports and jobs in a local database with project-scoped artifact storage. Reload saved projects after server restart and recover interrupted jobs predictably.
- API operations for project CRUD, staged uploads, import preview/commit, asset edits, validation, scenario runs, run status and artifact downloads. UI and import share the same validation rules.
- Break the current single UI file into project setup, input library, map editor, asset forms, tables, issues, operations and result components. Display actionable API errors and clean up polling on navigation.

## 10. Delivery sequence and acceptance gates

| Phase | Deliverables | Acceptance gate |
| --- | --- | --- |
| 1 — Correct model foundation | Typed records, geometry/node separation, tank versus reservoir, rule corrections, immutable revisions | Elbow uses no duplicate joint; a vertex-only edit adds no node; reversed road direction preserves physical continuity; a valid tee is allowed; a third roadside run is rejected |
| 2 — Inputs and editable drafts | Persistent projects, INP/CSV/GIS imports, mapping preview, templates, manual forms | User imports or manually creates a real network, corrects row errors, saves/reloads it, and receives no hidden synthetic replacements |
| 3 — GIS and construction | Road offsets, complete polylines, snapping review, connection tools, approved crossings and optional reference layers | One/two-side routes follow roads; an unconnected crossing stays unconnected; same-side elbow and approved bore have correct connectivity |
| 4 — Operations and simulation | Pumps/valves, curves/patterns/controls editors, DDA/PDA and EPS, tank operation, warning capture | Official tutorial fixtures and purpose-built cases reproduce expected behavior; tank depletion and pressure-driven demand reduction appear at the correct times |
| 5 — Constraints and optimization | Full scenario evaluation, locked assets, loop-aware candidate evaluation, comparison | No accepted change violates a mandatory criterion; infeasible cases remain failures; parallel links and flow reversal are handled correctly |
| 6 — Evidence and quality | Versioned downloads, reports, round-trip validation, age/quality scenarios | Reimported INP retains supported semantics/results; exports match selected revision; outdated results are clearly marked |

First usable milestone: phases 1–2 plus baseline DDA/PDA import-and-analyze support and a working INP download. EPS optimization and quality simulation follow; they must not block basic real-data entry.

Regression fixtures should cover elbows, reversed geometry, duplicate endpoints, close but separate roadside lines, tees, four-way junctions, grade-separated crossings, a single approved bore, one-side roads, three-run overlaps, loops, parallel links, multiple sources, tanks, invalid valves, missing CRS and invalid units. Browser checks cover every start mode, table/map synchronization, draft recovery, upload errors, stale results and downloads. Use private reference models only in a separately configured local evaluation process.

## 11. Definition of completion

The upgraded project lets a field official upload or enter actual inputs, lets an engineer inspect and correct topology, analyzes the declared operating cases through EPANET, and exports a reproducible design with explicit evidence. It preserves road alignment and physical connections, represents storage honestly, and keeps model validity, engineering criteria and approval as separate decisions.
