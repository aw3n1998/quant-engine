"""Unit tests for data validation functions."""

import pytest
import pandas as pd
import numpy as np
from io import StringIO


class TestDataValidation:
    """Test data validation functionality."""

    def test_valid_ohlcv_data(self, sample_ohlcv_data):
        """Test validation of valid OHLCV data."""
        df = sample_ohlcv_data

        # Check required columns exist
        required_columns = {"open", "high", "low", "close", "volume"}
        assert required_columns.issubset(df.columns), "Missing required columns"

        # Check OHLC relationships
        assert (df["high"] >= df["low"]).all(), "Invalid OHLC: high < low"
        assert (df["high"] >= df["open"]).all(), "Invalid OHLC: high < open"
        assert (df["high"] >= df["close"]).all(), "Invalid OHLC: high < close"
        assert (df["low"] <= df["open"]).all(), "Invalid OHLC: low > open"
        assert (df["low"] <= df["close"]).all(), "Invalid OHLC: low > close"

    def test_csv_upload_missing_columns(self, invalid_csv_content):
        """Test validation fails with missing required columns."""
        df = pd.read_csv(StringIO(invalid_csv_content))
        required_columns = {"open", "high", "low", "close", "volume"}
        missing = required_columns - set(df.columns)

        assert len(missing) > 0, "Should detect missing columns"

    def test_csv_upload_invalid_ohlc(self, invalid_ohlc_csv):
        """Test validation fails with invalid OHLC relationships."""
        df = pd.read_csv(StringIO(invalid_ohlc_csv))

        # Find invalid rows
        invalid_rows = ~((df["high"] >= df["low"]) & (df["high"] >= df["open"]) & (df["high"] >= df["close"]))

        assert invalid_rows.any(), "Should detect invalid OHLC relationships"

    def test_data_with_nan_handling(self, data_with_nan):
        """Test handling of NaN values in data."""
        df = data_with_nan.copy()

        # Count NaN values before handling
        nan_before = df.isna().sum().sum()
        assert nan_before > 0, "Test data should contain NaN"

        # Option 1: Drop NaN rows
        df_dropped = df.dropna()
        assert df_dropped.isna().sum().sum() == 0, "Should remove all NaN"
        assert len(df_dropped) < len(data_with_nan), "Should have fewer rows"

        # Option 2: Forward fill
        df_filled = data_with_nan.copy()
        df_filled = df_filled.ffill()
        assert df_filled.isna().sum().sum() == 0, "Should fill all NaN"

    def test_data_with_duplicates(self, data_with_duplicates):
        """Test detection of duplicate timestamps."""
        df = data_with_duplicates
        duplicates = df[df.duplicated(subset=["timestamp"], keep=False)]

        assert len(duplicates) > 0, "Should detect duplicate timestamps"

    def test_zero_volume_detection(self, zero_volume_data):
        """Test detection of zero volume candles."""
        df = zero_volume_data
        zero_volume_rows = df[df["volume"] == 0]

        assert len(zero_volume_rows) > 0, "Should detect zero volume candles"

    def test_negative_price_validation(self):
        """Test detection of negative prices."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=10, freq="1h"),
                "open": np.array([100, 101, -5, 102, 103, 104, 105, 106, 107, 108]),
                "high": np.array([101, 102, 103, 104, 105, 106, 107, 108, 109, 110]),
                "low": np.array([99, 100, 101, 102, 103, 104, 105, 106, 107, 108]),
                "close": np.array([100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5]),
                "volume": np.array([1000] * 10),
            }
        )

        negative_rows = df[(df["open"] < 0) | (df["high"] < 0) | (df["low"] < 0) | (df["close"] < 0)]
        assert len(negative_rows) > 0, "Should detect negative prices"

    def test_monotonic_timestamp_check(self):
        """Test that timestamps are monotonically increasing."""
        # Valid monotonic
        df_valid = pd.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=10, freq="1h"),
                "open": np.random.uniform(100, 110, 10),
                "high": np.random.uniform(110, 120, 10),
                "low": np.random.uniform(90, 100, 10),
                "close": np.random.uniform(100, 110, 10),
                "volume": np.random.uniform(1000, 10000, 10),
            }
        )

        assert df_valid["timestamp"].is_monotonic_increasing, "Timestamps should be monotonically increasing"

        # Invalid non-monotonic
        df_invalid = df_valid.copy()
        df_invalid["timestamp"] = df_invalid["timestamp"].iloc[[0, 2, 1, 3, 4, 5, 6, 7, 8, 9]]

        assert not df_invalid["timestamp"].is_monotonic_increasing, "Should detect non-monotonic timestamps"


class TestCSVParsing:
    """Test CSV parsing and validation."""

    def test_csv_parsing_success(self, sample_csv_content):
        """Test successful CSV parsing."""
        df = pd.read_csv(StringIO(sample_csv_content))

        assert len(df) == 5, "Should parse 5 rows"
        assert set(df.columns) == {"timestamp", "open", "high", "low", "close", "volume"}

    def test_csv_datetime_parsing(self, sample_csv_content):
        """Test datetime column parsing."""
        df = pd.read_csv(StringIO(sample_csv_content), parse_dates=["timestamp"])

        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"]), "Timestamp should be datetime type"
        assert df["timestamp"].is_monotonic_increasing, "Timestamps should be sorted"

    def test_csv_numeric_conversion(self, sample_csv_content):
        """Test conversion of numeric columns."""
        df = pd.read_csv(StringIO(sample_csv_content))

        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} should be numeric"
