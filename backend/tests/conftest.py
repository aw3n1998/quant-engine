"""Pytest configuration and shared fixtures for crypto_quant_terminal tests."""

import pytest
import pandas as pd
import numpy as np
from io import StringIO
from datetime import datetime, timedelta


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="1h")
    data = {
        "timestamp": dates,
        "open": np.random.uniform(100, 110, 100),
        "high": np.random.uniform(110, 120, 100),
        "low": np.random.uniform(90, 100, 100),
        "close": np.random.uniform(100, 110, 100),
        "volume": np.random.uniform(1000, 10000, 100),
    }
    df = pd.DataFrame(data)
    # Ensure OHLC relationships
    df["high"] = df[["open", "high", "close"]].max(axis=1) + 1
    df["low"] = df[["open", "low", "close"]].min(axis=1) - 1
    return df


@pytest.fixture
def sample_returns():
    """Create sample returns data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=252, freq="1D")
    returns = np.random.normal(0.0005, 0.02, 252)
    return pd.Series(returns, index=dates)


@pytest.fixture
def sample_csv_content():
    """Create sample CSV content for upload testing."""
    csv_content = """timestamp,open,high,low,close,volume
2023-01-01 00:00:00,100.0,101.0,99.0,100.5,1000
2023-01-01 01:00:00,100.5,102.0,100.0,101.0,1100
2023-01-01 02:00:00,101.0,102.5,100.5,101.5,1200
2023-01-01 03:00:00,101.5,103.0,101.0,102.0,1300
2023-01-01 04:00:00,102.0,103.5,101.5,102.5,1400
"""
    return csv_content


@pytest.fixture
def invalid_csv_content():
    """Create invalid CSV content for validation testing."""
    # Missing required columns
    csv_content = """timestamp,price
2023-01-01 00:00:00,100.0
2023-01-01 01:00:00,100.5
"""
    return csv_content


@pytest.fixture
def invalid_ohlc_csv():
    """Create CSV with invalid OHLC relationships."""
    csv_content = """timestamp,open,high,low,close,volume
2023-01-01 00:00:00,100.0,99.0,101.0,100.5,1000
2023-01-01 01:00:00,100.5,100.0,102.0,101.0,1100
"""
    return csv_content


@pytest.fixture
def data_with_nan():
    """Create OHLCV data with NaN values."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="1h")
    data = {
        "timestamp": dates,
        "open": np.random.uniform(100, 110, 50),
        "high": np.random.uniform(110, 120, 50),
        "low": np.random.uniform(90, 100, 50),
        "close": np.random.uniform(100, 110, 50),
        "volume": np.random.uniform(1000, 10000, 50),
    }
    df = pd.DataFrame(data)
    # Add some NaN values
    df.loc[5:10, "close"] = np.nan
    df.loc[20:22, "volume"] = np.nan
    return df


@pytest.fixture
def data_with_duplicates():
    """Create OHLCV data with duplicate timestamps."""
    dates = list(pd.date_range(start="2023-01-01", periods=50, freq="1h"))
    # Add duplicate timestamp
    dates.insert(25, dates[24])

    data = {
        "timestamp": dates,
        "open": np.random.uniform(100, 110, 51),
        "high": np.random.uniform(110, 120, 51),
        "low": np.random.uniform(90, 100, 51),
        "close": np.random.uniform(100, 110, 51),
        "volume": np.random.uniform(1000, 10000, 51),
    }
    return pd.DataFrame(data)


@pytest.fixture
def zero_volume_data():
    """Create OHLCV data with zero volume candles."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="1h")
    data = {
        "timestamp": dates,
        "open": np.random.uniform(100, 110, 50),
        "high": np.random.uniform(110, 120, 50),
        "low": np.random.uniform(90, 100, 50),
        "close": np.random.uniform(100, 110, 50),
        "volume": np.random.uniform(1000, 10000, 50),
    }
    df = pd.DataFrame(data)
    df.loc[10:15, "volume"] = 0  # Zero volume candles
    return df
