# PROJECT_STATE.md

# Project State

## 1. Current Status

The project has completed the initial documentation package, repository scaffold,
Phase 1 core foundation, Phase 2 market data/feature layer, Phase 3
strategy/risk layer, Phase 4 execution/backtest brokerage layer, Phase 5
backtest engine/reporting layer, Phase 6 Alpaca paper trading integration,
Phase 7 ML workflow, Phase 8 monitoring/live-trading readiness, and Phase 9
IBKR paper brokerage foundation, Phase 10 Alpaca SIP historical data download,
Major Architecture Phase C1 normalized broker-event polling sync, Major
Architecture Phase C2 vendor broker push adapter boundaries, Major Architecture
Phase C3 engine lifecycle synchronization hardening, Major Architecture Phase
D1 manual live order submission safety envelope, Major Architecture Phase D2
broker-specific live adapter enablement, Major Architecture Phase D3 automated
live decision submission, and Major Architecture Phase E chart reporting and
visual backtest diagnostics, Major Architecture Phase F1 ML model manifest
contracts, Major Architecture Phase F2 ML approval and stage gates, and Major
Architecture Phase F3 runtime ML metadata and audit diagnostics, followed by
the final system design and implementation review, the shared runtime decision
pipeline refactor, the brokerage factory refactor, the shared runtime data
portal refactor, and the package workflows/thin scripts refactor.

The Python package now includes stable domain enums and data models, core config
loading and validation, clocks, common exceptions, logging setup, local
historical bar providers, config-driven Alpaca SIP historical bar download,
data normalization, deterministic replay, a default data portal, an in-memory
runtime data portal, reusable batch indicators, feature schemas, feature
pipelines,
broker-agnostic strategy interfaces, SMA crossover and RSI mean-reversion
example strategies, normalized signal-to-intent conversion, position sizing, a
default risk engine, basic risk rules, an execution engine, order request
builder, order manager, order router, fill handler, normalized broker lifecycle
events, normalized brokerage interface, simulated `BacktestBrokerage`, internal
portfolio accounting, trade and cash ledgers, mark-to-market snapshots, a deterministic bar-driven
`BacktestEngine`, reporting metrics, report artifact export, optional static
SVG chart diagnostics, configuration
templates, package-level command workflows, thin CLI scripts, a small CLI
config validation path, runnable backtest scripts, a
dependency-free Alpaca Trading API client boundary, Alpaca payload mapping,
Alpaca broker trade-update event normalization, `AlpacaBrokerage`, mock Alpaca
client support, portfolio reconciliation, `PaperTradingEngine`, a paper runtime
initialization script, offline ML dataset construction, forward-return labels,
chronological and walk-forward splitting,
leakage checks, a dependency-free directional training pipeline, filesystem
model registry, runtime model inference, an ML strategy adapter, fixture ML
configs, model manifest/schema-hash contracts, model approval stage gates,
runtime ML diagnostics, a training script, monitoring health checks, runtime
metrics logging,
alert hooks, recovery behavior, broker reconciliation checks, live safety
gates, guarded dry-run `LiveEngine` scaffolding, a manual live order submission
safety envelope, Alpaca live adapter construction behind explicit D1 gates,
optional automated live decision submission behind a separate gate and kill
switch, operational runbooks, and focused tests. It also includes a
dependency-free IBKR Web API client boundary,
IBKR payload mapping, IBKR broker order-update event normalization,
`IBKRBrokerage`, a mock IBKR client, an IBKR paper configuration template, and
mocked IBKR tests.

Post-review config hardening has added reusable strategy `config_ref` imports,
`risk_ref` imports, multiple-base `extends`, circular include detection, strict
runtime config validation, deterministic path resolution, effective-config CLI
inspection commands, exact `bar_interval` filtering, and data-adjustment
validation for local historical bars.

The latest post-review correctness pass removes inherited active runtime
defaults from the shared base config, preserves full referenced-profile
provenance, propagates configured timeframes into local CSV/Parquet providers,
enforces quantity/notional exclusivity, validates fixed-notional sizing against
the fractional execution policy, tightens session/cooldown/daily-loss risk
rules, rejects mismatched injected strategy lists, supports explicit reporting
annualization settings, and fixes the IBKR fill polling `since` boundary.

Major Architecture Phase A has added a shared exchange calendar and
market-session service under `qts.calendar`. Runtime configs now support
`market_session`, Alpaca historical session filtering uses the shared US equity
calendar, paper/live health checks and live order safety use the shared service,
and broker fallback `is_market_open()` implementations no longer use
weekday-only logic.

Major Architecture Phase B1 has added a deterministic runtime market-event loop
foundation. Paper configs can now use `market_data.provider: fake_stream`,
finite fake streams can drive `PaperTradingEngine.start(max_events=...)`, and
the loop applies duplicate suppression, out-of-order fail-closed checks,
optional freshness checks, and `MarketSessionService` filtering before dispatch.

Major Architecture Phase B2a has added a mockable Alpaca stream adapter
boundary. Paper configs can now use `market_data.provider: alpaca_stream` with
Alpaca-shaped `mock_messages` or an injected stream client; the adapter
normalizes Alpaca bar/quote payloads into internal `Bar`/`Quote` events before
they enter the runtime event loop.

Major Architecture Phase B2b1 has added bounded reconnect and heartbeat/data-gap
policy to the runtime market-event loop. Event-loop health output now includes
disconnect, reconnect, heartbeat miss, source-run, and stopped-reason counters,
and paper runtime loops read `market_data.reconnect` and
`market_data.heartbeat` settings.

Major Architecture Phase B2b2 has added guarded live decision preview. Dry-run
live bar events now run through live data portal state, feature updates,
strategies, risk evaluation, normalized order-request construction, and live
safety validation, then record a preview without calling broker order
submission.

Major Architecture Phase C1 has added normalized broker events and polling
synchronization. Broker order/fill/account/position updates now have a stable
`BrokerEvent` envelope, existing broker polling can emit order/fill events, the
execution layer applies broker events idempotently, and the paper engine routes
polling fallback through that event contract.

Major Architecture Phase C2 has added mockable vendor broker push adapter
boundaries. Alpaca-shaped trade updates and IBKR-shaped order updates can now
be consumed from in-memory event clients and normalized into the same
`BrokerEvent` order/fill contract without opening real network streams.

Major Architecture Phase C3 has added checkpointed broker-event synchronization
for paper and live engines. Broker-event sources now run through duplicate
suppression, restart checkpoints, out-of-order detection, optional gap
fail-closed checks, and reconciliation before and after sync. Execution fill
handling also avoids double-counting when a cumulative broker order update
already reflects the matching fill event, and failed broker-event application
remains retryable after missing lifecycle state is recovered.

Major Architecture Phase D1 has added a manual live order submission envelope.
`LiveEngine.submit_live_order(...)` can submit a normalized `OrderRequest` only
after non-dry-run live mode, account allowlists, symbol allowlists, order caps,
market-session checks, reconciliation, `confirm_live_trading=true`, and
`enable_order_submission=true` all pass. The sample live config keeps
submission disabled by default, and automated strategy-driven live submission
remains future Phase D work.

Major Architecture Phase D2 has enabled broker-specific live adapter
construction for Alpaca behind the D1 submission envelope. Non-dry-run
`LiveEngine` instances can construct `AlpacaBrokerage` only after the explicit
live submission gates pass, while `AlpacaBrokerage` itself rejects unsafe live
mode, dry-run, mock, missing confirmation, and missing submission-gate
configurations. IBKR live brokerage remains fail-closed.

Major Architecture Phase D3 has enabled optional automated live decision
submission for externally supplied live bar events. Safety-approved previews can
submit through the D1 `submit_live_order(...)` path only when
`enable_automated_submission=true`, the automated kill switch is not set, D1
submission gates pass, and reconciliation before and after submission matches.
Submission failures and post-submit reconciliation mismatches stop further
automated submissions and report critical live health.

Major Architecture Phase E has added optional dependency-free visual backtest
diagnostics. When `reporting.generate_plots=true`, report export writes static
SVG equity-curve charts with buy/sell fill markers and drawdown charts, records
them in `BacktestResult.artifacts`, and keeps metric/CSV export intact if plot
generation fails.

Major Architecture Phase F1 has added local ML artifact governance contracts.
`FileModelRegistry.save_model(...)` now writes a portable `manifest.json`
beside `model.json`, manifests include deterministic feature-schema hashes,
model loads validate saved manifests when present, and runtime inference exposes
the loaded manifest while preserving legacy artifact loading.

Major Architecture Phase F2 has added local ML approval and stage gates.
`FileModelRegistry` can transition manifests through candidate, validated,
approved, and archived stages with approval metadata and transition history.
Runtime inference and ML strategy configs can require approved models or limit
loading to specific manifest stages.

Major Architecture Phase F3 has added runtime ML metadata and audit
diagnostics. Predictions and ML strategy signals now carry manifest identity,
stage, and feature-schema hash metadata. Backtest metrics/report summaries and
paper/live health checks can expose loaded ML model contracts without adding
persistent audit storage.

Post-Phase 8 design review fixes have been applied for replay-bounded backtest
data portal reads, broker/execution dependency direction, and explicit ML
runtime feature schema wiring. ADR-007 follow-up fixes made the original
paper/live market-data mode explicit through `market_data.provider:
external_events`; Phase B1 adds paper-only `fake_stream` support, and Phase B2a
adds paper-only `alpaca_stream` adapter support. Phase B2b1 adds runtime stream
reliability policy. Phase B2b2 adds guarded dry-run live decision previews.
Phase C1 adds normalized broker-event polling synchronization, Phase C2 adds
mockable vendor broker push adapter boundaries, and Phase C3 adds checkpointed
engine broker-event synchronization hardening. Phase D1 adds a manually invoked
live order submission path behind explicit production gates. Phase D2 enables
the selected Alpaca live adapter behind those same gates. Phase D3 allows
safety-approved live decision previews to submit through that path only behind
a separate automated-submission gate and kill switch. Phase E adds optional
static report chart diagnostics. Phase F1 adds model manifest and schema-hash
contracts. Phase F2 adds opt-in ML approval and stage loading policy. Live
remains external-event driven. Phase F3 adds runtime ML decision diagnostics.
Runtime order validation also enforces `execution.allow_fractional`.

The final system design review aligned the remaining implementation details
with the architecture documents: execution and monitoring import only the
`Brokerage` protocol instead of the concrete broker package, risk session
checks prefer the shared `MarketSessionService` when engines provide it,
paper/live data portals honor requested feature-name filtering, and stale
project-state/data-model documentation has been corrected.

The shared runtime decision pipeline refactor centralizes the data-portal
advance, latest-price update, portfolio mark-to-market, feature update,
strategy evaluation, risk-context construction, and risk evaluation sequence in
`RuntimeDecisionPipeline`. `BacktestEngine`, `PaperTradingEngine`, and
guarded `LiveEngine` decision previews now reuse that common path while keeping
fills, broker synchronization, order submission, reporting, monitoring, and
live safety gates in the owning engines.

The brokerage factory refactor centralizes adapter selection in
`qts.brokers.factory`. Backtest, paper, and live engines now request brokerages
from the factory while retaining connection lifecycle, simulated fills,
paper/live synchronization, and live safety policy in the engines.

The shared runtime data portal refactor centralizes externally supplied
paper/live market-event state in `InMemoryRuntimeDataPortal`. Paper and live
engines now share bar history, current bar, quote, lookback, feature-frame, and
per-symbol retention behavior while `BacktestEngine` continues to use the
replay-bounded `DefaultDataPortal`.

The package workflows/thin scripts refactor moves reusable command behavior to
`qts.workflows`. The `scripts/` entry points now parse arguments, delegate to
package workflow functions, print concise command output, and preserve existing
return-code behavior.

- **Current phase:** Package workflows/thin scripts refactor complete
- **Completed phases:**
  - Phase 0 - Documentation and repository scaffold initialization
  - Phase 1 - Project Skeleton and Core Domain Models
  - Phase 2 - Market Data and Feature Layer
  - Phase 3 - Strategy and Risk Layer
  - Phase 4 - Execution Layer and BacktestBrokerage
  - Phase 5 - Backtest Engine and Reporting
  - Phase 6 - Alpaca Paper Trading Integration
  - Phase 7 - ML Workflow
  - Phase 8 - Monitoring, Reconciliation, and Live-Trading Readiness
  - Phase 9 - IBKR Paper Brokerage Foundation
  - Phase 10 - Alpaca SIP Historical Data Download
  - Major Architecture Phase A - Exchange Calendar and Market Session Service
  - Major Architecture Phase B1 - Deterministic Runtime Event Loop and Fake Stream
  - Major Architecture Phase B2a - Alpaca Stream Adapter Boundary for Paper Runtime
  - Major Architecture Phase B2b1 - Runtime Reconnect and Heartbeat Policy
  - Major Architecture Phase B2b2 - Guarded Live Decision Preview
  - Major Architecture Phase C1 - Normalized Broker Events and Polling Sync
  - Major Architecture Phase C2 - Vendor Broker Push Adapter Boundaries
  - Major Architecture Phase C3 - Engine Lifecycle Synchronization Hardening
  - Major Architecture Phase D1 - Manual Live Order Submission Safety Envelope
  - Major Architecture Phase D2 - Broker-Specific Live Adapter Enablement
  - Major Architecture Phase D3 - Automated Live Decision Submission
  - Major Architecture Phase E - Chart Reporting and Visual Backtest Diagnostics
  - Major Architecture Phase F1 - ML Model Manifests and Schema Hash Contracts
  - Major Architecture Phase F2 - ML Approval and Stage Gates
  - Major Architecture Phase F3 - Runtime ML Metadata and Audit Diagnostics
  - Final system design and implementation review
  - Shared runtime decision pipeline refactor
  - Brokerage factory refactor
  - Shared runtime data portal refactor
  - Package workflows and thin scripts refactor
- **In-progress phase:** None
- **Next recommended task:** None. Start a new documented phase only when new
  requirements are defined.

## 2. Completed Phases

| Phase | Status | Notes |
|---|---|---|
| Phase 0 | Complete | Documentation package created. Repository scaffold initialized with package layout, configuration templates, dependency metadata, README, and smoke tests. |
| Phase 1 | Complete | Implemented stable domain models/enums, core config loading, clocks, exceptions, logging setup, CLI config validation, and unit tests. |
| Phase 2 | Complete | Implemented local market data interfaces/providers, CSV fixtures, optional Parquet provider, replay, default data portal, batch indicators, feature schema/pipeline, and tests. |
| Phase 3 | Complete | Implemented broker-agnostic strategy interfaces, SMA crossover and RSI example strategies, signal-to-intent conversion, position sizing, basic risk rules, default risk engine, configs, and tests. |
| Phase 4 | Complete | Implemented execution engine, order request builder, order manager, router, fill handler, brokerage protocol, BacktestBrokerage, fill/cost models, broker-side cash/positions, and tests. |
| Phase 5 | Complete | Implemented internal portfolio accounting, ledgers, mark-to-market snapshots, bar-driven BacktestEngine, metrics, report artifact export, fixture backtest config, scripts, and tests. |
| Phase 6 | Complete | Implemented Alpaca integration client/mapping, AlpacaBrokerage, mock paper mode, paper engine initialization/event handling, portfolio reconciliation, runner script, and mocked tests. |
| Phase 7 | Complete | Implemented ML dataset building, forward-return labeling, time-aware splits, leakage checks, dependency-free directional model training/evaluation, filesystem registry, runtime inference, ML signal strategy adapter, fixture configs, training script, and tests. |
| Phase 8 | Complete | Implemented monitoring health checks, metrics, alerts, recovery behavior, broker reconciliation checks, live safety gates, guarded dry-run LiveEngine scaffolding, live runner script, runbooks, and tests. |
| Phase 9 | Complete | Implemented dependency-free IBKR client/mapping, IBKRBrokerage, mock paper mode, IBKR paper config, paper engine factory support, and mocked tests. |
| Phase 10 | Complete | Implemented config-driven Alpaca SIP historical bar downloader, partitioned CSV/Parquet output, download script, data config template, docs, and tests. |
| Major Architecture Phase A | Complete | Implemented shared US equity calendar/session service, runtime config validation, Alpaca filtering integration, paper/live health checks, live order safety, and tests. |
| Major Architecture Phase B1 | Complete | Implemented deterministic runtime event-loop primitives, fake in-memory stream support, paper-engine finite stream execution, config template, and tests. |
| Major Architecture Phase B2a | Complete | Implemented mockable Alpaca stream payload adapter, paper-engine stream source wiring, config template, and tests. |
| Major Architecture Phase B2b1 | Complete | Implemented runtime reconnect/heartbeat policy, event-loop health counters, config validation, and tests. |
| Major Architecture Phase B2b2 | Complete | Implemented guarded live dry-run decision previews through feature, strategy, risk, order-request, and live safety validation without broker submission. |
| Major Architecture Phase C1 | Complete | Implemented normalized broker events, polling fallback event conversion, idempotent execution lifecycle updates, and paper-engine broker polling sync. |
| Major Architecture Phase C2 | Complete | Implemented mockable Alpaca/IBKR broker push adapter boundaries that normalize vendor-shaped order/fill updates into `BrokerEvent`. |
| Major Architecture Phase C3 | Complete | Implemented checkpointed broker-event sync loops, paper/live reconciliation hooks, gap/out-of-order handling, and lifecycle double-count protection. |
| Major Architecture Phase D1 | Complete | Implemented manual live order submission through explicit non-dry-run, confirmation, submission, safety, account, and reconciliation gates. |
| Major Architecture Phase D2 | Complete | Implemented Alpaca live adapter construction behind D1 gates and fail-closed unsafe live adapter tests. |
| Major Architecture Phase D3 | Complete | Implemented optional automated submission of safety-approved live previews through D1 gates with kill-switch and fail-stop behavior. |
| Major Architecture Phase E | Complete | Implemented optional dependency-free SVG equity and drawdown chart artifacts for backtest reports. |
| Major Architecture Phase F1 | Complete | Implemented ML model manifest artifacts, deterministic feature-schema hashes, and registry/inference contract validation. |
| Major Architecture Phase F2 | Complete | Implemented ML approval metadata, manifest stage transitions, and opt-in runtime stage loading policy. |
| Major Architecture Phase F3 | Complete | Implemented runtime ML manifest metadata propagation, health diagnostics, and report-summary hooks. |
| Final system design and implementation review | Complete | Reviewed actual implementation against system design, interfaces, data models, and ADRs; fixed protocol import boundaries, shared session-service use in risk checks, runtime data-portal feature filtering, and stale state/model documentation. |
| Shared runtime decision pipeline refactor | Complete | Added `RuntimeDecisionPipeline` and integrated backtest, paper, and guarded live preview paths through the shared feature, strategy, and risk decision sequence while preserving engine-owned fills, broker sync, order submission, and live safety gates. |
| Brokerage factory refactor | Complete | Added `qts.brokers.factory` and moved backtest, paper, and live broker adapter construction out of engines while preserving connection lifecycle, simulation models, broker sync, and live safety gates. |
| Shared runtime data portal refactor | Complete | Added `InMemoryRuntimeDataPortal` and moved paper/live runtime bar, quote, lookback, feature-frame, and retention behavior out of private engine portal classes. |
| Package workflows and thin scripts refactor | Complete | Added `qts.workflows` modules for backtest, reporting, paper, live, data download, and ML training workflows; scripts now delegate to those package functions. |

## 3. Pending Phases

| Phase | Status |
|---|---|
| None | Complete |

## 4. Implemented Modules

Documentation exists:

- `SYSTEM_DESIGN.md`
- `PHASE_PLAN.md`
- `INTERFACES.md`
- `DATA_MODELS.md`
- `DECISIONS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`

Repository scaffold exists:

- `pyproject.toml`
- `README.md`
- `.env.example`
- `.gitignore`
- `configs/base.yaml`
- `configs/data/alpaca_sip_bars.yaml`
- `configs/backtest.yaml`
- `configs/backtest_fixture.yaml`
- `configs/paper_alpaca.yaml`
- `configs/paper_ibkr.yaml`
- `configs/paper_fake_stream.yaml`
- `configs/paper_alpaca_stream_mock.yaml`
- `configs/live_alpaca.yaml`
- `configs/ml/directional_baseline.yaml`
- `configs/strategies/ml_directional.yaml`
- `configs/strategies/sma_crossover.yaml`
- `configs/strategies/rsi_mean_reversion.yaml`
- `configs/risk/base.yaml`
- `src/qts/`
- `tests/`
- `docs/runbooks.md`
- `docs/user_manual.md`
- `docs/system_handbook.md`
- `data/.gitkeep`
- `artifacts/.gitkeep`

Domain layer implemented:

- `src/qts/domain/enums.py`
- `src/qts/domain/models.py`
- `src/qts/domain/__init__.py`

Core infrastructure implemented:

- `src/qts/calendar/`
- `src/qts/core/config.py`
- `src/qts/core/clocks.py`
- `src/qts/core/exceptions.py`
- `src/qts/core/logging_config.py`
- `src/qts/core/__init__.py`
- `src/qts/cli.py`

Market data layer implemented:

- `src/qts/market_data/interfaces.py`
- `src/qts/market_data/alpaca.py`
- `src/qts/market_data/normalization.py`
- `src/qts/market_data/providers.py`
- `src/qts/market_data/portal.py`
- `src/qts/market_data/streaming.py`
- `src/qts/market_data/__init__.py`

Feature layer implemented:

- `src/qts/features/indicators.py`
- `src/qts/features/pipeline.py`
- `src/qts/features/__init__.py`

Strategy layer implemented:

- `src/qts/strategies/base.py`
- `src/qts/strategies/rule_based.py`
- `src/qts/strategies/ml_strategy.py`
- `src/qts/strategies/__init__.py`

Risk layer implemented:

- `src/qts/risk/types.py`
- `src/qts/risk/sizing.py`
- `src/qts/risk/rules.py`
- `src/qts/risk/engine.py`
- `src/qts/risk/__init__.py`

Execution layer implemented:

- `src/qts/execution/events.py`
- `src/qts/execution/orders.py`
- `src/qts/execution/manager.py`
- `src/qts/execution/fills.py`
- `src/qts/execution/router.py`
- `src/qts/execution/engine.py`
- `src/qts/execution/__init__.py`

Brokerage layer implemented:

- `src/qts/brokers/interfaces.py`
- `src/qts/brokers/factory.py`
- `src/qts/brokers/__init__.py`
- `src/qts/brokers/backtest/brokerage.py`
- `src/qts/brokers/backtest/__init__.py`
- `src/qts/brokers/alpaca/brokerage.py`
- `src/qts/brokers/alpaca/__init__.py`
- `src/qts/brokers/ibkr/brokerage.py`
- `src/qts/brokers/ibkr/__init__.py`

Integration layer implemented:

- `src/qts/integrations/alpaca/client.py`
- `src/qts/integrations/alpaca/events.py`
- `src/qts/integrations/alpaca/mapping.py`
- `src/qts/integrations/alpaca/mock.py`
- `src/qts/integrations/alpaca/__init__.py`
- `src/qts/integrations/ibkr/client.py`
- `src/qts/integrations/ibkr/events.py`
- `src/qts/integrations/ibkr/mapping.py`
- `src/qts/integrations/ibkr/mock.py`
- `src/qts/integrations/ibkr/__init__.py`

Portfolio layer implemented:

- `src/qts/portfolio/accounting.py`
- `src/qts/portfolio/__init__.py`

Runtime engines implemented:

- `src/qts/engines/backtest_engine.py`
- `src/qts/engines/event_loop.py`
- `src/qts/engines/market_data.py`
- `src/qts/engines/paper_trading_engine.py`
- `src/qts/engines/live_engine.py`
- `src/qts/engines/__init__.py`

Reporting layer implemented:

- `src/qts/reporting/charts.py`
- `src/qts/reporting/metrics.py`
- `src/qts/reporting/reporter.py`
- `src/qts/reporting/__init__.py`

ML workflow layer implemented:

- `src/qts/ml/types.py`
- `src/qts/ml/labels.py`
- `src/qts/ml/dataset.py`
- `src/qts/ml/splits.py`
- `src/qts/ml/leakage.py`
- `src/qts/ml/models.py`
- `src/qts/ml/registry.py`
- `src/qts/ml/inference.py`
- `src/qts/ml/training.py`
- `src/qts/ml/__init__.py`

Monitoring and live-readiness layer implemented:

- `src/qts/monitoring/types.py`
- `src/qts/monitoring/health.py`
- `src/qts/monitoring/metrics.py`
- `src/qts/monitoring/alerts.py`
- `src/qts/monitoring/safety.py`
- `src/qts/monitoring/reconciliation.py`
- `src/qts/monitoring/recovery.py`
- `src/qts/monitoring/__init__.py`

Workflow layer implemented:

- `src/qts/workflows/backtest.py`
- `src/qts/workflows/download_data.py`
- `src/qts/workflows/live_trading.py`
- `src/qts/workflows/paper_trading.py`
- `src/qts/workflows/reporting.py`
- `src/qts/workflows/training.py`
- `src/qts/workflows/__init__.py`

Scripts implemented:

- `scripts/run_backtest.py`
- `scripts/download_data.py`
- `scripts/generate_report.py`
- `scripts/run_paper_trading.py`
- `scripts/train_model.py`
- `scripts/run_live_trading.py`

Tests and fixtures implemented:

- `tests/test_scaffold.py`
- `tests/unit/domain/`
- `tests/unit/calendar/`
- `tests/unit/core/`
- `tests/unit/market_data/`
- `tests/unit/features/`
- `tests/unit/strategies/`
- `tests/unit/risk/`
- `tests/unit/execution/`
- `tests/unit/engines/`
- `tests/unit/brokers/test_factory.py`
- `tests/unit/brokers/backtest/`
- `tests/unit/brokers/alpaca/`
- `tests/unit/brokers/ibkr/`
- `tests/unit/integrations/alpaca/`
- `tests/unit/integrations/ibkr/`
- `tests/unit/portfolio/`
- `tests/unit/reporting/`
- `tests/unit/ml/`
- `tests/unit/monitoring/`
- `tests/unit/workflows/`
- `tests/integration/backtest/`
- `tests/integration/alpaca/`
- `tests/integration/ibkr/`
- `tests/integration/ml/`
- `tests/integration/live_safety/`
- `tests/fixtures/market_data/`
- `tests/fixtures/market_data/backtest_sma_cross.csv`
- `tests/fixtures/market_data/ml_directional.csv`

Placeholder package modules still exist for later phases:

- `src/qts/integrations/`
- `src/qts/integrations/futu/`
- `src/qts/integrations/polygon/`
- `src/qts/research/`
- `src/qts/utils/`

These placeholder modules intentionally contain no research, Futu, or Polygon
vendor business logic yet.

## 5. Missing Modules and Functional Work

Future functionality outside the current phase plan remains missing:

- research workflows,
- production deployment automation,
- real vendor live market-data stream ownership,
- persistent broker-event checkpoint storage,
- production dashboarding and notification integrations.

## 6. Known Issues

- The current foundation has a deterministic bar-driven backtest path and
  mockable Alpaca and IBKR paper initialization/event-handling paths, plus a
  finite fake-stream paper event loop and mock Alpaca stream adapter path for
  deterministic local testing.
- `PaperTradingEngine` does not yet own a vendor-backed continuous live
  market-data stream; it handles externally supplied `Bar`/`Quote` events,
  finite fake streams, mock Alpaca stream payloads, and dry-run initialization.
- The runtime event loop has deterministic reconnect and heartbeat/data-gap
  policies, but no real websocket transport or sleeping backoff implementation.
- Live Alpaca market data provider support is not implemented. Phase 10 adds
  historical SIP downloads only; live scaffolds still validate
  `market_data.provider: external_events`, while paper also supports
  `fake_stream` and `alpaca_stream` for finite local runs.
- Alpaca and IBKR order/fill synchronization currently uses normalized broker
  events built from polling and filled-quantity deltas. Mockable vendor
  push-event adapter boundaries and checkpointed engine sync are implemented,
  but real broker stream transports and persistent checkpoint storage remain
  future operational-readiness work.
- IBKR paper order submission requires `broker.account_id` and
  `broker.safety.symbol_conids`; automatic IBKR order reply confirmation is not
  enabled and reply prompts fail closed.
- Live readiness now includes dry-run initialization, safety validation, a
  manual `submit_live_order(...)` path gated by `enable_order_submission`,
  Alpaca live brokerage construction behind the same D1 gates, and optional
  automated submission of safety-approved live previews behind
  `enable_automated_submission` plus `automated_submission_kill_switch`.
- The Phase 7 ML model is a dependency-free directional baseline intended to
  validate workflow boundaries. Advanced model libraries, feature stores,
  online learning, optimization, and production model monitoring remain future
  work.
- Optional static SVG plot generation is implemented for backtest equity and
  drawdown diagnostics; interactive dashboarding remains future work.
- `pytest` is listed as an optional test dependency and is available in the
  current local virtual environment; the test suite also runs with
  standard-library `unittest`.
- Config loading supports PyYAML if installed and otherwise uses an internal
  parser for the repository's simple YAML templates. This parser is intentionally
  limited.
- Parquet loading is implemented through optional pandas or pyarrow dependencies.
  CSV fixtures remain the guaranteed no-dependency test path.
- Live trading is intentionally deferred and must remain guarded.
- First implementation target is minute-level bars.
- Second-level data support should be preserved architecturally but not overbuilt early.
- Alpaca is the first real broker target and now has a paper adapter.
- Alpaca is the first enabled live broker adapter target, but only for
  non-dry-run configurations that pass explicit confirmation and submission
  gates. Automated strategy-to-order live submission is available only for
  safety-approved live previews when its separate gate is enabled and the kill
  switch is open.
- IBKR is the second broker target and now has a paper adapter foundation.
- Alpaca SIP is the first remote historical data download target and writes
  normalized CSV or Parquet for the existing local provider/backtest path. The
  sample config now writes a partitioned dataset by timeframe, symbol, and date
  so multi-symbol downloads do not accumulate in one large file. Intraday rows
  are locally filtered to regular US equity session start times after requesting
  the full configured Alpaca interval.
- Local Parquet is the first historical data source.
- Backtest brokerage must not own historical data loading.
- Buying-power checks use `PortfolioSnapshot.metadata["buying_power"]` when
  present and otherwise fall back to cash.

## 7. Next Recommended Task

No implementation phase is currently pending.

The next AI coding agent should start from a new documented requirement or
phase proposal, then read the source-of-truth documents before editing. Preserve
the live-safety guardrails unless a future phase explicitly changes them and
documents the reason.

## 8. Rules for Future AI Coding Agent Sessions

Every new session must:

- inspect the existing repository before editing,
- continue from the next unfinished task,
- not restart the project from scratch,
- keep phase boundaries clear,
- avoid implementing future-phase functionality unless required for current-phase testability,
- prefer minimal complete functionality over broad incomplete implementation,
- write tests for the phase being implemented,
- update documentation after each phase.

## 9. Required Updates After Every Phase

At the end of each phase, update:

- `PROJECT_STATE.md`
  - current phase,
  - completed phases,
  - implemented modules,
  - missing modules,
  - known issues,
  - next recommended task.
- `CHANGELOG.md`
  - added,
  - changed,
  - fixed,
  - removed,
  - notes.

Also update when relevant:

- `DECISIONS.md` for new architectural decisions.
- `INTERFACES.md` for public interface changes.
- `DATA_MODELS.md` for stable model changes.
- `PHASE_PLAN.md` if phase scope changes.
