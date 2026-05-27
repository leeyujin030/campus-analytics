"""집계 모듈 — 날짜/캠퍼스/가맹점/업종 축 기준 집계"""
from __future__ import annotations

import pandas as pd

PAY_TYPES = ["카드", "식권", "쿠폰", "승차권"]


def _agg(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    agg_map = {
        "전체_주문": "sum", "전체_결제": "sum",
        "카드_주문": "sum",  "카드_결제": "sum",
        "식권_주문": "sum",  "식권_결제": "sum",
        "쿠폰_주문": "sum",  "쿠폰_결제": "sum",
        "승차권_주문": "sum", "승차권_결제": "sum",
    }
    result = df.groupby(group_cols, dropna=False).agg(agg_map).reset_index()
    return result.sort_values("전체_결제", ascending=False)


def summary(df: pd.DataFrame) -> dict:
    """전체 KPI 요약"""
    total = df["전체_결제"].sum()
    orders = df["전체_주문"].sum()
    campuses = df["캠퍼스"].nunique()
    merchants = df["가맹점"].nunique()

    # 결제 유형별 비중
    pay_breakdown = {}
    for pt in PAY_TYPES:
        amt = df[f"{pt}_결제"].sum()
        pay_breakdown[pt] = {"금액": int(amt), "비중": round(amt / total * 100, 1) if total else 0}

    return {
        "총_결제금액": int(total),
        "총_주문건수": int(orders),
        "캠퍼스_수": int(campuses),
        "가맹점_수": int(merchants),
        "결제유형별": pay_breakdown,
    }


def by_campus(df: pd.DataFrame) -> pd.DataFrame:
    """캠퍼스별 집계 (결제금액 내림차순)"""
    return _agg(df, ["캠퍼스"])


def by_campus_date(df: pd.DataFrame) -> pd.DataFrame:
    """캠퍼스 × 날짜 집계"""
    return _agg(df, ["날짜", "캠퍼스"])


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    """업종별 집계"""
    result = _agg(df, ["업종코드", "업종명"])
    total = result["전체_결제"].sum()
    result["비중(%)"] = (result["전체_결제"] / total * 100).round(1) if total else 0
    result["가맹점_수"] = df.groupby(["업종코드"])["가맹점"].nunique().reindex(
        result["업종코드"]
    ).values
    return result


def by_merchant(df: pd.DataFrame) -> pd.DataFrame:
    """가맹점별 집계 (업종코드 포함)"""
    return _agg(df, ["캠퍼스", "가맹점", "업종코드", "업종명"])


def daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    """날짜별 추이 (전체 기간)"""
    result = _agg(df, ["날짜"])
    result = result.sort_values("날짜")
    total = result["전체_결제"]
    result["전일대비(%)"] = total.pct_change().mul(100).round(1)
    return result


def campus_category(df: pd.DataFrame) -> pd.DataFrame:
    """캠퍼스 × 업종별 집계"""
    return _agg(df, ["캠퍼스", "업종코드", "업종명"])
