# 智能增量缓存更新

## Problem Statement

**How Might We:** 让缓存机制更智能，只获取缺失的最新数据而不是每次都重新下载全部，以解决 API 限流问题并确保数据新鲜度？

## Recommended Direction

采用**简单增量 + 元数据**组合方案：

- 保持当前 CSV 数据文件格式完全不变（向后兼容）
- 新增 `.meta.json` 元数据文件与 CSV 同目录同名
- 核心逻辑：
  1. 加载缓存时，先检查元数据（如果没有元数据，按旧逻辑全量加载）
  2. 比较缓存中最新日期与今天日期
  3. 如果有缺失，只请求 `缓存最新日期 + 1天` 到 `今天` 的数据
  4. 新数据追加到 CSV 末尾（去重），更新元数据

这个方案改动最小，风险最低，同时解决了核心痛点。

## Key Assumptions to Validate

- [ ] 数据源支持按日期范围增量查询（AKShare/BaoStock 都支持）
- [ ] CSV 追加写入不会导致数据损坏（使用临时文件 + 原子替换）
- [ ] 去重逻辑（按 date 列）能正确处理边界情况

## MVP Scope

**In Scope:**
- 新增 `load_cache_metadata()` 和 `save_cache_metadata()` 函数
- 修改 `get_stock_data()`：检查缓存最新日期，决定是全量还是增量
- 新增 `incremental_update()` 函数：获取增量数据并合并
- 简单的去重逻辑（按 date 列去重，保留最新的）
- 默认开启增量更新

**Out of Scope (for now):**
- 数据分片（按月份/年份）
- 缓存过期自动清理
- 复杂的数据完整性校验（哈希等）
- 缓存压缩

## Not Doing (and Why)

- **不做数据分片** — 当前数据量不大，简单方案优先
- **不做缓存过期** — 用户明确要求保留所有历史数据
- **不做复杂完整性校验** — 简单的日期连续性检查就够了
- **不修改缓存文件格式** — 保持向后兼容最重要

## Open Questions

- 是否需要一个 `force_refresh` 参数来强制全量刷新？（建议加）
- 元数据文件是否需要记录数据源信息？（建议加，便于问题排查）

## Technical Design Sketch

### Meta Data Structure
```json
{
  "symbol": "000333",
  "period": "daily",
  "start_date": "20250101",
  "latest_date": "2026-04-30",
  "last_updated": "2026-05-12T10:30:00",
  "source": "AKShare v2",
  "row_count": 320,
  "integrity": "ok"
}
```

### New Functions
```python
def load_cache_metadata(symbol: str, period: str, start_date: str) -> Optional[dict]
def save_cache_metadata(metadata: dict, symbol: str, period: str, start_date: str)
def get_incremental_data(symbol: str, period: str, from_date: str) -> pd.DataFrame
def merge_and_deduplicate(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame
```

### Flow
```
get_stock_data()
  ├─ 尝试加载缓存 + 元数据
  │   ├─ 无缓存 → 全量获取 → 保存缓存 + 元数据
  │   └─ 有缓存
  │       ├─ 检查 latest_date < today
  │       │   ├─ 是 → 获取增量数据 → 合并 → 保存
  │       │   └─ 否 → 直接返回缓存
  │       └─ 无元数据（旧缓存）→ 全量获取 → 覆盖缓存 + 新建元数据
  └─ 缓存失败 → 数据源 fallback → 保存
```
