# Quick Task 260414-v8a: ReportData.clusters → cluster: ReportCluster - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

## Task Boundary

ReportData.clusters → cluster: ReportCluster

## Implementation Decisions

### 结构变更
- 完全替换 `clusters: dict[str, list[ReportCluster]]` 为 `cluster: ReportCluster`
- 不再按 tag 分组，改为单 cluster 结构
