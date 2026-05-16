# Volume Strategy Chart — Hide Bollinger Bands, Show OBV

## Problem Statement

How might we ensure the chart for volume analysis strategy shows only volume-relevant indicators (price + OBV) instead of the irrelevant Bollinger Bands?

## Recommended Direction

**Price line + OBV sub-chart** — the classic volume analysis layout. Upper panel shows close price with buy/sell signal dots. Lower panel shows the OBV (On-Balance Volume) cumulative line, replacing the MACD histogram that other strategies use.

Bollinger Band fill area, upper band, middle band, and lower band lines are all gated to render only when the strategy is NOT dual_ma AND NOT volume_analysis — matching the existing dual_ma pattern.

## Key Assumptions to Validate

- [ ] OBV values in the API response sufficiently cover the 120-row history window — verify by checking `data.history[].obv` in a test call
- [ ] OBV y-axis scale works well with a line chart (OBV can have large cumulative values) — validate visually

## MVP Scope

**In** `templates/dashboard.html` `drawMiniChart()`:
- Add `isVolumeAnalysisChart` flag alongside existing `isDualMAChart`
- Gate Bollinger fill area (line 673): `if (!isDualMAChart && !isVolumeAnalysisChart)`
- Gate Bollinger lines (lines 732-769): same condition
- Lower panel: when `isVolumeAnalysisChart`, draw OBV line instead of MACD histogram

**Out:**
- No API changes (OBV already in response)
- No new files
- No changes to stat cards (already correctly gated)
- No changes to squeeze card rendering (already gated)

## Not Doing (and Why)

- Volume bars on the chart — requires Canvas bar rendering, significant effort; OBV line is more informative
- VWAP overlay — needs intraday data
- Volume Profile — needs price-bucket aggregation, architecture change

## Implementation Estimate

~50 lines changed in `templates/dashboard.html`, single function (`drawMiniChart`).
