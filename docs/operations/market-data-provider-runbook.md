# Market Data Provider Runbook

## 目标

市场数据 provider 必须显式返回质量状态，避免把缺失、估算、过期数据误当成强实时信号。

质量状态：

- `fresh`：实时或足够新的可用数据。
- `stale`：可用但可能过期的数据。
- `estimated`：估算或跨市场 fallback 数据，只能辅助展示。
- `unavailable`：不可用，不能参与强信号。

## 默认行为

`market_provider_router_enabled=false` 时，系统保持原行情链路：

```text
Tencent -> Eastmoney -> trends/minute/spot -> Sina fallback
```

## 灰度开启

在系统配置或 DB feature flag 中开启：

```text
market_provider_router_enabled=true
```

开启后 `get_quote()` 会先尝试统一 provider router：

```text
Eastmoney -> AkShare -> OpenBB(estimated)
```

如所有 provider 不可用，会自动回到原行情链路。

## 验收命令

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_market_provider_contract.py \
  backend/tests/test_market_provider_flag.py \
  backend/tests/test_market_data_quality_fields.py -q
```

## 回滚

关闭 feature flag 即可：

```text
market_provider_router_enabled=false
```

不需要改代码或迁移数据库。
