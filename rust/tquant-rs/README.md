# tquant-rs

Production-ready Rust/PyO3 acceleration crate for CPU-bound finance math.

It remains optional at runtime, but the Python reference path and the Rust
extension are both validated through parity and benchmark evidence.

Initial functions:

- `max_drawdown`
- `rolling_mean`
- `atr_wilder`

Production acceptance requirements:

- Compare against Python reference with absolute error below `1e-8`.
- Keep Python fallback available.
- Keep the feature flag gate for controlled rollout.
- Record benchmark evidence in `docs/reports/go-rust-performance-acceptance-2026-05-25.json`.
