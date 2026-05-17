# Benchmarking

Benchmark history is stored in SQLite table `benchmark_runs`.

The schema tracks node identity, image and commit metadata, sync run timestamps, sync durations, validation phase durations, final height, peer count, resource maxima, result and error message.

The controller starts a benchmark row when a worker node starts or resets. It completes the row when the node is API-up, has peers, and its current block height is close to the gateway height. It then stores total duration, final height and observed resource maxima.
Because Grin can report `no_sync` before the node is fully caught up, benchmark completion is based on worker height near the gateway height rather than treating `no_sync` as complete.

Completion default:

- Worker height must be within `RUNTIME_SYNC_COMPLETE_LAG=2` blocks of `grin-gw`.

Failed benchmark completion is also guarded against startup transients. API/container/peer failures must be confirmed across `RUNTIME_BENCHMARK_FAILURE_OBSERVATIONS=3` recent observations before a running benchmark is marked failed.

Phase durations are derived from observed sync-state transitions where the node exposes them:

- `header_sync_duration` from `header_sync`
- `PIHD_duration` from `txhashset_download`
- `PIBD_duration` from `txhashset_pibd`
- `rangeproof_validation_duration` from `txhashset_rangeproofs_validation`
- `kernel_validation_duration` from `txhashset_kernels_validation`

`GET /api/benchmarks` returns recent benchmark rows.

Grafana provisions `Grin Benchmark History` for the same data.
