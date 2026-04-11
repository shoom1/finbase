"""SQLite schema definitions for time series database."""

# SQL schema for risk_factors table
RISK_FACTORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_factors (
    risk_factor_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol              TEXT NOT NULL,
    asset_class         TEXT NOT NULL,
    asset_subclass      TEXT,
    description         TEXT,
    currency            TEXT,
    country             TEXT,
    sector              TEXT,
    data_source         TEXT NOT NULL,
    frequency           TEXT NOT NULL,
    start_date          DATE,
    end_date            DATE,
    last_updated        TIMESTAMP,
    is_active           BOOLEAN DEFAULT 1,
    metadata_json       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(symbol, asset_class, data_source)
);
"""

# SQL schema for timeseries_data table
TIMESERIES_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS timeseries_data (
    ts_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_factor_id      INTEGER NOT NULL,
    date                DATE NOT NULL,
    open                REAL,
    high                REAL,
    low                 REAL,
    close               REAL NOT NULL,
    adj_close           REAL,
    volume              REAL,
    data_quality        TEXT DEFAULT 'good',

    FOREIGN KEY (risk_factor_id) REFERENCES risk_factors(risk_factor_id),
    UNIQUE(risk_factor_id, date)
);
"""

# Indexes for performance
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_risk_factor_date ON timeseries_data(risk_factor_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_date ON timeseries_data(date);",
    "CREATE INDEX IF NOT EXISTS idx_symbol ON risk_factors(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_asset_class ON risk_factors(asset_class);",
]

# SQL schema for data_updates table (audit trail)
DATA_UPDATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_updates (
    update_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_factor_id      INTEGER NOT NULL,
    update_type         TEXT NOT NULL,
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    records_added       INTEGER,
    records_updated     INTEGER,
    data_source         TEXT,
    update_timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes               TEXT,

    FOREIGN KEY (risk_factor_id) REFERENCES risk_factors(risk_factor_id)
);
"""

# SQL schema for indices table (equity index metadata)
INDICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS indices (
    index_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    index_code          TEXT UNIQUE NOT NULL,
    index_name          TEXT NOT NULL,
    description         TEXT,
    country             TEXT,
    asset_class         TEXT DEFAULT 'equity',
    data_source         TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated        TIMESTAMP
);
"""

# SQL schema for index constituents (slowly changing dimension)
INDEX_CONSTITUENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS index_constituents (
    constituent_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    index_id            INTEGER NOT NULL,
    symbol              TEXT NOT NULL,

    effective_date      DATE NOT NULL,
    end_date            DATE,

    company_name        TEXT,
    sector              TEXT,
    sub_industry        TEXT,
    date_added_to_index DATE,

    extracted_at        TIMESTAMP NOT NULL,
    data_source         TEXT NOT NULL,

    FOREIGN KEY (index_id) REFERENCES indices(index_id),
    UNIQUE(index_id, symbol, effective_date)
);
"""

# Index-specific indexes for performance
INDEX_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_constituents_symbol ON index_constituents(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_constituents_dates ON index_constituents(effective_date, end_date);",
    "CREATE INDEX IF NOT EXISTS idx_constituents_index_id ON index_constituents(index_id);",
    "CREATE INDEX IF NOT EXISTS idx_constituents_active ON index_constituents(index_id, end_date);",
]

def get_all_schemas():
    """Return all schema definitions."""
    return [
        RISK_FACTORS_SCHEMA,
        TIMESERIES_DATA_SCHEMA,
        DATA_UPDATES_SCHEMA,
        INDICES_SCHEMA,
        INDEX_CONSTITUENTS_SCHEMA
    ] + INDEXES + INDEX_INDEXES
