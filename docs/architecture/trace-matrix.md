# Trace matrix

## FEAT-01 — Options Analyst

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-OPT-01 | CLI selection and graph defaults | OPT-T1 | Run settings and invoked analysts |
| FR-OPT-02 | Options analyst and report state | OPT-T2 | Options section and source observations |
| FR-OPT-03 | Researchers, risk debaters and graph | OPT-T3 | Agent input capture in supervised replay and completed decision |
| FR-OPT-04 | CLI display, graph log and shared report writer | OPT-T4 | Report panels and generated files |
| FR-OPT-05 | Options data boundary and graph | OPT-T5 | Unavailable notice and final run status |
| INV-OPT-01 | Options data adapter | OPT-T6 | Rejected or accepted observation identity and time in supervised replay |

## FEAT-02 — Research debate early stop

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-DEB-01 | Research debate state, bull/bear router and Research Manager handoff | DEB-T1 through DEB-T5 | Ordered speaker history, completed round count and recorded reason on early stop |

## FEAT-03 — Company background in the consolidated report

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-RPT-01 | Profile/date handling and shared report export (reporting.py, report_html.py) | RPT-T1 through RPT-T4 | Company Background section in exported Markdown and HTML |
