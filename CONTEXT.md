# DharaNokxa domain language

DharaNokxa creates and documents candidate water distribution designs from household and source locations.

## Language

**Household**: A consumer location with measured or estimated population. It is distinct from a hydraulic demand node.

**Service connection**: The association and, when modeled, physical connection between a household and its demand node.

**Demand node**: A hydraulic junction to which consumer demands are assigned.

**Required endpoint**: A consumer-serving location at which the design must verify the applicable pressure requirement. It is not restricted to graph nodes with degree one.

**Critical endpoint**: The required endpoint with the lowest pressure across the specified evaluation scenarios and times.

**Hard minimum pressure**: The exclusive lower pressure limit; this brief requires pressure strictly greater than 7 m.

**Target pressure**: The pressure sought by optimization; the default is 8 m, comprising the hard minimum and a configured 1 m margin.

**Achieved pressure margin**: The minimum endpoint pressure minus the hard minimum. It is distinct from the configured margin.

**Source hydraulic level**: The water head supplied to the network relative to a stated elevation datum. It is distinct from ESR ground elevation, staging, and full supply level.

**Candidate design**: A generated network and its evaluated engineering evidence, awaiting the applicable engineering review.

**Hydraulic compliance**: Satisfaction of all mandatory hydraulic constraints for the declared scenarios and evaluation times. It does not constitute engineer approval.

**Engineer approval**: An accountable review decision for a specific design revision and its supporting evidence.

**Design basis**: The collection of criteria, assumptions, references, and overrides used to generate and evaluate a design.

**Design run**: One reproducible attempt to generate and evaluate a candidate from a fixed set of inputs and assumptions.
