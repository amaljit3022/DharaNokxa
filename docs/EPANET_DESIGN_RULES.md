# EPANET object semantics and design rules

This document records the rules extracted from the local EPANET 2.2 help files and tutorial:

- `C:\Automation\WNTR\docs\EPANET Manuals\epanet2.chm`
- `C:\Automation\WNTR\docs\EPANET Manuals\tutorial.chm`

The source topics were reviewed from the decompressed CHM content, including `network_components`, `types_of_objects`, `junctions`, `reservoirs`, `tanks`, `pipes`, `pumps`, `valves`, their property pages, hydraulic analysis, demand models, controls, error messages, geometry import, and the tutorial pages for constructing and analyzing a network.

EPANET rules below describe what the hydraulic engine means by an object and what it requires for a solvable model. They do not replace the authority's design standards for demand, fire flow, minimum pressure, velocity, pipe material, cover, road work, or construction.

## 1. The EPANET model

EPANET represents a water distribution system as a graph:

| Category | EPANET objects | Hydraulic meaning |
| --- | --- | --- |
| Nodes | Junctions, reservoirs, tanks | Locations at which hydraulic head is solved or prescribed |
| Links | Pipes, pumps, valves | Connections between two existing nodes |
| Operational data | Time patterns, curves, controls, analysis options | Rules that vary demands, levels, pump operation, valve settings, and solver behavior |
| Map data | Coordinates, vertices, labels, backdrop | Display and GIS geometry; not additional hydraulic objects |

The hydraulic solution applies conservation of flow at junctions and a head-loss or head-gain relationship across every link. Reservoir heads, tank levels, and junction demands are the boundary or operating values used at each simulation time.

### Node versus vertex

An EPANET **node** is a hydraulic object. It can have elevation, head, pressure, demand, storage, or source quality, and links can connect to it.

An EPANET **vertex** is an intermediate map point used to shape a link. The tutorial draws a curved pipe with vertices between the same start and end nodes. A vertex does not create a junction, does not split a pipe hydraulically, carries no demand, and is not a place where a new pipe may connect. Use vertices to follow a surveyed or GIS road alignment; create a node only for a real hydraulic connection, demand, control device, storage asset, source, or approved construction connection.

## 2. Node types

### Junction

A junction is a point where links join and where water enters or leaves the network. Required engineering inputs are:

- unique junction ID;
- elevation above a common datum;
- base demand (zero is valid for a transit or connection node);
- optional demand time pattern and additional demand categories;
- optional initial/source water quality;
- optional emitter coefficient.

EPANET computes hydraulic head, pressure, and water quality at a junction. A negative base demand represents external inflow into the junction. A normal demand is not automatically pressure limited under the default **demand-driven analysis (DDA)** model; DDA attempts to deliver the specified demand even if the resulting pressure is negative. **Pressure-driven analysis (PDA)** instead varies delivered demand from zero to the requested value between the configured minimum and required pressures.

Use a junction when a pipe ends, a demand is assigned, or a real branch/control connection exists. Do not add a junction only because a pipe changes direction on a map.

### Reservoir

A reservoir represents an infinite external source or sink: for example a lake, river, aquifer, treatment-plant clearwell, or tie-in to another system. Required inputs are:

- unique reservoir ID;
- total hydraulic head (elevation plus pressure head);
- optional head time pattern;
- optional initial/source water quality.

The reservoir head and source quality are boundary conditions and cannot be changed by network behavior. A reservoir has no computed demand or pressure output in the normal junction sense. It can be the hydraulic source or sink for a network and can have multiple links.

### Tank

A tank is a storage node whose volume and water-surface head vary during a simulation. Required inputs are:

- unique tank ID;
- bottom elevation;
- initial water level;
- minimum and maximum water levels;
- diameter, or a volume-versus-level curve for an irregular tank.

The initial level must be within the allowed operating range, and the lower level must not exceed the upper level. EPANET stops tank outflow at the minimum level. At the maximum level it stops inflow unless overflow is enabled, in which case excess inflow is spill. Tanks may also have initial/source quality and one of the supported mixing models (fully mixed, two-compartment, FIFO, or LIFO).

## 3. Link types

Every link has two existing, different node IDs. Start and end are the nominal orientation stored in the model; they are not a guarantee that a normal pipe will flow in that direction.

### Pipe

Pipes convey water between two nodes and are assumed to remain full. Required inputs are:

- unique pipe ID;
- start node and end node;
- positive length;
- positive diameter;
- roughness coefficient consistent with the selected head-loss formula;
- initial status: open, closed, or check valve.

The ordinary pipe flow direction is determined by the relative hydraulic heads and may reverse during a simulation. A check-valve pipe permits flow only from its start node to its end node. A check valve is a pipe property, not a separate link object, and its status cannot be changed by simple or rule-based controls.

EPANET can model wall/bulk reactions and a unitless minor-loss coefficient for fittings, bends, meters, and valves. The default minor-loss value is zero when omitted. The hydraulic outputs include flow, velocity, head loss, friction factor, and reaction results.

### Pump

A pump adds energy and raises hydraulic head. Its start node is the suction side and its end node is the discharge side. A pump must have either:

- a pump head-versus-flow curve; or
- a constant power rating.

If both are supplied, the pump curve is used. Pump flow is unidirectional. EPANET can shut a pump down when the required head is beyond the supplied curve and reports a warning; it can also extrapolate the curve when the required flow is beyond the supplied range. Speed, status, time patterns, controls, efficiency, energy price, and demand charge may be specified.

### Valve

EPANET valve links control pressure or flow. The supported types are:

- **PRV** — pressure reducing valve, maintains downstream pressure when active;
- **PSV** — pressure sustaining valve, maintains upstream pressure when active;
- **PBV** — pressure breaker valve, imposes a specified pressure loss;
- **FCV** — flow control valve, limits flow to a setting;
- **TCV** — throttle control valve, uses a loss coefficient;
- **GPV** — general-purpose valve, uses a user-supplied head-loss curve.

The setting must use the units and meaning required by the valve type. A fixed `OPEN` or `CLOSED` status overrides the active control setting until a control assigns a new numerical setting.

EPANET rejects these valve arrangements:

- a PRV, PSV, or FCV directly connected to a reservoir or tank; insert a pipe between the valve and the storage/boundary node;
- PRVs in series or sharing the same downstream node;
- PSVs in series or sharing the same upstream node;
- a PSV directly connected to the downstream node of a PRV.

## 4. Hydraulic rules

### Head loss and roughness

Select one pipe head-loss formula for the project:

- Hazen–Williams;
- Darcy–Weisbach;
- Chezy–Manning.

Roughness has a different meaning and unit convention for each formula. Do not switch formula without reviewing every pipe roughness value. Minor losses are proportional to velocity head and should be included only where the design basis provides a defensible fitting/valve loss coefficient.

### Demand model

- **DDA** is the classical EPANET default. Nodal demands are fixed and EPANET attempts to satisfy them regardless of pressure.
- **PDA** makes delivered demand a pressure-dependent function. Below the minimum pressure, delivered demand is zero; at or above required pressure, full demand is delivered; between them, demand follows the configured pressure exponent.
- Under PDA, required pressure must be at least 0.1 pressure units above minimum pressure. EPANET reports error 208 for invalid limits.

Use DDA to test the nominal design requirement and PDA to expose service shortfalls or demand reduction under inadequate pressure. A positive demand at negative pressure is a warning sign, not evidence of a physically acceptable supply.

### Network solvability and connectivity

A valid hydraulic network must include at least one source/storage node (reservoir or tank) and at least one junction. Every demand junction must have an open path to a reservoir, tank, or junction with negative demand. A node with no link is invalid. A link cannot connect a node to itself.

The most relevant EPANET checks are:

| Error | Rule |
| --- | --- |
| 203/204/205/206 | Every referenced node, link, pattern, and curve must exist. |
| 215 | IDs must be unique within the object type and node/link IDs cannot collide where prohibited. |
| 222 | A link's start and end nodes must be different. |
| 223/224 | The model must contain enough nodes and at least one reservoir or tank. |
| 233 | Every node must be connected to at least one link. |
| 110 | The hydraulic equations could not be solved; check disconnected portions and unreasonable data. |
| 219/220 | Valve-to-storage and valve-to-valve restrictions were violated. |
| 226/227 | A pump lacks a curve/power or has an invalid pump curve. |
| 230 | Curve X-values are not increasing. |

Closed links can disconnect a demand area during an extended simulation even when the initial topology is connected. Validate connectivity at every relevant operating state, not only at time zero.

### Pressure and negative-pressure rules

EPANET warns when a positive-demand junction has negative pressure. This commonly indicates a disconnected/closed path, insufficient source head, excessive loss, or an unrealistic demand. Project-specific minimum-pressure requirements must be checked separately from whether EPANET converged.

### Time and convergence

- Total duration `0` runs a single-period snapshot. Water-quality analysis requires a non-zero duration.
- The typical hydraulic time step is one hour; the typical quality step is five minutes; pattern and reporting steps are typically one hour. These are defaults, not universal design requirements.
- EPANET shortens a hydraulic step when a report time, pattern change, tank empty/full event, or control event occurs.
- The hydraulic solver uses iterative balancing. Maximum trials, convergence accuracy, unbalanced action, maximum head error, and maximum flow change are analysis options. The manual suggests at least 40 trials and an accuracy around 0.001 as starting values; confirm convergence for the actual network.
- A successful run is not the same as a compliant design: inspect warnings, pressure, demand delivery, tank levels, velocities, head loss, and status changes.

## 5. Operational and water-quality rules

### Patterns and curves

A time pattern is a sequence of multipliers applied to a nominal demand, reservoir head, pump schedule, or quality source. All patterns use the project's common pattern time step; a pattern wraps to its first multiplier after its last period.

Curves are pairs of X/Y values. EPANET uses pump, efficiency, volume, and general-purpose-valve head-loss curves. Curve X-values must increase, and a pump curve must have decreasing head as flow increases.

### Controls

Simple controls can change link status or settings based on tank level, junction pressure, elapsed time, or clock time. Rule-based controls combine conditions on nodes, links, tanks, or system values and then apply link actions. In a mixed `AND`/`OR` expression, `OR` has higher precedence than `AND`; use separate rules when parentheses would otherwise be ambiguous. A higher rule priority wins conflicting actions; equal priorities keep the earlier rule. Never attempt to control a check-valve pipe.

### Water quality

Water-quality inputs include initial quality at nodes, source quality, bulk and wall reaction coefficients in pipes, and tank mixing. Quality routing uses shorter time steps than hydraulics because travel times through pipes can be short. Quality, age, and source tracing are separate analyses from the hydraulic pressure check and must be enabled deliberately.

## 6. EPANET input and geometry rules

EPANET's text export uses labeled sections such as `[JUNCTIONS]`, `[RESERVOIRS]`, `[TANKS]`, `[PIPES]`, `[PUMPS]`, `[VALVES]`, `[PATTERNS]`, `[CURVES]`, `[CONTROLS]`, `[RULES]`, `[OPTIONS]`, `[TIMES]`, `[REPORT]`, `[COORDINATES]`, and `[VERTICES]`. The exact sections present depend on the model. IDs and references must be consistent across sections, numeric values must use one coherent unit system, and the exported `.INP` should be retained as a human-readable archive.

The partial-network import format confirms the critical geometry distinction:

- `[JUNCTIONS]` declares hydraulic junction IDs;
- `[PIPES]` declares each pipe ID and its two endpoint junction IDs;
- `[COORDINATES]` locates nodes on the map;
- `[VERTICES]` adds intermediate display points to a link.

GIS/CAD geometry can therefore provide road-aligned coordinates and vertices without inventing hydraulic joints. Snap the two pipe endpoints to the same node ID when they are one physical connection.

## 7. DharaNokxa rules derived from the EPANET model

The following are application and construction rules, not rules imposed by EPANET:

1. A road has at most two longitudinal distribution lines: `LEFT` and `RIGHT`.
2. A line is split only at a named connection point, approved intersection, source entry, or another real hydraulic asset.
3. A road bend is represented by link vertices or GIS geometry; it does not create an extra junction.
4. At an approved road intersection, use one shared hydraulic node per side for the continuous same-side line. Do not create two coincident endpoint nodes and a zero-purpose connector.
5. Keep the two sides distinct: left connects to left and right connects to right unless an approved crossing explicitly connects them.
6. A road crossing/boring is a deliberate link between the two sides. It must be represented once, at the approved crossing location, with its construction metadata.
7. The ESR/source entry remains an explicit source-to-network connection because it is a real hydraulic and construction transition.
8. No generated pipe may reference an unknown node, use the same node at both ends, or duplicate an existing connection.
9. Every generated design must pass both EPANET solvability checks and application topology checks. EPANET convergence alone does not approve a road layout.

In the current implementation these application checks are enforced by `src/dharanokxa/topology.py` and the generated hydraulic model in `src/dharanokxa/hydraulics.py`. The current hydraulic run uses EPANET 2.2 through WNTR, metric LPS input units, and Hazen–Williams; the pressure thresholds and road construction limits remain project-profile assumptions until an authority approves them.

## 8. Practical review checklist

Before an engineer accepts an exported model, verify:

- IDs are unique and every link endpoint/reference resolves.
- There is at least one source/storage node and at least one demand junction.
- Every demand junction has an open source path in each operating state.
- Junction elevations and demands are sourced, labeled, and assigned the intended pattern.
- Reservoir head and tank levels/geometry represent the actual boundary/storage condition.
- Every pipe has valid length, diameter, roughness, status, and (where justified) minor loss.
- Pump curves or power ratings are present and physically valid.
- Valve type, setting, orientation, and separation rules are valid.
- DDA and PDA results are interpreted separately; negative pressure and demand shortfall are reviewed.
- Snapshot and extended-period results are both run when operating changes matter.
- Pressure, velocity, head loss, tank bounds, pump/valve status, and warnings are reviewed at the critical time steps.
- Map bends are encoded as vertices or GIS geometry, while true hydraulic joints are encoded as nodes.
- DharaNokxa's two-line road rule, same-side continuity, approved crossing list, and source-entry boring are visible in the design review record.

## Source topic map

The most important local source topics are:

| Subject | EPANET CHM topic |
| --- | --- |
| Object taxonomy | `network_components.htm`, `types_of_objects.htm` |
| Junctions | `junctions.htm`, `junction_properties.htm`, `demand_models.htm`, `emitters.htm` |
| Reservoirs | `reservoirs.htm`, `reservoir_properties.htm` |
| Tanks | `tanks.htm`, `tank_properties.htm`, `tank_mixing_models.htm` |
| Pipes and losses | `pipes.htm`, `pipe_properties.htm`, `head_loss_formulas.htm`, `minor_losses.htm` |
| Pumps | `pumps.htm`, `pump_properties.htm`, `pump_curve.htm`, `pump_problems.htm` |
| Valves | `valves.htm`, `valve_types.htm`, `valve_properties.htm` |
| Hydraulics and time | `hydraulic_analysis.htm`, `analysis_options-hydraulics.htm`, `analysis_options-times.htm` |
| Controls | `controls.htm`, `simple_controls.htm`, `rule-based_controls.htm`, `rule_format.htm`, `rule_evaluation.htm` |
| Connectivity and errors | `disconnected_network.htm`, `negative_pressures.htm`, `unsolveable_equations.htm`, `error_messages.htm` |
| Input/GIS geometry | `exporting_to_text_file.htm`, `importing_a_partial_network.htm`, `importing_a_network_map.htm`, `exporting_the_network_map.htm` |
| Workflow | `steps_in_using_epanet.htm` and the pages in `tutorial.chm` |
