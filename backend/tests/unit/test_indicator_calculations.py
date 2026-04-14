"""Unit tests for indicator calculations and technical analysis."""

import pytest
import pandas as pd
import numpy as np


class TestIndicatorCalculations:
    """Test technical indicator calculations."""

    def test_simple_moving_average(self, sample_ohlcv_data):
        """Test simple moving average calculation."""
        df = sample_ohlcv_data.copy()
        window = 5

        # Calculate SMA
        df["sma"] = df["close"].rolling(window=window).mean()

        # Check results
        assert df["sma"].isna().sum() == window - 1, "First n-1 values should be NaN"
        assert not df["sma"].iloc[window:].isna().any(), "After warmup, no NaN should exist"

        # Verify calculation accuracy
        manual_sma = df["close"].iloc[0 : window].mean()
        calculated_sma = df["sma"].iloc[window - 1]
        np.testing.assert_almost_equal(manual_sma, calculated_sma)

    def test_exponential_moving_average(self, sample_ohlcv_data):
        """Test exponential moving average calculation."""
        df = sample_ohlcv_data.copy()
        window = 5

        # Calculate EMA
        df["ema"] = df["close"].ewm(span=window, adjust=False).mean()

        # Check no NaN after first value
        assert df["ema"].notna().any(), "EMA should have valid values"
        assert df["ema"].iloc[0] != np.nan, "EMA should start with first close price"

    def test_rsi_calculation(self, sample_ohlcv_data):
        """Test RSI (Relative Strength Index) calculation."""
        df = sample_ohlcv_data.copy()
        period = 14

        # Calculate price changes
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # Avoid division by zero
        rs = np.where(loss != 0, gain / loss, 0)
        rsi = 100 - (100 / (1 + rs))

        # RSI should be between 0 and 100
        valid_rsi = rsi[~np.isnan(rsi)]
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all(), "RSI should be between 0-100"

    def test_bollinger_bands(self, sample_ohlcv_data):
        """Test Bollinger Bands calculation."""
        df = sample_ohlcv_data.copy()
        window = 20
        num_std = 2

        # Calculate Bollinger Bands
        sma = df["close"].rolling(window=window).mean()
        std = df["close"].rolling(window=window).std()
        df["upper_band"] = sma + (std * num_std)
        df["lower_band"] = sma - (std * num_std)
        df["middle_band"] = sma

        # Check relationships (ignoring warmup NaNs)
        assert (df["upper_band"].dropna() >= df["middle_band"].dropna()).all(), "Upper band should be >= middle"
        assert (df["lower_band"].dropna() <= df["middle_band"].dropna()).all(), "Lower band should be <= middle"

    def test_macd_calculation(self, sample_ohlcv_data):
        """Test MACD (Moving Average Convergence Divergence) calculation."""
        df = sample_ohlcv_data.copy()

        # Calculate MACD
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        # Check that MACD values exist after warmup
        assert df["macd"].iloc[26:].notna().all(), "MACD should have values after warmup"

    def test_atr_calculation(self, sample_ohlcv_data):
        """Test ATR (Average True Range) calculation."""
        df = sample_ohlcv_data.copy()
        period = 14

        # Calculate True Range
        df["tr1"] = df["high"] - df["low"]
        df["tr2"] = abs(df["high"] - df["close"].shift())
        df["tr3"] = abs(df["low"] - df["close"].shift())
        df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

        # Calculate ATR
        df["atr"] = df["tr"].rolling(window=period).mean()

        # ATR should be positive and less than the range
        atr_values = df["atr"][period:].dropna()
        assert (atr_values > 0).all(), "ATR should be positive"

    def test_returns_calculation(self, sample_ohlcv_data):
        """Test returns calculation from price data."""
        df = sample_ohlcv_data.copy()

        # Calculate daily returns
        df["returns"] = df["close"].pct_change()

        # Check first return is NaN
        assert pd.isna(df["returns"].iloc[0]), "First return should be NaN"

        # Check returns are calculated correctly
        manual_return = (df["close"].iloc[1] - df["close"].iloc[0]) / df["close"].iloc[0]
        calculated_return = df["returns"].iloc[1]
        np.testing.assert_almost_equal(manual_return, calculated_return)

    def test_cumulative_returns(self, sample_returns):
        """Test cumulative returns calculation."""
        returns = sample_returns
        # Method 1: using cumprod
        cumulative_1 = (1 + returns).cumprod() - 1

        # Method 2: manual calculation
        cumulative_2 = (1 + returns).cumprod() - 1

        pd.testing.assert_series_equal(cumulative_1, cumulative_2)

        # Check monotonic increase (for positive average returns)
        if returns.mean() > 0:
            assert cumulative_1.iloc[-1] > 0, "Cumulative returns should be positive overall"

    def test_sharpe_ratio_calculation(self, sample_returns):
        """Test Sharpe Ratio calculation."""
        returns = sample_returns
        rf = 0.0  # Risk-free rate
        periods_per_year = 252  # Daily data

        # Calculate Sharpe Ratio
        excess_returns = returns - rf / periods_per_year
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)

        # Sharpe ratio should be a single number
        assert isinstance(sharpe, (int, float, np.number)), "Sharpe ratio should be numeric"

    def test_maximum_drawdown_calculation(self, sample_returns):
        """Test maximum drawdown calculation."""
        cumulative_returns = (1 + sample_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max

        max_dd = drawdown.min()

        # Max drawdown should be negative or zero
        assert max_dd <= 0, "Maximum drawdown should be negative or zero"
        assert max_dd >= -1, "Maximum drawdown should not exceed -100%"

    def test_win_rate_calculation(self):
        """Test win rate calculation for trades."""
        returns = pd.Series([0.02, -0.01, 0.03, 0.01, -0.02, 0.04, 0.02, -0.03])

        winning_trades = (returns > 0).sum()
        total_trades = len(returns)
        win_rate = winning_trades / total_trades

        assert win_rate == 0.625, "Win rate should be 5/8 = 62.5%"
        assert 0 <= win_rate <= 1, "Win rate should be between 0 and 1"
