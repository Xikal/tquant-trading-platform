pub fn max_drawdown_values(equity: &[f64]) -> f64 {
    if equity.is_empty() {
        return 0.0;
    }
    let mut peak = equity[0];
    let mut max_dd = 0.0_f64;
    for value in equity {
        if *value > peak {
            peak = *value;
        }
        if peak > 0.0 {
            let dd = (peak - *value) / peak;
            if dd > max_dd {
                max_dd = dd;
            }
        }
    }
    max_dd
}

pub fn rolling_mean_values(values: &[f64], window: usize) -> Vec<Option<f64>> {
    if window == 0 {
        return vec![None; values.len()];
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
    result
}

pub fn rolling_std_values(values: &[f64], window: usize) -> Vec<Option<f64>> {
    if window == 0 {
        return vec![None; values.len()];
    }
    let mut result = Vec::with_capacity(values.len());
    let mut sum = 0.0_f64;
    let mut sum_sq = 0.0_f64;
    for idx in 0..values.len() {
        let value = values[idx];
        sum += value;
        sum_sq += value * value;
        if idx >= window {
            let old = values[idx - window];
            sum -= old;
            sum_sq -= old * old;
        }
        if idx + 1 >= window {
            result.push(Some(sample_std_from_sums(sum, sum_sq, window)));
        } else {
            result.push(None);
        }
    }
    result
}

pub fn volatility_value(returns: &[f64], periods_per_year: f64) -> Option<f64> {
    if returns.len() < 2 {
        return None;
    }
    let std = sample_std(returns)?;
    Some(std * periods_per_year.max(1.0).sqrt())
}

pub fn correlation_value(left: &[f64], right: &[f64]) -> Option<f64> {
    pearson(left, right)
}

pub fn beta_value(asset_returns: &[f64], benchmark_returns: &[f64]) -> Option<f64> {
    let len = asset_returns.len().min(benchmark_returns.len());
    if len < 2 {
        return None;
    }
    let asset = &asset_returns[..len];
    let benchmark = &benchmark_returns[..len];
    let asset_mean = asset.iter().sum::<f64>() / len as f64;
    let benchmark_mean = benchmark.iter().sum::<f64>() / len as f64;
    let mut covariance = 0.0_f64;
    let mut benchmark_var = 0.0_f64;
    for idx in 0..len {
        let a = asset[idx] - asset_mean;
        let b = benchmark[idx] - benchmark_mean;
        covariance += a * b;
        benchmark_var += b * b;
    }
    if benchmark_var <= 0.0 {
        return None;
    }
    Some(covariance / benchmark_var)
}

pub fn bollinger_bands_values(
    values: &[f64],
    window: usize,
    num_std: f64,
) -> Vec<Option<(f64, f64, f64)>> {
    if window == 0 {
        return vec![None; values.len()];
    }
    let means = rolling_mean_values(values, window);
    let stds = rolling_std_values(values, window);
    means
        .into_iter()
        .zip(stds)
        .map(|(mean, std)| match (mean, std) {
            (Some(middle), Some(std_value)) => {
                let upper = middle + num_std * std_value;
                let lower = middle - num_std * std_value;
                Some((upper, middle, lower))
            }
            _ => None,
        })
        .collect()
}

pub fn atr_wilder_values(
    highs: &[f64],
    lows: &[f64],
    closes: &[f64],
    period: usize,
) -> Vec<Option<f64>> {
    let len = highs.len().min(lows.len()).min(closes.len());
    if period == 0 || len < period + 1 {
        return vec![None; len];
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
    result
}

pub fn rsi_wilder_value(values: &[f64], period: usize) -> Option<f64> {
    if period == 0 || values.len() <= period {
        return None;
    }
    let mut gains = 0.0_f64;
    let mut losses = 0.0_f64;
    for idx in 1..=period {
        let delta = values[idx] - values[idx - 1];
        if delta >= 0.0 {
            gains += delta;
        } else {
            losses += -delta;
        }
    }
    let mut avg_gain = gains / period as f64;
    let mut avg_loss = losses / period as f64;
    for idx in period + 1..values.len() {
        let delta = values[idx] - values[idx - 1];
        let gain = if delta > 0.0 { delta } else { 0.0 };
        let loss = if delta < 0.0 { -delta } else { 0.0 };
        avg_gain = (avg_gain * (period as f64 - 1.0) + gain) / period as f64;
        avg_loss = (avg_loss * (period as f64 - 1.0) + loss) / period as f64;
    }
    if avg_loss == 0.0 {
        return Some(if avg_gain > 0.0 { 100.0 } else { 50.0 });
    }
    let rs = avg_gain / avg_loss;
    Some(100.0 - 100.0 / (1.0 + rs))
}

pub fn vwap_value(prices: &[f64], volumes: &[f64]) -> Option<f64> {
    let len = prices.len().min(volumes.len());
    if len == 0 {
        return None;
    }
    let mut turnover = 0.0_f64;
    let mut total_volume = 0.0_f64;
    for idx in 0..len {
        let volume = volumes[idx].max(0.0);
        turnover += prices[idx] * volume;
        total_volume += volume;
    }
    if total_volume <= 0.0 {
        return None;
    }
    Some(turnover / total_volume)
}

pub fn rank_ic_value(factor: &[f64], returns: &[f64]) -> Option<f64> {
    let len = factor.len().min(returns.len());
    if len < 2 {
        return None;
    }
    let factor_ranks = ranks(&factor[..len]);
    let return_ranks = ranks(&returns[..len]);
    pearson(&factor_ranks, &return_ranks)
}

fn ranks(values: &[f64]) -> Vec<f64> {
    let mut pairs: Vec<(usize, f64)> = values.iter().copied().enumerate().collect();
    pairs.sort_by(|left, right| {
        left.1
            .partial_cmp(&right.1)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut result = vec![0.0; values.len()];
    let mut idx = 0;
    while idx < pairs.len() {
        let start = idx;
        let value = pairs[idx].1;
        while idx < pairs.len() && pairs[idx].1 == value {
            idx += 1;
        }
        let rank = (start + 1 + idx) as f64 / 2.0;
        for pair in &pairs[start..idx] {
            result[pair.0] = rank;
        }
    }
    result
}

fn pearson(left: &[f64], right: &[f64]) -> Option<f64> {
    let len = left.len().min(right.len());
    if len < 2 {
        return None;
    }
    let left_mean = left[..len].iter().sum::<f64>() / len as f64;
    let right_mean = right[..len].iter().sum::<f64>() / len as f64;
    let mut covariance = 0.0_f64;
    let mut left_var = 0.0_f64;
    let mut right_var = 0.0_f64;
    for idx in 0..len {
        let l = left[idx] - left_mean;
        let r = right[idx] - right_mean;
        covariance += l * r;
        left_var += l * l;
        right_var += r * r;
    }
    if left_var <= 0.0 || right_var <= 0.0 {
        return None;
    }
    Some(covariance / (left_var.sqrt() * right_var.sqrt()))
}

fn sample_std(values: &[f64]) -> Option<f64> {
    if values.len() < 2 {
        return None;
    }
    let sum = values.iter().sum::<f64>();
    let sum_sq = values.iter().map(|value| value * value).sum::<f64>();
    Some(sample_std_from_sums(sum, sum_sq, values.len()))
}

fn sample_std_from_sums(sum: f64, sum_sq: f64, len: usize) -> f64 {
    if len < 2 {
        return 0.0;
    }
    let n = len as f64;
    let variance = ((sum_sq - (sum * sum / n)) / (n - 1.0)).max(0.0);
    variance.sqrt()
}
