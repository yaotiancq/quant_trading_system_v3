# CHANGELOG.md

# Changelog

This changelog tracks project changes by phase.

The format follows a simplified Keep a Changelog style.

---

## [Major Architecture Phase F2] - 2026-05-24

### Added

- Added ML model stage transition helpers for candidate, validated, approved,
  and archived manifests.
- Added manifest approval metadata fields and persisted stage transition
  history.
- Added runtime inference policy for `require_approved_model` and
  `allowed_model_stages`.
- Added ML strategy/config pass-through for model stage loading policy.
- Added tests for registry transitions, approved-only inference, archived
  rejection under approval policy, strategy enforcement, and config validation.

### Changed

- Approved manifests now require approver metadata and approval timestamp.
- The sample ML strategy config now blocks archived and legacy artifacts by
  default while still allowing development-stage models.

### Fixed

- ML strategy initialization now converts ML loading policy failures into
  strategy-layer errors.

### Removed

- None.

---

## [Major Architecture Phase F1] - 2026-05-24

### Added

- Added `MLModelManifest` and deterministic feature-schema hash generation for
  local ML model contracts.
- Added `manifest.json` output beside every newly saved registry `model.json`.
- Added registry manifest loading and model/manifest contract validation.
- Added runtime inference access to the loaded model manifest.
- Added manifest path output from the dependency-free directional training
  pipeline and training script.
- Added tests for manifest round trips, schema-hash exposure, corrupted model
  or manifest rejection, and training-pipeline manifest output.

### Changed

- Directional model artifacts and predictions now include the feature-schema
  hash in their metadata.
- The ML training config records the initial model governance stage as
  `candidate`.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase E] - 2026-05-24

### Added

- Added dependency-free SVG chart rendering for backtest equity curves and
  drawdowns.
- Added buy/sell fill markers to the equity-curve chart.
- Added optional chart artifact export behind `reporting.generate_plots=true`.
- Added chart artifact paths to `BacktestResult.artifacts` when plot generation
  succeeds.
- Added `scripts/generate_report.py --generate-plots` for one-off chart
  artifact generation.
- Added deterministic unit and integration tests for chart export.

### Changed

- Report summaries now mention generated SVG diagnostics when plotting is
  enabled.
- Backtest config templates now document `reporting.generate_plots`.

### Fixed

- Plot generation failures are captured as report warnings so metrics, ledgers,
  config, and summary artifacts remain usable.

### Removed

- None.

---

## [Major Architecture Phase D3] - 2026-05-24

### Added

- Added `broker.safety.enable_automated_submission` as a separate gate before
  safety-approved live decision previews can become submitted orders.
- Added `broker.safety.automated_submission_kill_switch` to block automated
  live submissions even when the automation gate is enabled.
- Added `validate_live_automated_submission_config()` for automated live
  submission safety validation.
- Added automated live submission handling in `LiveEngine.on_market_event()`
  that routes approved previews through `LiveEngine.submit_live_order(...)`,
  records submission status, and reconciles after submission.
- Added fail-stop behavior for automated submission failures and post-submit
  reconciliation mismatches.
- Added deterministic tests for automation-disabled previews, successful
  automated submission, kill-switch blocking, and failure-stop behavior.

### Changed

- Live health output now includes automated submission enablement, kill-switch,
  event count, latest event, stopped flag, and stop reason.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase D2] - 2026-05-24

### Added

- Enabled `LiveEngine` to construct the selected `AlpacaBrokerage` live
  adapter for non-dry-run live configs after the D1 order-submission gates
  pass.
- Added Alpaca live adapter safety checks for `alpaca_live`, `paper=false`,
  `live_enabled=true`, `confirm_live_trading=true`,
  `enable_order_submission=true`, and non-mock/non-dry-run mode.
- Added deterministic tests for gated Alpaca live adapter construction,
  rejected unsafe live configs, and missing live credentials.

### Changed

- `AlpacaBrokerage` now supports explicitly gated live mode in addition to
  paper mode while preserving the normalized `Brokerage` interface.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase D1] - 2026-05-24

### Added

- Added explicit `broker.safety.enable_order_submission` gating for production
  live order submission.
- Added `validate_live_order_submission_config()` to require non-dry-run live
  mode, live broker config, `confirm_live_trading=true`, and
  `enable_order_submission=true` before any live order can be submitted.
- Added `LiveEngine.submit_live_order(...)` for manually supplied normalized
  `OrderRequest` objects after account, session, symbol, size, fractional, and
  reconciliation checks pass.
- Added live health output for manual live submission count and latest
  submission payload.
- Added deterministic tests using an injected recording brokerage.

### Changed

- Split Major Architecture Phase D into D1, D2, and D3 so real broker adapter
  enablement and automated strategy-driven submission remain separate future
  phases.
- Documented the new submission gate in `configs/live_alpaca.yaml`.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase C3] - 2026-05-24

### Added

- Added `BrokerEventSyncPolicy`, `BrokerEventSyncCheckpoint`,
  `BrokerEventSyncResult`, and `BrokerEventSyncLoop` for deterministic
  broker-event synchronization with duplicate, out-of-order, and gap handling.
- Added `PaperTradingEngine.sync_broker_events()` and
  `LiveEngine.sync_broker_events()` to run broker-event sources through
  checkpointed synchronization with reconciliation before and after sync.
- Added live and paper health output for the latest broker-event sync result.
- Added tests for checkpoint resume behavior, gap fail-closed behavior,
  duplicate suppression, paper sync reconciliation, and live dry-run sync.

### Changed

- `LiveEngine.on_broker_event()` now normalizes direct `Order`, `Fill`,
  `Account`, and `Position` inputs into `BrokerEvent` before recording broker
  event metrics.
- Execution fill handling now avoids double-counting a fill when a cumulative
  broker order update already reflects that fill.
- Phase C planning now marks C3 complete and points to Phase D as the next
  planned major architecture phase.

### Fixed

- Prevented broker push-style order-update-first delivery from inflating
  execution filled quantity when the matching fill event arrives afterward.
- Prevented failed broker-event application from marking the event processed
  before recovery can retry it.

### Removed

- None.

---

## [Major Architecture Phase C2] - 2026-05-24

### Added

- Added a generic `BrokerEventSource` protocol and deterministic
  `InMemoryBrokerEventSource`.
- Added Alpaca broker trade-update event adapter boundary with
  `AlpacaBrokerEventClient`, `InMemoryAlpacaBrokerEventClient`, and
  `AlpacaBrokerEventSource`.
- Added IBKR broker order-update event adapter boundary with
  `IBKRBrokerEventClient`, `InMemoryIBKRBrokerEventClient`, and
  `IBKRBrokerEventSource`.
- Added tests for Alpaca/IBKR-shaped push-event payload normalization,
  incremental fill deltas, in-memory client subscription behavior, and
  fail-closed error payloads.

### Changed

- Alpaca and IBKR integration packages now export their broker-event adapter
  boundary types and normalization helpers.
- Phase C planning now marks C2 complete and points to C3 lifecycle
  synchronization hardening as the next task.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase C1] - 2026-05-24

### Added

- Added `BrokerEventType` and `BrokerEvent` as the normalized broker lifecycle
  event envelope.
- Added execution helpers for converting normalized `Order`, `Fill`, `Account`,
  and `Position` payloads into broker events.
- Added `OrderRouter.poll_events()` as a polling fallback over existing broker
  order and fill polling APIs.
- Added tests for broker-event validation, idempotent fill handling, stale
  order update rejection, and paper-engine polling synchronization.

### Changed

- `ExecutionEngine` now consumes normalized broker events idempotently and
  ignores duplicate fill events.
- `OrderManager` now skips stale or regressive lifecycle updates.
- `PaperTradingEngine.poll_broker_updates()` now routes polling updates through
  normalized broker events while retaining direct `Order`/`Fill` compatibility.
- `BacktestBrokerage.list_orders()` now accepts broad `all`, `open`, and
  `closed` status filters for polling parity with paper broker adapters.

### Fixed

- Prevented duplicate broker fill events from double-applying execution state or
  paper portfolio state.
- Prevented stale order updates from overwriting newer tracked order status.

### Removed

- None.

---

## [Major Architecture Phase B2b2] - 2026-05-24

### Added

- Added guarded live decision previews to `LiveEngine` for dry-run market events.
- Added live runtime data portal state, feature pipeline initialization, strategy
  initialization, and risk engine wiring.
- Added live preview tests for safety-approved previews, safety-rejected
  previews, quote-only events, and no broker submission.

### Changed

- `LiveEngine.on_market_event()` now advances live data state, marks the
  portfolio to market, runs bar-based strategy/risk evaluation, builds
  normalized order-request previews, and validates live safety gates without
  submitting broker orders.
- Live health output now reports decision preview count and the latest preview.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase B2b1] - 2026-05-24

### Added

- Added runtime reconnect and heartbeat policy models for market-event loops.
- Added `StreamDisconnectedError` for controlled stream disconnect handling.
- Added event-loop result counters for disconnects, reconnects, heartbeat
  misses, source runs, and stopped reason.
- Added `market_data.reconnect` and `market_data.heartbeat` config validation.
- Added deterministic tests for reconnect success, reconnect-disabled failure,
  heartbeat warning mode, and heartbeat fail-closed mode.

### Changed

- `PaperTradingEngine` now passes configured reconnect and heartbeat policies
  into the runtime event loop.
- `configs/paper_alpaca_stream_mock.yaml` documents reconnect and heartbeat
  settings for future stream transports.
- `PHASE_PLAN.md` now splits B2b into B2b1 and B2b2 so guarded live decision
  preview remains separate from stream reliability mechanics.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase B2a] - 2026-05-23

### Added

- Added `qts.market_data.streaming` with an Alpaca stream client protocol,
  `InMemoryAlpacaStreamClient`, `AlpacaStreamEventSource`, and Alpaca
  bar/quote payload normalization helpers.
- Added `configs/paper_alpaca_stream_mock.yaml` for credential-free Alpaca
  stream adapter smoke tests.
- Added tests for Alpaca bar/quote message normalization, control/error
  payload handling, stream subscription filtering, config loading, and paper
  runtime execution through mock Alpaca stream payloads.

### Changed

- `PaperTradingEngine` can now build a market event source from
  `market_data.provider: alpaca_stream` when mock messages or an injected
  stream client are supplied.
- `PAPER` runtime configs now accept `alpaca_stream`, `alpaca_sip_stream`, and
  `alpaca_iex_stream` provider names in addition to B1 providers.
- `PHASE_PLAN.md` now splits B2 into B2a and B2b so real stream transport,
  heartbeat/reconnect policy, and guarded live decision preview remain separate.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase B1] - 2026-05-23

### Added

- Added `qts.engines.event_loop` with `MarketEventSource`,
  `InMemoryMarketEventSource`, `RuntimeEventLoop`, and event-loop result
  counters.
- Added `configs/paper_fake_stream.yaml` for deterministic local paper-runtime
  event-loop smoke tests.
- Added tests for fake-stream dispatch, duplicate suppression, out-of-order
  fail-closed behavior, stale-event checks, session filtering, config loading,
  and paper-engine fake-stream execution.

### Changed

- `PaperTradingEngine.start(max_events=...)` can now process finite fake
  streams through the existing strategy, risk, execution, brokerage, and
  portfolio path.
- `PAPER` runtime configs now accept `market_data.provider: fake_stream` in
  addition to `external_events`.
- `PHASE_PLAN.md` now splits the former Phase B into B1 and B2 so real vendor
  streaming adapters remain isolated from the deterministic event-loop
  foundation.

### Fixed

- None.

### Removed

- None.

---

## [Major Architecture Phase A] - 2026-05-23

### Added

- Added `qts.calendar` with `MarketSession`, `MarketSessionConfig`,
  `MarketSessionService`, `MarketCalendar`, and a deterministic built-in US
  equity calendar provider for `XNYS` and `NASDAQ`.
- Added runtime `market_session` config support for exchange, timezone,
  regular-session-only mode, extended-hours windows, fail-closed behavior, and
  provider selection.
- Added tests for normal trading days, weekends, holidays, early closes,
  daylight-saving conversion, extended hours, and fail-closed provider behavior.

### Changed

- Alpaca historical session filtering now uses the shared market-session service
  so holidays and early closes are handled consistently.
- Paper/live health checks and live order safety now use the shared session
  service instead of broker weekday fallbacks.
- Broker fallback `is_market_open()` implementations now delegate to the
  default market-session service.
- `PHASE_PLAN.md` now tracks major architecture phases A-F from the external
  phase prompt document.

### Fixed

- Fixed weekday-only market-open behavior in fallback broker/session checks.
- Fixed historical intraday filtering on exchange holidays and early-close days.

### Removed

- Removed ad hoc local-time-only filtering from the Alpaca downloader session
  path.

---

## [Post-Review Correctness Fixes] - 2026-05-23

### Added

- Added tests for explicit runtime mode/universe validation, referenced config
  provenance, configured timeframe propagation, strategy-injection count checks,
  reporting annualization options, IBKR fill polling boundaries, and risk-rule
  edge cases.

### Changed

- `configs/base.yaml` no longer provides inherited `runtime.mode`, `symbols`, or
  `timeframe`; active runtime configs now declare those operational fields
  explicitly.
- Backtest and Alpaca paper templates now allow fractional/notional execution
  when using fixed-notional risk sizing, while the IBKR paper template remains
  quantity-based.
- Reusable risk session defaults are disabled to avoid implying fixed UTC
  regular-session hours across daylight-saving changes.
- Local CSV and Parquet providers now receive the configured default timeframe
  from the backtest engine and ML training script.
- Reporting metrics now support configured `annualization_factor` and
  `risk_free_rate`, and unsupported reporting fields fail validation.

### Fixed

- Fixed referenced strategy/risk profile provenance so profiles that use
  `extends` include their full source-file chain in runtime metadata.
- Fixed notional sizing compatibility with `execution.allow_fractional: false`
  by failing fast unless the runtime uses quantity-compatible sizing or an
  explicitly disabled template.
- Fixed order construction so `quantity` and `notional` are mutually exclusive
  before broker payload generation.
- Fixed trading-session close semantics so `market_close` is exclusive.
- Fixed cooldown enforcement to apply per `(strategy_id, symbol)` instead of
  per symbol only.
- Fixed daily loss checks to include realized plus unrealized PnL.
- Fixed projected exposure for SELL notional intents when no price is available.
- Fixed injected strategy handling so backtest and paper engines reject too few
  or too many injected strategy instances.
- Fixed IBKR fill polling so fills exactly at the `since` boundary are excluded.

### Removed

- Removed inherited active runtime defaults from the shared base config.

---

## [Post-Review Config Hardening] - 2026-05-23

### Added

- Added runtime `config_ref` support for reusable strategy profiles.
- Added runtime `risk_ref` support for reusable risk profiles.
- Added multiple-file `extends` support with circular inheritance detection.
- Added generic `${VAR}` and `${VAR:-default}` environment interpolation for
  runtime configs.
- Added `qts config validate`, `qts config dump`, `qts config explain`, and
  `qts config list-snippets`.
- Added exact `bar_interval` metadata/filtering for local historical bars.
- Added data-adjustment metadata/filtering for local historical bars.

### Changed

- Runtime config loading now resolves paths relative to the discovered project
  root and records config metadata/source files in the effective config.
- Runtime configs now import the shared SMA strategy and risk profiles instead
  of duplicating complete strategy/risk blocks.
- Local CSV/Parquet providers now filter by exact bar interval when configured.
- Backtest replay now passes configured adjustment and exact interval settings
  through the data provider and data portal.
- Download and ML scripts now use layered config loading and deterministic path
  resolution.
- Documentation now describes resolved config inspection and SIP-only Alpaca
  historical downloads.

### Fixed

- Fixed stale informational `required_features` fields in rule-strategy snippets
  by removing unused metadata.
- Fixed misleading Alpaca feed comments that advertised unsupported IEX mode.
- Fixed late risk-sizing failures by validating sizing parameters during config
  load.
- Fixed the risk of accidentally mixing 1-minute, 5-minute, and 15-minute bars
  when backtesting against a shared dataset root.
- Fixed exposure rules so risk-reducing sells and buy-to-cover orders are
  evaluated against projected post-trade exposure instead of proposed order
  notional alone.

### Removed

- None.

---

## [Phase 10] - 2026-05-22

### Added

- Added a config-driven Alpaca SIP historical stock bar downloader under
  `qts.market_data.alpaca`.
- Added `scripts/download_data.py` for downloading historical K-line bars to
  normalized CSV or Parquet.
- Added `configs/data/alpaca_sip_bars.yaml` for user-managed download settings.
- Added support for user levels `1min`, `5min`, `15min`, `1hour`, and `1day`.
- Added unit tests for timeframe normalization, paginated responses, CSV/Parquet
  output, and config/env loading.

### Changed

- Exported Alpaca downloader helpers from `qts.market_data`.
- Added config and CLI support for `output.format: csv` or `parquet`.
- Added partitioned dataset output for Alpaca SIP downloads with configurable
  `output.partition_by` fields.
- Added explicit local regular-session filtering after Alpaca downloads so the
  API request can cover the full configured interval while stored intraday bars
  keep `[09:30, 16:00)` America/New_York start times.
- Updated `configs/backtest.yaml` to default to the partitioned CSV dataset
  produced under `data/alpaca`.
- Updated CSV and Parquet local providers to read partitioned dataset
  directories recursively.
- Replaced the sample fixed data-download filename with partitioned
  `timeframe`/`symbol`/`date` storage so multi-symbol downloads do not land in a
  single large file.
- Updated `.env.example`, README, user manual, system handbook, project state,
  system design, phase plan, and decisions docs for the new data download path.

### Fixed

- None.

### Removed

- None.

---

## [Documentation Additions] - 2026-05-22

### Added

- Added `docs/user_manual.md` with detailed setup, configuration, execution,
  broker, ML, live dry-run, safety, and troubleshooting guidance.
- Added `docs/system_handbook.md` with architecture explanations, runtime
  flows, file-by-file system reference, extension workflows, and debugging maps.

### Changed

- Linked the new manuals from `README.md`.
- Updated `PROJECT_STATE.md` to list the new maintained documentation files.

### Fixed

- None.

### Removed

- None.

---

## [Phase 9] - 2026-05-22

### Added

- Implemented a dependency-free IBKR Web API client boundary under
  `integrations/ibkr/`.
- Added IBKR payload mapping for order requests, normalized orders, fill deltas,
  account summaries, and positions.
- Implemented `IBKRBrokerage` for paper trading through the normalized
  `Brokerage` interface.
- Added an in-memory IBKR client for credential-free mock paper runs.
- Added `configs/paper_ibkr.yaml` with IBKR account and symbol `conid` mapping
  settings.
- Added mocked IBKR tests for mapping, brokerage behavior, fail-closed reply
  prompts, live-mode rejection, and paper engine initialization.

### Changed

- Updated `PaperTradingEngine` to select either `alpaca_paper` or `ibkr_paper`
  from configuration.
- Updated `scripts/run_paper_trading.py` wording so the runner is broker-neutral.
- Updated README, system design, interface, data model, project state, phase
  plan, and environment-example documentation for IBKR paper support.
- Added ADR-021 documenting the IBKR adapter boundary and manual-reply safety
  policy.

### Fixed

- None.

### Removed

- None.

### Notes

- IBKR live order submission remains disabled.
- IBKR order responses that require manual reply confirmation fail closed; the
  adapter does not auto-confirm those prompts.

---

## [Post-Phase 8 Design Review Fixes] - 2026-05-22

### Changed

- Moved the shared open-order status set into the domain layer so
  `BacktestBrokerage` no longer depends on the execution package.
- Added shared engine feature-pipeline settings resolution from
  `StrategyConfig.feature_config`.
- Added explicit event-driven market-data provider validation for paper and live
  engines.
- Added explicit paper broker selection validation from `broker.broker_type`.
- Wired `execution.allow_fractional` into execution order validation and live
  order safety validation.
- Updated the ML strategy fixture config with explicit feature specs and schema
  version for runtime training-serving consistency.
- Updated paper/live configuration templates to declare `external_events` as the
  current supported market-data provider.

### Fixed

- Backtest `DefaultDataPortal` instances now enforce replay bounds so strategies
  cannot read future bars from the injected data portal during replay.
- `FeaturePipeline([])` now preserves an explicit empty feature set instead of
  falling back to default features.
- `MLSignalStrategy` now validates the runtime feature pipeline schema against
  the loaded model during initialization when a pipeline is available.
- Paper/live configs no longer imply that Alpaca market data is implemented in
  the current phase.

### Removed

- None.

---

## [Phase 8] - 2026-05-22

### Added

- Implemented monitoring primitives under `qts.monitoring`:
  - health check results and aggregation,
  - runtime metric logging,
  - alert events and alert sinks,
  - recovery manager behavior,
  - broker/internal reconciliation health checks,
  - live safety validation helpers.
- Added guarded `LiveEngine` scaffolding with explicit safety gates and
  dry-run-only broker initialization.
- Added live order safety validation for allowed symbols, account allowlists,
  max order notional, and max order quantity.
- Added `scripts/run_live_trading.py` for safe dry-run live initialization.
- Added `docs/runbooks.md` with Phase 8 operational procedures.
- Added Phase 8 tests for:
  - live safety gates,
  - account and symbol allowlists,
  - max order size checks,
  - health check aggregation,
  - alert hooks,
  - runtime metrics logging,
  - recovery manager stop behavior,
  - reconciliation mismatches,
  - dry-run live engine initialization.

### Changed

- Updated `configs/live_alpaca.yaml` with explicit live safety defaults.
- Updated `README.md` with Phase 8 status and dry-run live initialization
  instructions.
- Updated `PROJECT_STATE.md` to mark Phase 8 complete.
- Updated `INTERFACES.md` with monitoring and live-safety helper contracts.
- Added ADR-020 documenting the guarded dry-run live-engine foundation.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 8 does not enable real live broker order submission.
- The dry-run live engine validates operational wiring and safety controls
  without touching external broker APIs.

---

## [Phase 7] - 2026-05-22

### Added

- Implemented offline ML dataset construction from existing feature pipelines.
- Added forward-return directional labels with configurable horizon and
  thresholds.
- Added chronological train/validation/test splits, walk-forward split helpers,
  and temporal leakage checks.
- Implemented a dependency-free directional baseline model with training,
  evaluation, and runtime prediction support.
- Added a filesystem model registry under `artifacts/models/` conventions.
- Implemented `DefaultMLModelInference` for loading registered model artifacts
  and producing normalized `ModelPrediction` objects.
- Added `MLSignalStrategy` to convert model predictions into broker-agnostic
  `Signal` outputs.
- Added fixture ML configs:
  - `configs/ml/directional_baseline.yaml`,
  - `configs/strategies/ml_directional.yaml`.
- Added `scripts/train_model.py` for local Phase 7 model training.
- Added Phase 7 tests for:
  - dataset construction and labels,
  - chronological and walk-forward splits,
  - temporal leakage detection,
  - model registry and inference,
  - ML strategy signal conversion,
  - fixture-backed training pipeline execution.

### Changed

- Updated `README.md` with Phase 7 status and local training instructions.
- Updated `PROJECT_STATE.md` to mark Phase 7 complete and Phase 8 pending.
- Added ADR-019 documenting the dependency-free Phase 7 baseline model and local
  registry approach.
- Extended the strategy factory to instantiate the ML signal strategy from
  configuration.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 7 does not introduce advanced model libraries, online learning,
  optimization, production model monitoring, or live trading readiness.
- The initial ML model is intentionally small and dependency-free so workflow
  contracts can be tested in the current local environment.

---

## [Phase 6] - 2026-05-22

### Added

- Implemented a dependency-free Alpaca Trading API client boundary under
  `integrations/alpaca/`.
- Added Alpaca payload mapping for:
  - order requests,
  - normalized orders,
  - fill deltas from polled order state,
  - accounts,
  - positions.
- Implemented `AlpacaBrokerage` for paper trading through the normalized
  `Brokerage` interface.
- Added an in-memory Alpaca client for credential-free mock paper runs.
- Implemented portfolio reconciliation against broker account and positions.
- Implemented `PaperTradingEngine` initialization and externally supplied
  market-event handling for paper mode.
- Added `scripts/run_paper_trading.py` for paper runtime initialization.
- Added mocked Phase 6 tests for:
  - Alpaca mapping,
  - broker order submission and fill polling,
  - broker error normalization,
  - live-mode safety rejection,
  - portfolio reconciliation,
  - mock paper engine initialization,
  - shared paper execution path from strategy to portfolio fill.

### Changed

- Updated `configs/paper_alpaca.yaml` with explicit paper safety settings.
- Updated `README.md` with Phase 6 status and mock paper runtime instructions.
- Updated `PROJECT_STATE.md` to mark Phase 6 complete and Phase 7 pending.
- Added ADR-018 documenting the Alpaca REST boundary, mock client, and polling
  fill approach.
- Updated `.env.example` to describe Alpaca credentials as active paper
  configuration values.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 6 does not enable live trading.
- Alpaca market data and streaming order updates remain separate future work.
- Paper fills are currently detected by polling order filled-quantity deltas.

---

## [Phase 5] - 2026-05-22

### Added

- Implemented internal portfolio accounting with:
  - fill application,
  - position accounting,
  - realized and unrealized PnL,
  - cash ledger entries,
  - trade ledger entries,
  - mark-to-market portfolio snapshots.
- Implemented reporting metrics:
  - total return,
  - annualized return when the period is long enough,
  - volatility,
  - Sharpe ratio,
  - max drawdown,
  - win rate,
  - profit factor,
  - average trade PnL,
  - trade counts,
  - exposure summary.
- Implemented `BacktestReporter` for Markdown, JSON, and CSV artifact export.
- Implemented deterministic bar-driven `BacktestEngine` wiring together market
  data, features, strategy, risk, execution, backtest brokerage, portfolio, and
  reporting.
- Added runnable scripts:
  - `scripts/run_backtest.py`,
  - `scripts/generate_report.py`.
- Added a local SMA crossover fixture config and CSV fixture:
  - `configs/backtest_fixture.yaml`,
  - `tests/fixtures/market_data/backtest_sma_cross.csv`.
- Added Phase 5 tests for:
  - portfolio accounting,
  - metric calculation,
  - report artifact export,
  - end-to-end backtest execution,
  - empty-signal backtests,
  - fixed-fixture reproducibility.

### Changed

- Updated `README.md` to reflect Phase 5 status and fixture backtest commands.
- Updated `PROJECT_STATE.md` to mark Phase 5 complete and Phase 6 pending.
- Added ADR-017 documenting the deterministic bar-driven Phase 5 backtest engine
  and artifact-export approach.
- Added strategy attribution to backtest broker order metadata so portfolio trade
  ledgers can preserve strategy IDs without changing stable fill models.

### Fixed

- Avoided intraday annualized-return overflow by returning no annualized value
  for periods shorter than one day.

### Removed

- None.

### Notes

- Phase 5 does not implement Alpaca integration, paper/live runtime engines, ML
  workflows, operational monitoring, or visual plotting.
- Report output is intentionally lightweight and dependency-free: Markdown,
  JSON, and CSV.

---

## [Phase 4] - 2026-05-22

### Added

- Implemented normalized `Brokerage` protocol.
- Implemented execution workflow components:
  - `build_order_request`,
  - `OrderManager`,
  - `OrderRouter`,
  - `FillHandler`,
  - `ExecutionEngine`.
- Implemented `BacktestBrokerage` with broker-side order, fill, cash, account,
  and position state.
- Added simulated order lifecycle behavior for accepted, rejected, submitted,
  partially filled, filled, canceled, and expired orders.
- Added simulated market, limit, stop, and stop-limit order handling.
- Added deterministic fill policies:
  - `next_bar_open`,
  - `next_bar_close`,
  - `next_bar_typical_price`,
  - `quote_bid_ask`.
- Added simple commission and slippage models for backtest fills.
- Added broker-side buying-power/cash and position checks.
- Added Phase 4 unit tests for:
  - order request construction,
  - rejected risk decision handling,
  - order routing,
  - order manager cancellation and open-order tracking,
  - market, limit, stop, quote, partial-fill, insufficient-cash, cancellation,
    slippage, and commission behavior.

### Changed

- Updated `README.md` to reflect Phase 4 status and execution/backtest broker
  modules.
- Updated `PROJECT_STATE.md` to mark Phase 4 complete and Phase 5 pending.
- Added ADR-016 documenting the Phase 4 backtest brokerage state and fill-policy
  decisions.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 4 does not implement a full backtest engine, internal portfolio
  accounting, ledgers, reporting, Alpaca integration, ML workflows, or live/paper
  trading runtime behavior.
- `BacktestBrokerage` does not load historical data; callers must provide market
  events from the market data layer or future engines.

---

## [Phase 3] - 2026-05-22

### Added

- Implemented broker-agnostic strategy contracts and shared strategy helpers.
- Implemented example rule-based strategies:
  - `SMACrossoverStrategy`,
  - `RSIMeanReversionStrategy`,
  - `create_strategy` factory for Phase 3 strategy configs.
- Implemented signal and target-position conversion into normalized
  `TradeIntent` objects.
- Implemented `DefaultPositionSizer` with fixed quantity, fixed notional, and
  percent-of-equity sizing policies.
- Implemented risk result helpers, default risk rules, and `RiskEngine`.
- Added basic risk rules for:
  - symbol allow/block lists,
  - trading session checks,
  - daily loss limit placeholder,
  - cooldown,
  - max position notional,
  - max symbol weight,
  - max gross exposure,
  - buying power.
- Added Phase 3 configuration templates under `configs/strategies/` and
  `configs/risk/`.
- Added Phase 3 unit tests for deterministic strategy output, signal/target
  conversion, sizing, approvals, rejections, risk modifications, session checks,
  buying power, daily-loss rejection, gross exposure, and cooldown.

### Changed

- Updated `README.md` to reflect Phase 3 status and the new strategy/risk
  modules.
- Updated `PROJECT_STATE.md` to mark Phase 3 complete and Phase 4 pending.
- Added ADR-015 documenting the Phase 3 signal-first strategy behavior and
  risk-owned sizing decision.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 3 does not implement order routing, broker adapters, fill simulation,
  portfolio accounting, backtest orchestration, reporting, ML workflows, or
  live/paper trading runtime behavior.
- Strategy and risk tests run with standard-library `unittest`.

---

## [Phase 2] - 2026-05-22

### Added

- Implemented market data protocols for `MarketDataProvider` and `DataPortal`.
- Implemented historical bar normalization helpers:
  - required bar column validation,
  - UTC timestamp normalization,
  - symbol normalization,
  - duplicate symbol/timestamp/timeframe detection,
  - date/symbol/timeframe filtering.
- Implemented local market data providers:
  - `CSVBarProvider`,
  - `LocalParquetProvider` using optional pandas or pyarrow,
  - `ReplayMarketDataProvider`.
- Implemented `DefaultDataPortal` for historical bar access, current market event
  state, quote passthrough, and feature-frame access.
- Implemented reusable batch indicators:
  - SMA,
  - EMA,
  - RSI,
  - MACD,
  - Bollinger Bands,
  - ATR,
  - VWAP,
  - returns,
  - volatility,
  - volume mean,
  - volume ratio.
- Implemented `FeatureSpec`, `FeatureSchema`, and `FeaturePipeline`.
- Added CSV market data fixtures for normal, duplicate, and missing-column cases.
- Added Phase 2 unit tests for:
  - CSV loading and normalization,
  - missing-column errors,
  - duplicate timestamp errors,
  - deterministic replay order,
  - data portal access,
  - known-value indicators,
  - feature pipeline output and schema validation.

### Changed

- Updated `README.md` to reflect Phase 2 status, optional Parquet dependencies,
  and CSV provider usage.
- Added optional `data` dependency extra for pandas/pyarrow-backed Parquet loading.
- Updated `PROJECT_STATE.md` to mark Phase 2 complete and Phase 3 pending.
- Added ADR-014 documenting row-oriented feature frames and optional Parquet
  dependencies.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 2 does not implement strategies, risk rules, execution logic, brokers,
  portfolio accounting, engines, reporting, ML workflows, or live/paper trading
  runtime behavior.
- CSV fixtures and tests run without third-party dependencies. Parquet loading
  requires installing optional `data` dependencies.

---

## [Phase 1] - 2026-05-22

### Added

- Implemented stable domain enums from `DATA_MODELS.md`.
- Implemented validated dataclass domain models for:
  - market data objects,
  - signals and trade intents,
  - risk decisions,
  - orders and fills,
  - positions, accounts, and portfolio snapshots,
  - ledger entries,
  - backtest results,
  - feature and prediction records,
  - strategy, risk, broker, and runtime config models.
- Added domain serialization helpers that normalize enums and UTC timestamps.
- Implemented core configuration loading and validation:
  - layered YAML config loading with `extends`,
  - deep merge behavior,
  - `.env` key-value loading,
  - validated `RuntimeConfig` construction,
  - optional PyYAML support with a small internal parser for repository templates.
- Implemented `RealClock` and `ReplayClock`.
- Implemented common exception categories.
- Implemented basic logging setup with plain text or JSON formatting.
- Added CLI config validation with `qts --config configs/backtest.yaml`.
- Added Phase 1 unit tests for domain validation, enum values, config loading,
  clocks, and logging.

### Changed

- Updated config templates with valid default symbols, date range, and strategy
  config shape so Phase 1 config loading can validate them.
- Updated `README.md` with Phase 1 status, test commands, and config validation
  instructions.
- Updated `PROJECT_STATE.md` to mark Phase 1 complete and Phase 2 pending.
- Added ADR-013 documenting the standard-library dataclass/config-parser choice.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 1 does not implement market data providers, indicators, strategies,
  risk rules, execution logic, brokers, portfolio accounting, engines, reporting,
  ML, or live/paper trading runtime behavior.
- Tests run locally with `unittest`; `pytest` remains an optional dependency and
  was not installed in the current virtual environment.

---

## [Phase 0] - 2026-05-22

### Added

- Created initial documentation package:
  - `SYSTEM_DESIGN.md`
  - `PHASE_PLAN.md`
  - `INTERFACES.md`
  - `DATA_MODELS.md`
  - `DECISIONS.md`
  - `PROJECT_STATE.md`
  - `CHANGELOG.md`
- Defined modular quantitative trading system architecture.
- Defined phase-by-phase implementation plan.
- Defined core interfaces for:
  - market data,
  - features,
  - strategies,
  - ML inference,
  - risk,
  - execution,
  - brokerage,
  - portfolio,
  - engines,
  - reporting.
- Defined stable domain data models.
- Recorded initial architectural decisions.
- Initialized project state and next implementation task.
- Initialized Git repository metadata.
- Added repository scaffold:
  - `pyproject.toml`
  - `README.md`
  - `.env.example`
  - `.gitignore`
  - `configs/base.yaml`
  - `configs/backtest.yaml`
  - `configs/paper_alpaca.yaml`
  - `configs/live_alpaca.yaml`
  - `src/qts/` package layout
  - `tests/test_scaffold.py`
  - `data/.gitkeep`
  - `artifacts/.gitkeep`
- Added placeholder package modules matching the architecture in `SYSTEM_DESIGN.md`.
- Added standard-library smoke tests for required docs, package imports,
  configuration templates, and project metadata.

### Changed

- Updated `PROJECT_STATE.md` to reflect that repository scaffolding exists while
  Phase 1 domain/core implementation remains pending.

### Fixed

- None.

### Removed

- None.

### Notes

- No trading business logic has been implemented.
- No domain models, config loader, clocks, broker adapters, strategies, risk
  rules, execution logic, portfolio accounting, engines, or reporting logic have
  been implemented.
- Phase 1 should start with domain models, core config loading, clocks,
  exceptions, logging, and focused tests.
