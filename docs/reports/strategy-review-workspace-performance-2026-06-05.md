# 策略跟踪复盘中心性能验收

## Backend API Budget
| Metric | Target | Result | Pass |
|---|---:|---:|---|
| review-workspace warm p95 | <250ms target / <500ms hard | 约 0.98ms（样本 2-8 最大 1.053ms wall） | Pass |
| review_pool source p95 | <120ms target / <250ms hard | 约 0.69ms warm | Pass |
| trade_journal source p95 | <80ms target / <150ms hard | 约 0.09ms warm | Pass |
| relative_strength source p95 | <120ms target / <250ms hard | 约 0.19ms warm | Pass |
| payload size | <120KB target / <250KB hard | 约 2.2KB | Pass |

## Frontend Budget
| Metric | Target | Result | Pass |
|---|---:|---:|---|
| duplicate active-tab queries | 0 | 聚合接口路径测试覆盖，不再并行调用 review-pool / trade-journal / relative-strength | Pass |
| review workspace bundle gzip delta | <15KB target / <30KB hard | 独立 lazy chunk 约 4.18KB gzip | Pass |
| desktop layout overlap | 0 | CSS grid 固定列与 min-width:0；targeted render/build 通过 | Pass |
| mobile layout overlap | 0 | <640px 单列布局；targeted render/build 通过 | Pass |

## Source Timings Evidence
本地 `http://127.0.0.1:8000/api/...` 当前返回前端 HTML fallback，未作为 API JSON 证据采信。以下为后端服务测试客户端样本，使用 SQLite 内存库、开启 `trading_experience_suite_enabled` / `trade_review_suite_enabled` / `relative_strength_board_enabled`，种子样本 1 只 `review_pool` 股票：

```text
sample=1 wall_ms=9.678 elapsed_ms=3.740 size_bytes=2195 review_pool=2.838 trade_journal=0.540 relative_strength=0.331 cache=fresh
sample=2 wall_ms=1.053 elapsed_ms=0.978 size_bytes=2197 review_pool=0.687 trade_journal=0.087 relative_strength=0.188 cache=fresh
sample=3 wall_ms=0.944 elapsed_ms=0.889 size_bytes=2196 review_pool=0.608 trade_journal=0.080 relative_strength=0.187 cache=fresh
sample=4 wall_ms=0.927 elapsed_ms=0.873 size_bytes=2195 review_pool=0.599 trade_journal=0.080 relative_strength=0.180 cache=fresh
sample=5 wall_ms=0.935 elapsed_ms=0.881 size_bytes=2196 review_pool=0.605 trade_journal=0.080 relative_strength=0.183 cache=fresh
sample=6 wall_ms=0.936 elapsed_ms=0.880 size_bytes=2196 review_pool=0.604 trade_journal=0.082 relative_strength=0.182 cache=fresh
sample=7 wall_ms=0.931 elapsed_ms=0.878 size_bytes=2197 review_pool=0.601 trade_journal=0.082 relative_strength=0.182 cache=fresh
sample=8 wall_ms=0.929 elapsed_ms=0.876 size_bytes=2197 review_pool=0.599 trade_journal=0.081 relative_strength=0.183 cache=fresh
```

## Conclusion
Backend API hard limits pass in local test-client samples. `npm run analyze` passed with `first_screen_js_gzip_kb=318KB`, `total_gzip_kb=818.06KB`, and review workspace lazy chunk `StrategyReviewWorkspacePanel-*.js` about `4.18KB gzip`.
