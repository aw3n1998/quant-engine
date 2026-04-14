"""
数据验证工具模块

提供OHLCV数据的完整验证功能：
- 列名和类型检查
- OHLC关系验证
- 时间索引单调性检查
- 异常值检测
- NaN和重复值处理
"""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger("data_validation")


class DataValidationError(ValueError):
    """数据验证异常"""
    pass


def validate_ohlcv_data(
    df: pd.DataFrame,
    strict: bool = False,
    allow_nan: bool = False,
    max_nan_ratio: float = 0.1,
) -> pd.DataFrame:
    """
    验证OHLCV数据的完整性和正确性。

    Parameters
    ----------
    df : pd.DataFrame
        输入的OHLCV数据
    strict : bool, default False
        严格模式：如果为True，任何异常都会抛出异常；否则进行修复
    allow_nan : bool, default False
        是否允许NaN值
    max_nan_ratio : float, default 0.1
        允许的最大NaN比率（0-1）

    Returns
    -------
    pd.DataFrame
        验证并可能修复后的数据框

    Raises
    ------
    DataValidationError
        当数据不符合验证要求时
    """

    df = df.copy()

    # 1. 列名检查
    required_columns = {"open", "high", "low", "close", "volume"}
    df.columns = df.columns.str.lower().str.strip()

    missing_cols = required_columns - set(df.columns)
    if missing_cols:
        raise DataValidationError(f"缺少必需列: {sorted(missing_cols)}")

    # 2. 数据类型检查
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        try:
            df[col] = pd.to_numeric(df[col], errors="raise")
        except Exception as e:
            raise DataValidationError(f"列 {col} 无法转换为数字: {e}")

    # 3. 时间索引检查
    if isinstance(df.index, pd.DatetimeIndex):
        if not df.index.is_monotonic_increasing:
            logger.warning("时间索引不单调递增，进行排序")
            if strict:
                raise DataValidationError("时间索引不单调递增")
            df = df.sort_index()
    else:
        # 尝试解析为datetime
        if hasattr(df.index, "name") and df.index.name and "date" in str(df.index.name).lower():
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                logger.warning(f"无法将索引转换为datetime: {e}")

    # 4. NaN检查
    nan_count = df[numeric_cols].isna().sum().sum()
    nan_ratio = nan_count / (len(df) * len(numeric_cols))

    if nan_ratio > max_nan_ratio:
        if strict:
            raise DataValidationError(f"NaN比率过高: {nan_ratio:.2%}")
        logger.warning(f"NaN比率: {nan_ratio:.2%}，执行前向填充")
        df = df.ffill()
        df = df.dropna()

    if nan_count > 0 and not allow_nan:
        if strict:
            raise DataValidationError(f"发现 {nan_count} 个NaN值")
        logger.warning(f"发现 {nan_count} 个NaN值，执行前向填充")
        df = df.ffill()

    # 5. 重复时间检查
    if isinstance(df.index, pd.DatetimeIndex):
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            if strict:
                raise DataValidationError(f"发现 {duplicates} 个重复时间戳")
            logger.warning(f"发现 {duplicates} 个重复时间戳，删除重复行")
            df = df[~df.index.duplicated(keep="first")]

    # 6. OHLC关系验证
    ohlc_violations = []

    # High >= Low
    invalid_hl = ~(df["high"] >= df["low"])
    if invalid_hl.any():
        ohlc_violations.append(f"high < low: {invalid_hl.sum()} 行")

    # High >= Open
    invalid_ho = ~(df["high"] >= df["open"])
    if invalid_ho.any():
        ohlc_violations.append(f"high < open: {invalid_ho.sum()} 行")

    # High >= Close
    invalid_hc = ~(df["high"] >= df["close"])
    if invalid_hc.any():
        ohlc_violations.append(f"high < close: {invalid_hc.sum()} 行")

    # Low <= Open
    invalid_lo = ~(df["low"] <= df["open"])
    if invalid_lo.any():
        ohlc_violations.append(f"low > open: {invalid_lo.sum()} 行")

    # Low <= Close
    invalid_lc = ~(df["low"] <= df["close"])
    if invalid_lc.any():
        ohlc_violations.append(f"low > close: {invalid_lc.sum()} 行")

    if ohlc_violations:
        msg = "OHLC关系违规: " + "; ".join(ohlc_violations)
        if strict:
            raise DataValidationError(msg)
        logger.warning(msg)
        # 尝试修复：调整low和high
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

    # 7. 负价格检查
    negative_prices = (df[["open", "high", "low", "close"]] < 0).any(axis=1).sum()
    if negative_prices > 0:
        if strict:
            raise DataValidationError(f"发现 {negative_prices} 个负价格值")
        logger.warning(f"发现 {negative_prices} 个负价格值，删除")
        df = df[(df[["open", "high", "low", "close"]] >= 0).all(axis=1)]

    # 8. 成交量检查
    zero_volume = (df["volume"] == 0).sum()
    if zero_volume > 0:
        logger.warning(f"发现 {zero_volume} 个零成交量K线")
        if strict and zero_volume > len(df) * 0.05:  # 如果超过5%则严格抛错
            raise DataValidationError(f"零成交量K线过多: {zero_volume}")

    negative_volume = (df["volume"] < 0).sum()
    if negative_volume > 0:
        if strict:
            raise DataValidationError(f"发现 {negative_volume} 个负成交量值")
        logger.warning(f"发现 {negative_volume} 个负成交量值，设置为0")
        df.loc[df["volume"] < 0, "volume"] = 0

    # 9. 最终检查
    if len(df) == 0:
        raise DataValidationError("验证后数据为空")

    logger.info(f"数据验证通过: {len(df)} 行，时间范围 {df.index.min() if isinstance(df.index, pd.DatetimeIndex) else 'N/A'} 到 {df.index.max() if isinstance(df.index, pd.DatetimeIndex) else 'N/A'}")

    return df


def detect_data_quality_issues(df: pd.DataFrame) -> dict[str, list[str]]:
    """
    检测数据质量问题但不抛错，返回问题列表。

    Returns
    -------
    dict
        包含各类问题的字典，键为问题类别，值为问题描述列表
    """
    issues = {
        "warnings": [],
        "errors": [],
        "info": [],
    }

    try:
        df = df.copy()
        df.columns = df.columns.str.lower().str.strip()

        # 检查必需列
        required_cols = {"open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            issues["errors"].append(f"缺少列: {sorted(missing)}")
            return issues

        numeric_cols = ["open", "high", "low", "close", "volume"]

        # NaN统计
        nan_info = df[numeric_cols].isna().sum()
        if nan_info.sum() > 0:
            issues["warnings"].append(f"存在 {nan_info.sum()} 个NaN值")

        # 重复行
        if isinstance(df.index, pd.DatetimeIndex) and df.index.duplicated().sum() > 0:
            issues["warnings"].append(f"存在 {df.index.duplicated().sum()} 个重复时间戳")

        # OHLC关系
        ohlc_issues = []
        if (~(df["high"] >= df["low"])).any():
            ohlc_issues.append(f"{(~(df['high'] >= df['low'])).sum()} 行 high<low")
        if (~(df["high"] >= df["open"])).any():
            ohlc_issues.append(f"{(~(df['high'] >= df['open'])).sum()} 行 high<open")
        if (~(df["low"] <= df["open"])).any():
            ohlc_issues.append(f"{(~(df['low'] <= df['open'])).sum()} 行 low>open")

        if ohlc_issues:
            issues["errors"].append(f"OHLC关系违规: {'; '.join(ohlc_issues)}")

        # 负值检查
        negative_prices = (df[["open", "high", "low", "close"]] < 0).any(axis=1).sum()
        if negative_prices > 0:
            issues["errors"].append(f"发现 {negative_prices} 个负价格")

        # 零/负成交量
        zero_vol = (df["volume"] == 0).sum()
        neg_vol = (df["volume"] < 0).sum()
        if zero_vol > 0:
            issues["warnings"].append(f"发现 {zero_vol} 个零成交量K线")
        if neg_vol > 0:
            issues["errors"].append(f"发现 {neg_vol} 个负成交量")

        # 单调性
        if isinstance(df.index, pd.DatetimeIndex) and not df.index.is_monotonic_increasing:
            issues["warnings"].append("时间索引不单调递增")

        # 数据范围
        issues["info"].append(f"数据行数: {len(df)}")
        if isinstance(df.index, pd.DatetimeIndex):
            issues["info"].append(f"时间范围: {df.index.min()} 至 {df.index.max()}")
        issues["info"].append(f"价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")

    except Exception as e:
        issues["errors"].append(f"检测过程出错: {e}")

    return issues
