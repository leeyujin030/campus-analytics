"""BIP 엑셀 파일 파서 — 캠퍼스_PAYCO_일일상세결제_*.xlsx"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd

BIP_PATTERN = re.compile(r"캠퍼스_PAYCO_일일상세결제_.*\.xlsx$", re.IGNORECASE)

COLS = [
    "_", "날짜", "캠퍼스", "가맹점",
    "전체_주문", "전체_결제",
    "카드_주문", "카드_결제",
    "식권_주문", "식권_결제",
    "쿠폰_주문", "쿠폰_결제",
    "승차권_주문", "승차권_결제",
]

NUMERIC_COLS = [c for c in COLS if c not in ("_", "날짜", "캠퍼스", "가맹점")]


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def is_bip_file(path: Path) -> bool:
    return bool(BIP_PATTERN.search(_nfc(path.name)))


def find_latest_bip(folder: Path) -> Optional[Path]:
    """폴더에서 가장 최근에 수정된 BIP 파일 반환 (임시파일 ~$ 제외)"""
    candidates = [
        p for p in folder.iterdir()
        if p.is_file() and not p.name.startswith("~") and is_bip_file(p)
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _clean(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.shape[1] < 14:
        raise ValueError(f"컬럼 수 불일치: {raw.shape[1]}개 (14개 예상) — 파일 형식 변경 여부 확인")
    raw = raw.iloc[:, :14].copy()
    raw.columns = COLS
    df = raw.dropna(subset=["날짜", "캠퍼스"]).copy()
    df["날짜"] = df["날짜"].astype(str).str.strip().str[:8]
    df = df[df["날짜"].str.match(r"^\d{8}$")]
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df.drop(columns=["_"]).reset_index(drop=True)


def parse_bytes(data: bytes) -> pd.DataFrame:
    """바이트 데이터(파일 업로드)에서 파싱"""
    import io
    raw = pd.read_excel(io.BytesIO(data), sheet_name="일일상세결제", header=None, skiprows=4)
    return _clean(raw)


def parse(path: Path) -> pd.DataFrame:
    """BIP 엑셀을 읽어 정제된 DataFrame 반환"""
    raw = pd.read_excel(path, sheet_name="일일상세결제", header=None, skiprows=4)
    return _clean(raw)


def filter_by_date(df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, str]:
    """
    target: "latest" | "all" | "YYYYMMDD"
    반환: (필터된 df, 실제 날짜 문자열)
    """
    if target == "all":
        label = f"{df['날짜'].min()}~{df['날짜'].max()}"
        return df, label

    if target == "latest":
        date_str = df["날짜"].max()
    else:
        date_str = target.strip()

    filtered = df[df["날짜"] == date_str]
    if filtered.empty:
        available = sorted(df["날짜"].unique())
        raise ValueError(
            f"날짜 '{date_str}' 데이터 없음. "
            f"사용 가능한 날짜: {available[-5:]} (최근 5개)"
        )

    return filtered, date_str
