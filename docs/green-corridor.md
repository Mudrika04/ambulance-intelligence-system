# Green corridor (prototype simulation)

Three simulated intersections, configured in `configs/config.yaml`:

| ID | Name | Role |
| --- | --- | --- |
| INT-01 | Kalyanpur Crossing | primary |
| INT-02 | Vikas Nagar Junction | downstream |
| INT-03 | Rawatpur Gate | downstream |

While the primary intersection is in `PREPARE`, `ALL_RED` or `EMERGENCY_GREEN`: INT-01 is `ACTIVE_PRIORITY`, INT-02 is `PREPARE`, INT-03 is `MONITOR`. On `CLEARANCE` the active intersection becomes `CLEARED` and priority hands over downstream after a simulated travel time. Returning to `NORMAL` resets every node to `MONITOR`.

**This is a prototype simulation.** There is no connection to real traffic infrastructure, no inter-controller protocol and no measured travel time between real junctions. The API marks it `simulated: true` and the UI labels it PROTOTYPE SIMULATION.
