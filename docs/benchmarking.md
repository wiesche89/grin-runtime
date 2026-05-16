# Benchmarking

Benchmark history is stored in SQLite table `benchmark_runs`.

The schema tracks node identity, image and commit metadata, sync run timestamps, sync durations, validation phase durations, final height, peer count, resource maxima, result and error message.

The controller starts a benchmark row when a worker node starts or resets. It completes the row when the node reports a full sync state, storing total duration, final height and observed resource maxima.

`GET /api/benchmarks` returns recent benchmark rows.
