from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.services.company_service import CHANGED_STATUSES


DIMENSION_ALIASES = {
    "product_name": "normalized_product_name",
}


class PivotService:
    def source_view(self, base: str, classification_mode: str) -> str:
        if base == "product":
            return "vw_product_primary_type_pivot"
        if base == "coverage":
            return "vw_product_type_coverage_pivot"
        if base == "sales":
            return "vw_product_sales_pivot"
        raise ValueError(f"Unsupported pivot base: {base}")

    def run_pivot(
        self,
        db: Session,
        base: str,
        classification_mode: str,
        rows: list[str],
        columns: list[str],
        filters: dict[str, list[Any]] | None,
        metrics: list[dict[str, str]],
        include_review: bool = False,
        min_confidence: float | None = None,
    ) -> dict[str, Any]:
        view = self.source_view(base, classification_mode)
        df = pd.read_sql_query(f"SELECT * FROM {view}", db.get_bind())
        classification_mode = "primary_only"
        if "assignment_role" in df.columns:
            df = df[(df["assignment_role"].isna()) | (df["assignment_role"] == "primary")]
        if "product_status" in df.columns:
            df = df[df["product_status"].fillna("active").astype(str).str.lower() == "active"]
        if not include_review and "needs_review" in df.columns:
            df = df[~df["needs_review"].astype(bool)]
        confidence_col = "confidence_total" if "confidence_total" in df.columns else "confidence"
        if min_confidence is not None and confidence_col in df.columns:
            df = df[df[confidence_col].fillna(0) >= min_confidence]
        filter_values = dict(filters or {})
        self._apply_company_inclusion(df, filter_values)
        for key, allowed in filter_values.items():
            if key.startswith("_"):
                continue
            col = DIMENSION_ALIASES.get(key, key)
            if col in df.columns and allowed:
                df = df[df[col].isin(allowed)]
        rows = [DIMENSION_ALIASES.get(item, item) for item in rows]
        columns = [DIMENSION_ALIASES.get(item, item) for item in columns]
        group_fields = [field for field in rows + columns if field in df.columns]
        if not metrics:
            metrics = [{"name": "product_count", "agg": "count_distinct", "field": "product_id"}]
        if df.empty:
            return {"base": base, "classification_mode": classification_mode, "rows": rows, "columns": columns, "metrics": [m["name"] for m in metrics], "records": []}
        if not group_fields:
            grouped = [({}, df)]
        else:
            grouped = df.groupby(group_fields, dropna=False)
        records: list[dict[str, Any]] = []
        for key, part in grouped:
            record: dict[str, Any] = {}
            if group_fields:
                values = key if isinstance(key, tuple) else (key,)
                record.update({field: None if pd.isna(value) else value for field, value in zip(group_fields, values)})
            for metric in metrics:
                record[metric["name"]] = self._aggregate(part, metric)
            records.append(record)
        return {"base": base, "classification_mode": classification_mode, "rows": rows, "columns": columns, "metrics": [m["name"] for m in metrics], "records": records}

    @staticmethod
    def _apply_company_inclusion(df: pd.DataFrame, filters: dict[str, list[Any]]) -> None:
        if "include_in_product_news_default" not in df.columns:
            return
        include_roles = filters.pop("_company_include_roles", [])
        exclude_roles = filters.pop("_exclude_company_roles", [])
        exclude_statuses = filters.pop("_exclude_statuses", [])
        if include_roles:
            keep = (df["include_in_product_news_default"] == "Y") | df["company_role"].isin(include_roles)
            df.drop(df.index[~keep], inplace=True)
        elif "include_in_product_news_default" not in filters:
            df.drop(df.index[df["include_in_product_news_default"] != "Y"], inplace=True)
        if exclude_roles and "company_role" in df.columns:
            df.drop(df.index[df["company_role"].isin(exclude_roles)], inplace=True)
        if exclude_statuses and "status_2024_2026" in df.columns:
            df.drop(df.index[df["status_2024_2026"].isin(exclude_statuses)], inplace=True)

    @staticmethod
    def _aggregate(df: pd.DataFrame, metric: dict[str, str]):
        if metric.get("filter_metric_names") and "metric_name" in df.columns:
            df = df[df["metric_name"].isin(metric["filter_metric_names"])]
        agg = metric.get("agg")
        field = metric.get("field")
        if field not in df.columns:
            if metric.get("name") == "article_count" and "article_count" in df.columns:
                return int(df["article_count"].sum())
            return 0
        series = df[field].dropna()
        if agg == "count_distinct":
            return int(series.nunique())
        if agg == "count":
            return int(series.count())
        if agg == "sum":
            return float(series.sum()) if len(series) else 0
        if agg == "max":
            return float(series.max()) if len(series) else None
        if agg == "avg":
            return float(series.mean()) if len(series) else None
        raise ValueError(f"Unsupported agg: {agg}")

    def presets(self) -> list[dict[str, Any]]:
        return [
            {"name": "industry_company", "base": "product", "rows": ["insurance_type"], "columns": ["company_name"], "metrics": [{"name": "product_count", "agg": "count_distinct", "field": "product_id"}]},
            {"name": "company_product_type", "base": "product", "rows": ["company_name"], "columns": ["product_type_name"], "metrics": [{"name": "product_count", "agg": "count_distinct", "field": "product_id"}]},
            {"name": "product_type_by_month", "base": "product", "rows": ["release_year_month"], "columns": ["product_type_name"], "metrics": [{"name": "product_count", "agg": "count_distinct", "field": "product_id"}]},
            {"name": "coverage_by_type", "base": "coverage", "rows": ["product_type_name"], "columns": ["risk_area"], "metrics": [{"name": "coverage_count", "agg": "count_distinct", "field": "coverage_id"}]},
            {"name": "sales_by_product_type", "base": "sales", "rows": ["product_type_name"], "columns": ["metric_name"], "metrics": [{"name": "sales_metric_sum", "agg": "sum", "field": "metric_value"}]},
        ]

    def export(self, result: dict[str, Any], output_path: str | Path, file_format: str = "csv") -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(result.get("records") or [])
        if file_format == "xlsx":
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
