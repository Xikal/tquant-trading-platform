use pyo3::prelude::*;

mod finance_core;

pub use finance_core::{
    atr_wilder_values, beta_value, bollinger_bands_values, correlation_value, max_drawdown_values,
    rank_ic_value, rolling_mean_values, rolling_std_values, rsi_wilder_value, volatility_value,
    vwap_value,
};

#[pyfunction]
fn max_drawdown(equity: Vec<f64>) -> PyResult<f64> {
    Ok(max_drawdown_values(&equity))
}

#[pyfunction]
fn rolling_mean(values: Vec<f64>, window: usize) -> PyResult<Vec<Option<f64>>> {
    Ok(rolling_mean_values(&values, window))
}

#[pyfunction]
fn rolling_std(values: Vec<f64>, window: usize) -> PyResult<Vec<Option<f64>>> {
    Ok(rolling_std_values(&values, window))
}

#[pyfunction]
fn volatility(returns: Vec<f64>, periods_per_year: f64) -> PyResult<Option<f64>> {
    Ok(volatility_value(&returns, periods_per_year))
}

#[pyfunction]
fn correlation(left: Vec<f64>, right: Vec<f64>) -> PyResult<Option<f64>> {
    Ok(correlation_value(&left, &right))
}

#[pyfunction]
fn beta(asset_returns: Vec<f64>, benchmark_returns: Vec<f64>) -> PyResult<Option<f64>> {
    Ok(beta_value(&asset_returns, &benchmark_returns))
}

#[pyfunction]
fn bollinger_bands(
    values: Vec<f64>,
    window: usize,
    num_std: f64,
) -> PyResult<Vec<Option<(f64, f64, f64)>>> {
    Ok(bollinger_bands_values(&values, window, num_std))
}

#[pyfunction]
fn atr_wilder(
    highs: Vec<f64>,
    lows: Vec<f64>,
    closes: Vec<f64>,
    period: usize,
) -> PyResult<Vec<Option<f64>>> {
    Ok(atr_wilder_values(&highs, &lows, &closes, period))
}

#[pyfunction]
fn rsi_wilder(values: Vec<f64>, period: usize) -> PyResult<Option<f64>> {
    Ok(rsi_wilder_value(&values, period))
}

#[pyfunction]
fn vwap(prices: Vec<f64>, volumes: Vec<f64>) -> PyResult<Option<f64>> {
    Ok(vwap_value(&prices, &volumes))
}

#[pyfunction]
fn rank_ic(factor: Vec<f64>, returns: Vec<f64>) -> PyResult<Option<f64>> {
    Ok(rank_ic_value(&factor, &returns))
}

#[pymodule]
fn tquant_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(max_drawdown, m)?)?;
    m.add_function(wrap_pyfunction!(rolling_mean, m)?)?;
    m.add_function(wrap_pyfunction!(rolling_std, m)?)?;
    m.add_function(wrap_pyfunction!(volatility, m)?)?;
    m.add_function(wrap_pyfunction!(correlation, m)?)?;
    m.add_function(wrap_pyfunction!(beta, m)?)?;
    m.add_function(wrap_pyfunction!(bollinger_bands, m)?)?;
    m.add_function(wrap_pyfunction!(atr_wilder, m)?)?;
    m.add_function(wrap_pyfunction!(rsi_wilder, m)?)?;
    m.add_function(wrap_pyfunction!(vwap, m)?)?;
    m.add_function(wrap_pyfunction!(rank_ic, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn max_drawdown_uses_time_ordered_peak_to_trough() {
        let value = max_drawdown(vec![100.0, 120.0, 90.0, 130.0]).unwrap();

        assert!((value - 0.25).abs() < 1e-9);
    }

    #[test]
    fn rolling_mean_keeps_warmup_empty() {
        let values = rolling_mean(vec![1.0, 2.0, 3.0, 4.0], 3).unwrap();

        assert_eq!(values, vec![None, None, Some(2.0), Some(3.0)]);
    }

    #[test]
    fn rolling_std_uses_sample_standard_deviation() {
        let values = rolling_std(vec![1.0, 2.0, 3.0, 5.0], 3).unwrap();

        assert!(values[0].is_none());
        assert!(values[1].is_none());
        assert!((values[2].unwrap() - 1.0).abs() < 1e-9);
        assert!((values[3].unwrap() - 1.5275252316519468).abs() < 1e-9);
    }

    #[test]
    fn correlation_and_beta_are_numeric_only() {
        let corr = correlation(vec![0.01, 0.02, -0.01], vec![0.02, 0.04, -0.02])
            .unwrap()
            .unwrap();
        let beta_value = beta(vec![0.01, 0.02, -0.01], vec![0.02, 0.04, -0.02])
            .unwrap()
            .unwrap();

        assert!((corr - 1.0).abs() < 1e-9);
        assert!((beta_value - 0.5).abs() < 1e-9);
    }

    #[test]
    fn bollinger_bands_keep_warmup_empty() {
        let values = bollinger_bands(vec![1.0, 2.0, 3.0], 3, 2.0).unwrap();

        assert!(values[0].is_none());
        assert!(values[1].is_none());
        let (upper, middle, lower) = values[2].unwrap();
        assert!((upper - 4.0).abs() < 1e-9);
        assert!((middle - 2.0).abs() < 1e-9);
        assert!((lower - 0.0).abs() < 1e-9);
    }

    #[test]
    fn atr_wilder_matches_expected_sequence() {
        let highs = vec![10.0, 11.0, 12.0, 13.0, 14.0];
        let lows = vec![9.0, 9.5, 10.0, 11.0, 12.0];
        let closes = vec![9.5, 10.5, 11.0, 12.0, 13.0];
        let values = atr_wilder(highs, lows, closes, 3).unwrap();

        assert!(values[0].is_none());
        assert!(values[1].is_none());
        assert!(values[2].is_none());
        assert!((values[3].unwrap() - 1.8333333333333333).abs() < 1e-9);
        assert!((values[4].unwrap() - 1.8888888888888886).abs() < 1e-9);
    }

    #[test]
    fn rsi_wilder_matches_known_sequence() {
        let values = vec![
            44.0, 44.15, 43.9, 44.35, 44.8, 45.0, 44.7, 44.9, 45.2, 45.5, 45.1, 45.7, 46.0, 46.4,
            46.1, 46.8,
        ];
        let value = rsi_wilder(values, 14).unwrap().unwrap();

        assert!((value - 76.6523).abs() < 0.0002);
    }

    #[test]
    fn rsi_wilder_returns_neutral_for_flat_sequence() {
        let values = vec![10.0; 16];
        let value = rsi_wilder(values, 14).unwrap().unwrap();

        assert!((value - 50.0).abs() < 1e-9);
    }

    #[test]
    fn vwap_weights_by_volume() {
        let value = vwap(vec![10.0, 12.0], vec![100.0, 300.0]).unwrap().unwrap();

        assert!((value - 11.5).abs() < 1e-9);
    }

    #[test]
    fn rank_ic_uses_spearman_correlation() {
        let value = rank_ic(vec![1.0, 2.0, 3.0], vec![3.0, 2.0, 1.0])
            .unwrap()
            .unwrap();

        assert!((value + 1.0).abs() < 1e-9);
    }
}
