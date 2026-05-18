# Benchmarking

Benchmark history is stored in SQLite table `benchmark_runs`.

The schema tracks node identity, image and commit metadata, sync run timestamps, sync durations, validation phase durations, final height, peer count, resource maxima, result and error message.

The controller starts a benchmark row when a worker node starts or resets. It completes the row when the node is API-up, has peers, and its local block height is close to the gateway block height. It then stores total duration, final height and observed resource maxima.
Because Grin can expose `tip.height` near the network height before local block sync/validation is actually complete, benchmark completion uses `sync_info.current_height` as the local block height. `tip.height` is only a fallback when `sync_info.current_height` is not exposed.

Completion default:

- The latest `RUNTIME_SYNC_COMPLETE_OBSERVATIONS=3` worker observations for the same `sync_run_id` must be within `RUNTIME_SYNC_COMPLETE_LAG=2` blocks of `grin-gw`.
- `validate_chain` must succeed via the node owner API. This prevents a run from finishing when the API height is near the gateway but local chain validation is still incomplete.

Failed benchmark completion is also guarded against startup transients. A running benchmark is not marked failed during `RUNTIME_BENCHMARK_FAILURE_GRACE_SECONDS=180` after start. After that grace period, API/container/peer failures must be confirmed across `RUNTIME_BENCHMARK_FAILURE_OBSERVATIONS=3` recent observations for the same `sync_run_id` before the benchmark closes as failed. Peerless completion is suppressed while active sync states or disk/network activity are observed. Stuck detection uses `RUNTIME_STUCK_FAILURE_OBSERVATIONS=12` current-run observations and only fires when height/header are unchanged, peers exist, no active sync phase is reported, and disk/network counters do not move. Resource-limit states are exposed as failures for alerting but do not close benchmark runs as failed.

Dynamic Rust worker profiles use `chain_validation_mode = "Disabled"` by default. This avoids running a full-chain validation pass after every accepted block, which can dominate CPU and delay block catch-up during runtime sync tests. Normal block and consensus validation still happens in the Grin node pipeline.

Use the `validated` profile when a test explicitly needs `chain_validation_mode = "EveryBlock"`.

Phase durations are derived from observed sync-state transitions where the node exposes them:

- `header_sync_duration` from `header_sync`
- `PIHD_duration` from `txhashset_download`
- `PIBD_duration` from `txhashset_pibd`
- `rangeproof_validation_duration` from `txhashset_rangeproofs_validation`
- `kernel_validation_duration` from `txhashset_kernels_validation`

`GET /api/benchmarks` returns recent benchmark rows.

Grafana provisions `Grin Benchmark History` for the same data.
