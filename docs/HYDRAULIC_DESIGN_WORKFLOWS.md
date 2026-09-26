# Hydraulic design research workflows

DharaNokxa now has two user-level Codex skills installed from public GitHub
repositories:

- [Librarian](https://github.com/jivebreaddev/skills-claude-agent/tree/main/.claude/skills/librarian)
  handles external documentation and implementation research. For this project,
  it is used for official EPANET, WNTR, Open Water Analytics, and WaterGEMS
  references. Load-bearing engineering claims must retain the source URL and
  version or access date.
- [Historian](https://github.com/wonsukchoi/domain-experts/tree/main/roles/historian)
  handles provenance and evidence criticism. For this project, it records the
  origin of Jorhat shapefiles, EPANET inputs, field CSVs, and derived aggregate
  profiles, distinguishing observed design facts from assumptions and synthetic
  values.

## Project application

The Librarian workflow should answer external questions from primary sources
before a hydraulic rule is added. Preferred references are:

- [USEPA EPANET](https://github.com/USEPA/EPANET) for solver concepts and
  pressure-driven or extended-period behavior.
- [Open Water Analytics EPANET](https://github.com/OpenWaterAnalytics/EPANET)
  for the maintained toolkit implementation.
- [WNTR documentation](https://usepa.github.io/WNTR/) for the Python modeling
  interface used by DharaNokxa.
- [Bentley OpenFlows WaterGEMS](https://www.bentley.com/software/openflows-watergems/)
  for vendor-specific workflows that must remain clearly labeled as such.

The Historian workflow maintains an evidence ledger for every design basis
change:

| Evidence class | Examples | Allowed use |
|---|---|---|
| Primary project artifact | Jorhat `.shp`, `.inp`, survey or approved crossing sheet | Calibrate or reproduce a measured design fact |
| Derived reference | Jorhat length, diameter, node-degree aggregates | Inform a synthetic candidate; never silently replace field approval |
| Field-confirmed input | Approved road corridor and crossing CSV/GeoJSON | Permit constructible alignment and boring links |
| Assumption | Synthetic coordinates, demand, elevation, catalog entry | Run a labeled candidate only; requires engineer review |

The implementation records this distinction in the design basis, exports, node
metadata, and `road_topology_status`. Raw Jorhat project files remain local;
public outputs contain only derived engineering aggregates.
