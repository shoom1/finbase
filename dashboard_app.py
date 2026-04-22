"""
FinBase Dashboard - Interactive web dashboard for data availability visualization.

Run with: streamlit run dashboard_app.py
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime

from finbase.dashboard import DashboardDataService
from finbase.config import get_settings
from finbase.utils.logging import configure_application_logging, get_logger

configure_application_logging()

# Configure page
st.set_page_config(
    page_title="FinBase Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize logger
logger = get_logger(__name__)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
    }
    h1 {
        color: #1f77b4;
    }
    .freshness-fresh {
        color: #28a745;
        font-weight: bold;
    }
    .freshness-current {
        color: #17a2b8;
        font-weight: bold;
    }
    .freshness-stale {
        color: #ffc107;
        font-weight: bold;
    }
    .freshness-old {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize data service
@st.cache_resource
def get_data_service():
    """Get cached data service instance."""
    settings = get_settings()
    return DashboardDataService(settings.database.path)

data_service = get_data_service()


def render_header():
    """Render dashboard header."""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("📊 FinBase Dashboard")
        st.markdown("**Historical Financial Data Availability & Quality Monitor**")

    with col2:
        st.markdown("###")  # Spacing
        if st.button("🔄 Refresh Data", use_container_width=True):
            data_service.clear_cache()
            st.cache_data.clear()
            st.rerun()


def render_overview_panel():
    """Render overview statistics panel."""
    st.header("📈 Overview")

    stats = data_service.get_overview_stats()

    # Create metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Symbols",
            value=f"{stats['total_symbols']:,}",
            delta=None
        )

    with col2:
        st.metric(
            label="Data Points",
            value=f"{stats['total_data_points']:,}",
            delta=None
        )

    with col3:
        st.metric(
            label="Asset Classes",
            value=stats['asset_classes'],
            delta=None
        )

    with col4:
        st.metric(
            label="Database Size",
            value=f"{stats['database_size_mb']:.1f} MB",
            delta=None
        )

    # Second row of metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Sectors",
            value=stats.get('sectors', 'N/A'),
            delta=None
        )

    with col2:
        st.metric(
            label="Countries",
            value=stats.get('countries', 'N/A'),
            delta=None
        )

    with col3:
        if stats['date_range']:
            st.metric(
                label="Date Range",
                value=f"{stats['earliest_date']} to {stats['latest_date']}",
                delta=None
            )
        else:
            st.metric(label="Date Range", value="No data", delta=None)

    with col4:
        if stats['last_updated']:
            st.metric(
                label="Last Updated",
                value=str(stats['last_updated'])[:10],
                delta=None
            )
        else:
            st.metric(label="Last Updated", value="Never", delta=None)


def render_data_coverage():
    """Render data coverage visualization."""
    st.header("📅 Data Coverage Timeline")

    coverage_df = data_service.get_data_coverage()

    if coverage_df.empty:
        st.warning("No data available to display coverage.")
        return

    # Create Gantt-style chart
    fig = go.Figure()

    # Sort by asset class and symbol
    coverage_df = coverage_df.sort_values(['asset_class', 'symbol'])

    # Color mapping for asset classes
    asset_classes = coverage_df['asset_class'].unique()
    colors = px.colors.qualitative.Set2[:len(asset_classes)]
    color_map = dict(zip(asset_classes, colors))

    for idx, row in coverage_df.iterrows():
        if pd.notna(row['actual_start']) and pd.notna(row['actual_end']):
            fig.add_trace(go.Scatter(
                x=[row['actual_start'], row['actual_end']],
                y=[row['symbol'], row['symbol']],
                mode='lines',
                line=dict(
                    color=color_map.get(row['asset_class'], '#1f77b4'),
                    width=10
                ),
                name=row['asset_class'],
                showlegend=False,
                hovertemplate=f"<b>{row['symbol']}</b><br>" +
                             f"Asset Class: {row['asset_class']}<br>" +
                             f"Sector: {row.get('sector', 'N/A')}<br>" +
                             f"Start: {row['actual_start']}<br>" +
                             f"End: {row['actual_end']}<br>" +
                             f"Data Points: {row['data_points']:,}<br>" +
                             f"Coverage: {row['coverage_pct']:.1f}%<br>" +
                             "<extra></extra>"
            ))

    fig.update_layout(
        title="Data Availability by Symbol",
        xaxis_title="Date",
        yaxis_title="Symbol",
        height=max(400, len(coverage_df) * 25),
        hovermode='closest',
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

    # Coverage statistics
    st.subheader("Coverage Statistics")
    quality = data_service.get_data_quality_summary()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Average Coverage", f"{quality['avg_coverage']:.1f}%")

    with col2:
        st.metric("Median Coverage", f"{quality['median_coverage']:.1f}%")

    with col3:
        st.metric("Full Coverage", quality['symbols_with_full_coverage'])

    with col4:
        st.metric("With Gaps", quality['symbols_with_gaps'])


def render_asset_distribution():
    """Render asset distribution charts."""
    st.header("🏢 Asset Distribution")

    distributions = data_service.get_asset_distribution()

    if not distributions:
        st.warning("No distribution data available.")
        return

    # Create tabs for different distributions
    tabs = st.tabs(["Asset Class", "Sector", "Country", "Currency"])

    # Asset Class Distribution
    with tabs[0]:
        if 'asset_class' in distributions:
            df = distributions['asset_class']

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.pie(
                    df,
                    values='count',
                    names='asset_class',
                    title='Symbols by Asset Class',
                    hole=0.4
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.dataframe(
                    df.style.format({'count': '{:,}'}),
                    hide_index=True,
                    use_container_width=True
                )

    # Sector Distribution
    with tabs[1]:
        if 'sector' in distributions and not distributions['sector'].empty:
            df = distributions['sector']

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.bar(
                    df.head(10),
                    x='count',
                    y='sector',
                    orientation='h',
                    title='Top 10 Sectors',
                    labels={'count': 'Number of Symbols', 'sector': 'Sector'}
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.dataframe(
                    df.head(10).style.format({'count': '{:,}'}),
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info("No sector data available.")

    # Country Distribution
    with tabs[2]:
        if 'country' in distributions and not distributions['country'].empty:
            df = distributions['country']

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.pie(
                    df.head(10),
                    values='count',
                    names='country',
                    title='Symbols by Country (Top 10)'
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.dataframe(
                    df.head(10).style.format({'count': '{:,}'}),
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info("No country data available.")

    # Currency Distribution
    with tabs[3]:
        if 'currency' in distributions and not distributions['currency'].empty:
            df = distributions['currency']

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.bar(
                    df,
                    x='currency',
                    y='count',
                    title='Symbols by Currency',
                    labels={'count': 'Number of Symbols', 'currency': 'Currency'}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.dataframe(
                    df.style.format({'count': '{:,}'}),
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info("No currency data available.")


def render_data_freshness():
    """Render data freshness table."""
    st.header("⏰ Data Freshness")

    freshness_df = data_service.get_data_freshness()

    if freshness_df.empty:
        st.warning("No freshness data available.")
        return

    # Summary metrics
    freshness_counts = freshness_df['freshness_status'].value_counts()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        fresh_count = freshness_counts.get('Fresh', 0)
        st.metric("🟢 Fresh", fresh_count, help="Updated within 1 day")

    with col2:
        current_count = freshness_counts.get('Current', 0)
        st.metric("🔵 Current", current_count, help="Updated within 7 days")

    with col3:
        stale_count = freshness_counts.get('Stale', 0)
        st.metric("🟡 Stale", stale_count, help="Updated within 30 days")

    with col4:
        old_count = freshness_counts.get('Old', 0)
        st.metric("🔴 Old", old_count, help="Updated > 30 days ago")

    # Filter options
    st.subheader("Filter Data")

    col1, col2 = st.columns(2)

    with col1:
        status_filter = st.multiselect(
            "Freshness Status",
            options=['Fresh', 'Current', 'Stale', 'Old'],
            default=['Stale', 'Old']
        )

    with col2:
        asset_class_filter = st.multiselect(
            "Asset Class",
            options=freshness_df['asset_class'].unique().tolist(),
            default=freshness_df['asset_class'].unique().tolist()
        )

    # Apply filters
    filtered_df = freshness_df[
        (freshness_df['freshness_status'].isin(status_filter)) &
        (freshness_df['asset_class'].isin(asset_class_filter))
    ]

    # Display table
    st.subheader(f"Showing {len(filtered_df)} of {len(freshness_df)} symbols")

    # Format the dataframe for display
    display_df = filtered_df[[
        'symbol', 'asset_class', 'sector', 'end_date', 'days_stale', 'freshness_status'
    ]].copy()

    display_df['end_date'] = pd.to_datetime(display_df['end_date']).dt.strftime('%Y-%m-%d')

    # Color code the status
    def color_status(val):
        colors = {
            'Fresh': 'background-color: #d4edda',
            'Current': 'background-color: #d1ecf1',
            'Stale': 'background-color: #fff3cd',
            'Old': 'background-color: #f8d7da'
        }
        return colors.get(val, '')

    styled_df = display_df.style.applymap(
        color_status,
        subset=['freshness_status']
    ).format({
        'days_stale': '{:.0f} days'
    })

    st.dataframe(styled_df, use_container_width=True, height=400)


def render_sidebar():
    """Render sidebar with additional information."""
    with st.sidebar:
        st.header("ℹ️ About")

        st.markdown("""
        ### FinBase Dashboard

        Interactive dashboard for monitoring historical financial data availability and quality.

        **Features:**
        - 📊 Overview statistics
        - 📅 Data coverage timeline
        - 🏢 Asset distribution
        - ⏰ Data freshness tracking

        **Data Refresh:**
        Click the refresh button to update the dashboard with latest data.
        """)

        st.markdown("---")

        st.header("🔧 Settings")

        settings = get_settings()
        st.text(f"Database: {settings.database.path}")
        st.text(f"Environment: {settings.environment}")

        st.markdown("---")

        st.header("📚 Quick Links")

        st.markdown("""
        - [Documentation](README.md)
        - [Architecture Review](notes/architecture_review_and_improvements.md)
        - [Phase 1 Summary](notes/phase1_implementation_summary.md)
        - [Phase 2 Summary](notes/phase2_implementation_summary.md)
        """)


def main():
    """Main dashboard application."""
    render_header()

    # Sidebar
    render_sidebar()

    # Check if database exists
    settings = get_settings()
    from pathlib import Path

    if not Path(settings.database.path).exists():
        st.error(f"❌ Database not found at: {settings.database.path}")
        st.info("💡 Initialize the database using: `python scripts/setup_database.py --init`")
        return

    # Main content
    render_overview_panel()

    st.markdown("---")

    render_data_coverage()

    st.markdown("---")

    render_asset_distribution()

    st.markdown("---")

    render_data_freshness()

    # Footer
    st.markdown("---")
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
