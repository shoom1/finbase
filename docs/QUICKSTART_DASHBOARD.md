# Dashboard Quick Start Guide

## 🚀 Launch in 3 Steps

### Step 1: Setup (First Time Only)

**Note:** Database is stored in `~/.finbase/timeseries.db` by default. Configuration is saved to `~/.finbaserc`.

```bash
# Option A: Automated setup with demo data
python demo_dashboard.py

# Option B: Manual setup
python scripts/setup_database.py --init
python scripts/setup_database.py --load-indices --max-symbols 10

# Option C: Custom database location
python scripts/setup_database.py --init --db-path /custom/path/db.db
```

### Step 2: Launch Dashboard

```bash
streamlit run dashboard_app.py
```

### Step 3: Open Browser

Dashboard opens automatically at: **http://localhost:8501**

---

## 📊 What You'll See

### 1. Overview Panel (Top)
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Total       │ Data        │ Asset       │ Database    │
│ Symbols: 25 │ Points: 32K │ Classes: 2  │ Size: 2.4MB │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

### 2. Data Coverage Timeline
```
Symbol    2020    2021    2022    2023    2024
^GSPC     ████████████████████████████████████
AAPL      ████████████████████████████████████
MSFT      ░░░░████████████████████████████████  (gap)
```

### 3. Asset Distribution
```
[Pie Chart]        [Bar Chart]        [Table]
Asset Classes      Top Sectors        Country Breakdown
```

### 4. Data Freshness
```
Status          Count
🟢 Fresh         15 symbols
🔵 Current        5 symbols
🟡 Stale          3 symbols
🔴 Old            2 symbols
```

---

## 🎯 Common Tasks

### Refresh Data
Click **🔄 Refresh Data** button (top-right)

### Filter Stale Symbols
1. Scroll to "Data Freshness"
2. Select "Stale" and "Old" in filter
3. Note symbols that need updating

### Check Coverage
1. View "Data Coverage Timeline"
2. Look for gaps (short bars)
3. Check coverage percentage

### View Distribution
1. Go to "Asset Distribution"
2. Switch between tabs
3. See breakdowns by sector/country

---

## ⚙️ Configuration

### Change Port
```bash
streamlit run dashboard_app.py --server.port 8080
```

### Allow Team Access
```bash
streamlit run dashboard_app.py --server.address 0.0.0.0
# Access at http://<your-ip>:8501
```
