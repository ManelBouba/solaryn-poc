# Client delivery

Solaryn is delivered as a generic application package named `Solaryn.zip`.

For every analysis, the client chooses the project location. Solaryn then exports a project-specific ZIP named from the resolved city/project and technical-leading technology.

## Runtime package contents

- `Solaryn_<Project>_<Technology>_Executive_Report.html` — high-level recommendation report with embedded graphs.
- `Solaryn_<Project>_<Technology>_Comparison.csv` — candidate metrics and evidence fields.
- `Solaryn_<Project>_<Technology>_Hourly_Physics.csv` — timestamped hourly physics outputs.
- `Solaryn_Real_World_Validation_Report.html` — measured validation evidence and limits.
- `README.txt` — location, project size, technical leader and decision status.

The filename identifies the **technical-leading technology**, not a guaranteed commercial winner. The report must be read together with the decision status and evidence boundary.
