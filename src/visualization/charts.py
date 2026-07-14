import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List, Optional
from src.processing.metric_taxonomy import METRIC_TAXONOMY

def create_comparison_chart(
    structured_data: Dict[str, Dict[str, Dict[str, Any]]],
    metric_key: str
) -> Optional[go.Figure]:
    """
    Generates a Plotly Figure comparing a single metric across companies and years.
    """
    metric_info = METRIC_TAXONOMY.get(metric_key)
    if not metric_info:
        return None
        
    title = metric_info["label"]
    unit = metric_info["unit"]
    
    # Flatten the data for easier plotting
    plot_rows = []
    for company, years_dict in structured_data.items():
        for year, metrics in years_dict.items():
            metric_val = metrics.get(metric_key)
            if metric_val:
                plot_rows.append({
                    "Company": company,
                    "Year": year,
                    "Value": metric_val["value"]
                })
                
    if not plot_rows:
        return None
        
    df = pd.DataFrame(plot_rows)
    
    # Generate grouped bar chart
    fig = go.Figure()
    
    companies = df["Company"].unique()
    years = sorted(df["Year"].unique())
    
    for year in years:
        year_df = df[df["Year"] == year]
        # Align values with companies order
        values = []
        for c in companies:
            val_row = year_df[year_df["Company"] == c]
            if not val_row.empty:
                values.append(val_row["Value"].values[0])
            else:
                values.append(0)
                
        fig.add_trace(go.Bar(
            name=str(year),
            x=companies,
            y=values,
            text=values,
            textposition='auto',
        ))
        
    fig.update_layout(
        title=f"{title} Comparison",
        xaxis_title="Company",
        yaxis_title=f"Value ({unit})",
        barmode='group',
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def create_trend_chart(
    company: str,
    metric_key: str,
    years: List[str],
    values: List[float]
) -> Optional[go.Figure]:
    """
    Generates a Plotly Scatter Figure showing a single metric's trend over years for one company.
    """
    metric_info = METRIC_TAXONOMY.get(metric_key)
    if not metric_info:
        return None
        
    title = metric_info["label"]
    unit = metric_info["unit"]
    
    # Sort data by year
    sorted_pairs = sorted(zip(years, values), key=lambda x: str(x[0]))
    sorted_years = [str(p[0]) for p in sorted_pairs]
    sorted_values = [p[1] for p in sorted_pairs]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sorted_years,
        y=sorted_values,
        mode='lines+markers',
        marker=dict(size=8, color="#00E676"),
        line=dict(width=3, color="#00E676"),
        text=sorted_values,
        textposition='top center'
    ))
    
    fig.update_layout(
        title=f"{company} {title} Trend",
        xaxis_title="Year",
        yaxis_title=f"Value ({unit})",
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0')
    )
    
    return fig
