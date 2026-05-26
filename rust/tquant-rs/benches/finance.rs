use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

#[path = "../src/finance_core.rs"]
mod finance_core;

use finance_core::{
    atr_wilder_values, max_drawdown_values, rank_ic_value, rolling_mean_values, rsi_wilder_value,
    vwap_value,
};

fn series(len: usize) -> Vec<f64> {
    (0..len)
        .map(|idx| 100.0 + (idx as f64 * 0.017).sin() * 8.0 + idx as f64 * 0.0003)
        .collect()
}

fn highs(values: &[f64]) -> Vec<f64> {
    values
        .iter()
        .enumerate()
        .map(|(idx, value)| value + 0.8 + (idx % 5) as f64 * 0.04)
        .collect()
}

fn lows(values: &[f64]) -> Vec<f64> {
    values
        .iter()
        .enumerate()
        .map(|(idx, value)| value - 0.8 - (idx % 3) as f64 * 0.03)
        .collect()
}

fn volumes(len: usize) -> Vec<f64> {
    (0..len)
        .map(|idx| 10_000.0 + (idx % 97) as f64 * 120.0)
        .collect()
}

fn bench_finance(c: &mut Criterion) {
    let len = 20_000;
    let values = series(len);
    let highs = highs(&values);
    let lows = lows(&values);
    let volumes = volumes(len);
    let returns = series(len).into_iter().rev().collect::<Vec<_>>();
    let mut group = c.benchmark_group("finance");
    group.throughput(Throughput::Elements(len as u64));
    group.bench_with_input(
        BenchmarkId::new("max_drawdown", len),
        &values,
        |b, values| b.iter(|| max_drawdown_values(black_box(values))),
    );
    group.bench_with_input(
        BenchmarkId::new("rolling_mean_20", len),
        &values,
        |b, values| b.iter(|| rolling_mean_values(black_box(values), 20)),
    );
    group.bench_with_input(
        BenchmarkId::new("atr_wilder_14", len),
        &values,
        |b, values| {
            b.iter(|| atr_wilder_values(black_box(&highs), black_box(&lows), black_box(values), 14))
        },
    );
    group.bench_with_input(
        BenchmarkId::new("rsi_wilder_14", len),
        &values,
        |b, values| b.iter(|| rsi_wilder_value(black_box(values), 14)),
    );
    group.bench_with_input(BenchmarkId::new("vwap", len), &values, |b, values| {
        b.iter(|| vwap_value(black_box(values), black_box(&volumes)))
    });
    group.bench_with_input(BenchmarkId::new("rank_ic", len), &values, |b, values| {
        b.iter(|| rank_ic_value(black_box(values), black_box(&returns)))
    });
    group.finish();
}

criterion_group!(benches, bench_finance);
criterion_main!(benches);
