# FinBase Dashboard

**Interactive web dashboard for visualizing financial data availability and quality.**

![Dashboard](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit)
---

## Overview

The FinBase Dashboard provides real-time visualization of your financial data database, focusing on data availability, freshness, and distribution across asset classes, sectors, and geographies.

### Key Features

✅ **Overview Panel** - Key metrics at a glance
✅ **Data Coverage Timeline** - Gantt-style visualization of data availability
✅ **Asset Distribution** - Pie charts and bar graphs for composition analysis
✅ **Data Freshness Tracking** - Identify stale data that needs updating
✅ **Interactive Filtering** - Drill down by asset class, sector, or status
✅ **Cached Data** - 5-minute cache for fast performance
✅ **On-Demand Refresh** - Manual refresh button for latest data

---

## Quick Start

### 1. Install Dependencies

```bash
# Activate finbase environment
conda activate finbase

# Dependencies already installed via environment.yml:
# - streamlit>=1.28.0
# - plotly>=5.17.0
```

### 2. Launch Dashboard

```bash
streamlit run dashboard_app.py
```

The dashboard will open in your default browser at `http://localhost:8501`

### 3. First Time Setup

If you see "Database not found", initialize it first:

```bash
python scripts/setup_database.py --init
python scripts/setup_database.py --load-indices --max-symbols 5
```

---

## Dashboard Sections

### 1. Overview Panel

**Location:** Top of dashboard

**Shows:**
- Total symbols tracked
- Total data points in database
- Number of asset classes, sectors, countries
- Database size in MB
- Date range of data
- Last update timestamp

**Use Case:** Quick health check of your database

---

### 2. Data Coverage Timeline

**Location:** Second section

**Visualization:** Interactive Gantt-style chart showing data availability per symbol

**Features:**
- Each symbol displayed as horizontal bar
- Start and end dates visible
- Hover for detailed information
- Color-coded by asset class
- Coverage percentage displayed

**Metrics:**
- Average coverage percentage
- Median coverage
- Symbols with full coverage (>99%)
- Symbols with gaps (<95%)

**Use Case:** Identify data gaps, verify coverage completeness

---

### 3. Asset Distribution

**Location:** Third section

**Tabs:**

#### Asset Class Tab
- Pie chart showing distribution by asset class
- Data table with counts

#### Sector Tab (Equities)
- Bar chart of top 10 sectors
- Full data table

#### Country Tab
- Pie chart of top 10 countries
- Geographic distribution table

#### Currency Tab
- Bar chart by currency
- Currency breakdown table

**Use Case:** Understand portfolio composition, identify concentration

---

### 4. Data Freshness

**Location:** Bottom section

**Status Indicators:**
- 🟢 **Fresh** - Updated within 1 day
- 🔵 **Current** - Updated within 7 days
- 🟡 **Stale** - Updated within 30 days
- 🔴 **Old** - Not updated in >30 days

**Features:**
- Filter by freshness status
- Filter by asset class
- Sortable table
- Color-coded rows
- Shows days since last update

**Use Case:** Identify symbols that need data refresh

---

## Using the Dashboard

### Refresh Data

Click the **🔄 Refresh Data** button in the top-right to clear cache and reload latest database state.

**When to refresh:**
- After loading new data
- After database updates
- To see real-time changes

### Filter Data Freshness

1. Navigate to "Data Freshness" section
2. Use multi-select filters:
   - **Freshness Status:** Select Fresh/Current/Stale/Old
   - **Asset Class:** Select specific asset classes
3. Table updates automatically

**Example:** Show only stale equity symbols:
- Status: ✓ Stale, ✓ Old
- Asset Class: ✓ equity

### Interactive Charts

All charts are interactive:
- **Hover:** See detailed information
- **Zoom:** Click and drag to zoom
- **Pan:** Hold shift and drag to pan
- **Reset:** Double-click to reset view
- **Download:** Click camera icon to save as PNG

---

## Configuration

### Database Path

The database is stored in user space (`~/.finbase/timeseries.db` by default) and configuration is saved to `~/.finbaserc` (YAML format).

**Configuration priority:**
1. Explicit path in code
2. User config file (`~/.finbaserc`)
3. Environment variable (`FINBASE_DB_PATH`)
4. Default (`~/.finbase/timeseries.db`)

**View current database path:**
```bash
cat ~/.finbaserc
```

**Override with environment variable:**
```bash
export FINBASE_DB_PATH=/path/to/custom.db
streamlit run dashboard_app.py
```

**Set custom path during initialization:**
```bash
python scripts/setup_database.py --init --db-path /custom/path/db.db
```

### Cache TTL

Data is cached for 5 minutes by default. To modify:

Edit `src/dashboard/data_service.py`:

```python
self.cache_ttl = 300  # seconds (5 minutes)
```

### Port Configuration

Change default port (8501):

```bash
streamlit run dashboard_app.py --server.port 8080
```

### Remote Access

Allow external connections:

```bash
streamlit run dashboard_app.py --server.address 0.0.0.0
```

---

## Troubleshooting

### "Database not found"

**Solution:**

```bash
# Initialize database
python scripts/setup_database.py --init
```

### "No data to display"

**Solution:**

```bash
# Load sample data
python scripts/setup_database.py --load-indices --max-symbols 5
```

### Dashboard not updating after data load

**Solution:** Click **🔄 Refresh Data** button

### Port already in use

**Solution:**

```bash
# Kill existing streamlit process
pkill -f streamlit

# Or use different port
streamlit run dashboard_app.py --server.port 8502
```

### Slow performance

**Solutions:**
1. Check database size: `ls -lh data/timeseries.db`
2. Clear cache: Click refresh button
3. Restart dashboard: `Ctrl+C` then relaunch

---

## Customization

### Adding New Metrics

Edit `src/dashboard/data_service.py`:

```python
def get_custom_metric(self):
    """Add your custom aggregation."""
    with TimeSeriesDB(self.db_path) as db:
        # Your SQL query
        result = ...
        return result
```

Update `dashboard_app.py`:

```python
def render_custom_section():
    """Render your custom visualization."""
    data = data_service.get_custom_metric()
    st.plotly_chart(...)
```

### Changing Colors

Modify color schemes in `dashboard_app.py`:

```python
# Asset class colors
colors = px.colors.qualitative.Set2

# Freshness status colors
colors = {
    'Fresh': '#28a745',
    'Current': '#17a2b8',
    'Stale': '#ffc107',
    'Old': '#dc3545'
}
```

### Custom Filters

Add filters in respective render functions:

```python
symbol_filter = st.text_input("Filter by symbol")
filtered_df = df[df['symbol'].str.contains(symbol_filter)]
```

