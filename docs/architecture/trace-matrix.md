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

### FEAT-01 verification evidence (2026-11-22)

| Case | Implemented evidence | Result |
| --- | --- | --- |
| OPT-T1 · FR-OPT-01 | `test_options_analyst.py::test_stock_defaults_include_the_original_four_plus_options`, `::test_fresh_stock_cli_preselects_five_and_saved_four_stays_four`, `::test_crypto_defaults_exclude_options`, `::test_saved_preferences_keep_the_original_four_and_drop_options_for_crypto`, `::test_explicit_options_only_and_original_four_selections`, `::test_deselected_options_makes_no_lookup_or_report` | Passed |
| OPT-T2 · FR-OPT-02 | `test_options_analyst.py::test_rendered_chain_reaches_the_options_model_input`, `::test_options_only_run_still_reaches_a_decision`; `test_options_data.py::test_rendered_evidence_contains_the_approved_indicator_set` | Passed |
| OPT-T3 · FR-OPT-03 | `test_options_analyst.py::test_options_report_reaches_bull_bear_and_three_risk_debaters`, `::test_deselected_options_report_is_absent_not_invented`, `::test_options_only_run_still_reaches_a_decision` | Passed |
| OPT-T4 · FR-OPT-04 | `test_options_analyst.py::test_options_report_reaches_cli_state_log_and_report_tree`, `::test_baseline_state_without_options_field_still_exports`, `::test_blank_options_report_writes_no_section`, `::test_cli_complete_report_shows_options` | Passed |
| OPT-T5 · FR-OPT-05 | `test_options_analyst.py::test_unavailable_notice_reaches_outputs_without_a_model_call`, `::test_unavailable_notice_carries_no_inferred_signal`; `test_options_data.py::test_historical_run_falls_back_to_unavailable_through_the_router` | Passed |
| OPT-T6 · INV-OPT-01 | `test_options_data.py::test_adapter_keeps_only_matching_and_cutoff_eligible_records`, `::test_date_only_snapshot_is_eligible`, `::test_record_at_cutoff_is_eligible`, `::test_duplicate_contract_keeps_latest_eligible_observation`, `::test_naive_timestamp_is_unverifiable`, `::test_only_rejected_records_trigger_unavailable`; `test_options_analyst.py::test_future_snapshot_never_reaches_the_options_model` | Passed |
| Live provider check | `test/live/test_options_yfinance_live.py` against the current yfinance option chain and a historical request | 2 passed |

Offline regression: `python -m pytest -q` reported `1443 passed, 6 skipped, 3 deselected, 100 subtests passed`. Structural check: `ruff check src test` reported no findings. The live file was run separately with `-m integration`.

## FEAT-02 — Research debate early stop

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-DEB-01 | Research debate state, bull/bear router and Research Manager handoff | DEB-T1 through DEB-T5 | Ordered speaker history, completed round count and recorded reason on early stop |

## FEAT-03 — Company background in the consolidated report

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-RPT-01 | Profile/date handling and shared report export (reporting.py, report_html.py) | RPT-T1 through RPT-T4 | Company Background section in exported Markdown and HTML |

## FEAT-04 — Per-run token usage warning

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-TOK-01 | Run configuration, shared statistics handler and active terminal or web display | TOK-T1 and TOK-T2 | First crossing total and threshold displayed during the run |

## FEAT-05 — Paragraph citations in the research debate

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-CIT-01 | Analyst-to-research handoff, bull/bear histories, consolidated report renderers | CIT-T1 through CIT-T3 | Source labels, argument citations and missing or invalid citation notices in the run report |

## FEAT-06 — Local web interface

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-WEB-01 | Local launcher, configuration form and analysis runner | WEB-T1 | Ready URL, resolved selections and active run |
| FR-WEB-02 | Graph event stream, usage handler and browser activity/content views | WEB-T2 and WEB-T3 | Ordered role-labelled output, warning and failure state |
| FR-WEB-03 | Report writer and run-specific results view | WEB-T4 | Displayed run metadata, HTML preview and Markdown download |
