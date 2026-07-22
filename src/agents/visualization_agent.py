"""
Visualization Agent for Sustally ESG Intelligence Platform
Generates interactive Plotly figure charts for rankings, time-series trends, and sector comparisons.
"""

from typing import List, Dict, Any, Optional
import logging
import plotly.graph_objects as go
from src.agents.planner_agent import QueryPlan

logger = logging.getLogger(__name__)

class VisualizationAgent:
    def __init__(self):
        pass

    def create_visualization(
        self,
        plan: QueryPlan,
        retrieved_data: Dict[str, Any],
        ranking_data: Optional[Dict[str, Any]] = None
    ) -> Optional[go.Figure]:
        """
        Creates an interactive Plotly Figure based on query plan and data.
        Returns None if insufficient numeric data exists.
        """
        try:
            if ranking_data and ranking_data.get("ranked_table"):
                return self._create_ranking_chart(ranking_data)

            metrics = retrieved_data.get("structured_metrics", [])
            if not metrics:
                return None

            if plan.intent == "TREND" or len(plan.years) > 1:
                return self._create_trend_chart(metrics)

            if plan.intent in ["COMPARISON", "RANKING"] or len(plan.companies) > 1:
                return self._create_comparison_chart(metrics)

            return None
        except Exception as e:
            logger.warning(f"Could not generate Plotly chart: {e}")
            return None

    def _create_ranking_chart(self, ranking_data: Dict[str, Any]) -> go.Figure:
        table = ranking_data.get("ranked_table", [])
        companies = [item["company"] for item in reversed(table)]
        values = [item["value"] for item in reversed(table)]
        unit = table[0]["unit"] if table else ""
        metric_label = table[0]["metric_label"] if table else "Metric"

        fig = go.Figure(go.Bar(
            x=values,
            y=companies,
            orientation='h',
            marker=dict(color='#00E676', line=dict(color='#00B0FF', width=1)),
            text=[f"{v} {unit}" for v in values],
            textposition='auto'
        ))

        fig.update_layout(
            title=f"Ranking Benchmark: {metric_label} ({ranking_data.get('year', '')})",
            xaxis_title=f"Value ({unit})",
            yaxis_title="Company",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0")
        )
        return fig

    def _create_trend_chart(self, metrics: List[Dict[str, Any]]) -> go.Figure:
        # Group by company -> (year, value)
        comp_map: Dict[str, Dict[str, float]] = {}
        unit = metrics[0].get("unit", "")
        metric_label = metrics[0].get("metric_label", "Metric")

        for m in metrics:
            c = m.get("company", "Unknown")
            y = str(m.get("year", ""))
            v = m.get("value")
            if c and y and v is not None:
                if c not in comp_map:
                    comp_map[c] = {}
                comp_map[c][y] = float(v)

        fig = go.Figure()
        for comp, yr_data in comp_map.items():
            sorted_years = sorted(yr_data.keys())
            sorted_vals = [yr_data[y] for y in sorted_years]
            fig.add_trace(go.Scatter(
                x=sorted_years,
                y=sorted_vals,
                mode='lines+markers',
                name=comp,
                line=dict(width=3),
                marker=dict(size=8)
            ))

        fig.update_layout(
            title=f"Time-Series Trend: {metric_label}",
            xaxis_title="Reporting Year",
            yaxis_title=f"Value ({unit})",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0")
        )
        return fig

    def _create_comparison_chart(self, metrics: List[Dict[str, Any]]) -> go.Figure:
        companies = [m.get("company", "Unknown") for m in metrics]
        values = [m.get("value", 0.0) for m in metrics]
        unit = metrics[0].get("unit", "")
        metric_label = metrics[0].get("metric_label", "Metric")

        fig = go.Figure(go.Bar(
            x=companies,
            y=values,
            marker=dict(color='#00B0FF'),
            text=[f"{v} {unit}" for v in values],
            textposition='auto'
        ))

        fig.update_layout(
            title=f"Cross-Company Benchmark: {metric_label}",
            xaxis_title="Company",
            yaxis_title=f"Value ({unit})",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0")
        )
        return fig
