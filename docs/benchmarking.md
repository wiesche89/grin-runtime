# Benchmarking

Benchmark history is stored in SQLite table `benchmark_runs`.

The schema tracks node identity, image and commit metadata, sync run timestamps, sync durations, validation phase durations, final height, peer count, resource maxima, result and error message.

The controller starts a benchmark row when a worker node starts or resets. It completes the row when the node is API-up, has peers, and its local block height is close to the gateway block height. It then stores total duration, final height and observed resource maxima.
Because Grin can expose `tip.height` near the network height before local block sync/validation is actually complete, benchmark completion uses `sync_info.current_height` as the local block height. `tip.height` is only a fallback when `sync_info.current_height` is not exposed.

Completion default:

- Worker height must be within `RUNTIME_SYNC_COMPLETE_LAG=2` blocks of `grin-gw`.
- `validate_chain` must succeed via the node owner API. This prevents a run from finishing when the API height is near the gateway but local chain validation is still incomplete.

Failed benchmark completion is also guarded against startup transients. API/container/peer failures must be confirmed across `RUNTIME_BENCHMARK_FAILURE_OBSERVATIONS=3` recent observations before a running benchmark is marked failed.

Dynamic Rust worker profiles use `chain_validation_mode = "EveryBlock"` so benchmark nodes perform normal block validation. The static gateway profile remains lightweight with validation disabled.

Phase durations are derived from observed sync-state transitions where the node exposes them:

- `header_sync_duration` from `header_sync`
- `PIHD_duration` from `txhashset_download`
- `PIBD_duration` from `txhashset_pibd`
- `rangeproof_validation_duration` from `txhashset_rangeproofs_validation`
- `kernel_validation_duration` from `txhashset_kernels_validation`

`GET /api/benchmarks` returns recent benchmark rows.

Grafana provisions `Grin Benchmark History` for the same data.
