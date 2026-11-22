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
| FR-DEB-01 | Bear-researcher progress judgement (`agents/debate_progress.py`), research-debate state, bull/bear router (`graph/conditional_logic.py`) and Research Manager handoff | DEB-T1 through DEB-T5; semantic fixture set (SEM-01, SEM-02, SEM-03, SEM-04, SEM-05a, SEM-05b, SEM-06) | `progress_outcome`, `progress_round` and `progress_reason` in the debate state and saved run log; ordered speaker history |

### FEAT-02 verification evidence (2026-11-22)

Implementation on branch `CS5351`. The end-to-end behaviour was verified offline; the semantic accuracy of the live judge is **not yet evaluated** (see the gap note below).

| Case | Implemented evidence | Result |
| --- | --- | --- |
| DEB-T1 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t1_opening_round_gives_bear_then_begins_round_two`, `::test_after_bull_speaks_in_round_two_the_bear_still_gets_a_turn` | Passed |
| DEB-T2 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t2_second_round_repetition_stops_after_the_bear_speaks`, `::test_cap_stop_is_not_labelled_no_progress` | Passed |
| DEB-T3 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t3_new_report_fact_continues_to_round_three` | Passed |
| DEB-T4 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t4_first_reply_continues_to_round_three` | Passed |
| DEB-T5 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t5_cap_one_hands_off_after_one_round`, `::test_deb_t5_cap_two_hands_off_after_two_rounds`, `::test_different_caps_keep_independent_final_rounds` | Passed |
| Judgement scheduling / cap precedence | `::test_judgement_is_scheduled_only_for_complete_rounds_between_two_and_cap`, `::test_bear_node_judges_only_round_two_not_the_opening_round`, `::test_bear_node_does_not_judge_at_or_after_the_cap` | Passed |
| Reason before/after manager, persistence | `::test_bear_node_records_no_progress_reason_before_the_manager_runs`, `::test_manager_preserves_the_reason_it_was_given`, `::test_manager_preserves_full_history_on_early_stop`, `::test_saved_run_log_records_outcome_and_reason` | Passed |
| UNKNOWN / fail-open / stale / old-state | `::test_failed_judgement_becomes_unknown_without_a_freetext_retry`, `::test_unknown_outcome_continues_and_keeps_speaker_order`, `::test_stale_no_progress_does_not_stop_the_opening_round`, `::test_stale_no_progress_does_not_stop_a_later_round_without_a_current_judgement`, `::test_older_state_without_progress_fields_still_routes_and_logs` | Passed |
| Structured contract (`classify_judgement`) | `::test_contract_clean_progress_maps_to_progress`, `::test_contract_confirmed_repetition_maps_to_no_progress`, `::test_contract_malformed_inconsistent_or_uncertain_is_unknown` (8 payload variants), `::test_contract_explicit_unknown_passes_through`, `::test_contract_schema_file_matches_rules` | Passed |
| FEAT-01 regression (options→researchers) | `::test_options_report_still_reaches_the_bull_researcher`, `::test_options_report_still_reaches_the_bear_researcher`; `test_options_analyst.py` and `test_options_data.py` unchanged and green | Passed |
| Semantic fixture well-formedness | `test_debate_semantics_eval.py::test_fixture_is_well_formed` (7 cases, labels validated) | Passed |

Offline regression: `python -m pytest -q` reported `1483 passed, 6 skipped, 4 deselected, 100 subtests passed` (1443 prior + 40 FEAT-02). FEAT-02 file alone: `40 passed, 1 deselected`. Structural check: `ruff check` on the changed src files and the two new test files reported no findings.

**Test-fixture correction recorded.** Six bear-node judge-scheduling tests and their helper initially assumed judgement on the *input* count (pairs "complete at even input counts"), which conflicted with the authoritative rule that the bear node receives the count before its turn and increments it. The rule is: judgement happens only after the bear completes a pair, when the resulting (post-increment) count is even and `4 <= new_count < 2 * max_debate_rounds`. The tests were corrected with explicit `cap=3` for round-two judgement and pre-bear input counts 3 (round two) and 5 (round three); assertions were strengthened (e.g. asserting the resulting `count == 4`), not weakened. Production logic was not changed to satisfy the tests.

**Live semantic-evaluation gap (outstanding).** `test_debate_semantics_eval.py::test_live_judge_meets_labelled_cases` is gated behind `TRADINGAGENTS_DEBATE_EVAL_LIVE=1` and has **not** been executed against a real model; no real-model semantic accuracy result exists. The runner is now wired to the implemented judge through the additive `DebateJudge.evaluate()` accessor (offline-verified with an injected fake LLM, including mismatch detection and failure/uncertainty handling). A separate single-request guarded probe, `test/live/test_debate_judge_cityu_probe.py`, is prepared for the CityU DeepSeek endpoint (`deepseek` provider, base URL `https://llm.cs.cityu.edu.hk/v1`, model `CS5351/DeepSeek-V4-Flash`) and has **not** been run. Running either live path remains outstanding work.

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
