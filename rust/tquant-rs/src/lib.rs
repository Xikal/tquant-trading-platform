use pyo3::prelude::*;

#[pyfunction]
fn max_drawdown(equity: Vec<f64>) -> PyResult<f64> {
    if equity.is_empty() {
        return Ok(0.0);
    }
    let mut peak = equity[0];
    let mut max_dd = 0.0_f64;
    for value in equity {
        if value > peak {
            peak = value;
        }
        if peak > 0.0 {
            let dd = (peak - value) / peak;
            if dd > max_dd {
                max_dd = dd;
            }
        }
    }
    Ok(max_dd)
}

#[pyfunction]
fn rolling_mean(values: Vec<f64>, window: usize) -> PyResult<Vec<Option<f64>>> {
    if window == 0 {
        return Ok(vec![None; values.len()]);
    }
    let mut result = Vec::with_capacity(values.len());
    let mut sum = 0.0_f64;
    for idx in 0..values.len() {
        sum += values[idx];
        if idx >= window {
            sum -= values[idx - window];
        }
        if idx + 1 >= window {
            result.push(Some(sum / window as f64));
        } else {
            result.push(None);
        }
    }
    Ok(result)
}

#[pyfunction]
fn atr_wilder(highs: Vec<f64>, lows: Vec<f64>, closes: Vec<f64>, period: usize) -> PyResult<Vec<Option<f64>>> {
    let len = highs.len().min(lows.len()).min(closes.len());
    if period == 0 || len < period + 1 {
        return Ok(vec![None; len]);
    }
    let mut true_ranges = Vec::with_capacity(len - 1);
    for idx in 1..len {
        let high_low = highs[idx] - lows[idx];
        let high_close = (highs[idx] - closes[idx - 1]).abs();
        let low_close = (lows[idx] - closes[idx - 1]).abs();
        true_ranges.push(high_low.max(high_close).max(low_close));
    }
    let mut result = vec![None; len];
    let mut atr = true_ranges[..period].iter().sum::<f64>() / period as f64;
    result[period] = Some(atr);
    for idx in period..true_ranges.len() {
        atr = (atr * (period as f64 - 1.0) + true_ranges[idx]) / period as f64;
        result[idx + 1] = Some(atr);
    }
    Ok(result)
}

#[pymodule]
fn tquant_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(max_drawdown, m)?)?;
    m.add_function(wrap_pyfunction!(rolling_mean, m)?)?;
    m.add_function(wrap_pyfunction!(atr_wilder, m)?)?;
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
}
