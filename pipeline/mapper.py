"""업종 코드 매퍼 — 가맹점명 → (업종코드, 업종명)

우선순위:
1. merchant_category.csv 정확 매칭
2. keyword_rules.csv 키워드 매칭 (priority 높은 순)
3. F999 미분류
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

UNMAPPED_CODE = "F999"
UNMAPPED_NAME = "미분류"


class MerchantMapper:
    def __init__(self, category_file: Path, keyword_file: Path):
        self._exact: dict[str, tuple[str, str]] = {}
        self._keywords: list[tuple[str, str, str, int]] = []  # (keyword, code, name, priority)

        if category_file.exists():
            self._load_exact(category_file)

        if keyword_file.exists():
            self._load_keywords(keyword_file)

    def _load_exact(self, path: Path):
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = row.get("가맹점명", "").strip()
                code = row.get("업종코드", "").strip()
                cat  = row.get("업종명", "").strip()
                if name and code:
                    self._exact[name] = (code, cat)

    def _load_keywords(self, path: Path):
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kw = row.get("keyword", "").strip()
                if not kw or kw.startswith("#"):
                    continue
                code = row.get("category_code", "").strip()
                name = row.get("category_name", "").strip()
                priority = int(row.get("priority", 5))
                if kw and code:
                    self._keywords.append((kw, code, name, priority))

        # priority 내림차순 (높을수록 먼저 매칭)
        self._keywords.sort(key=lambda x: -x[3])

    def lookup(self, merchant: str) -> tuple[str, str]:
        """단일 가맹점 → (업종코드, 업종명)"""
        m = str(merchant).strip()

        # 1. 정확 매칭
        if m in self._exact:
            return self._exact[m]

        # 2. 키워드 매칭 (최고 우선순위 키워드)
        for kw, code, name, _ in self._keywords:
            if kw in m:
                return code, name

        return UNMAPPED_CODE, UNMAPPED_NAME

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame에 업종코드·업종명 컬럼 추가"""
        results = df["가맹점"].map(self.lookup)
        df = df.copy()
        df["업종코드"] = results.map(lambda x: x[0])
        df["업종명"]   = results.map(lambda x: x[1])
        return df

    def unmapped_merchants(self, df: pd.DataFrame) -> pd.DataFrame:
        """미분류 가맹점 목록 반환 (결제금액 합계 포함)"""
        unmapped = df[df["업종코드"] == UNMAPPED_CODE].copy()
        if unmapped.empty:
            return pd.DataFrame(columns=["가맹점", "캠퍼스_수", "전체_결제"])

        return (
            unmapped.groupby("가맹점")
            .agg(
                캠퍼스_수=("캠퍼스", "nunique"),
                전체_결제=("전체_결제", "sum"),
            )
            .reset_index()
            .sort_values("전체_결제", ascending=False)
        )

    def add_exact(self, merchant: str, code: str, name: str):
        """런타임에 정확 매핑 추가 (merchant_category.csv 갱신용)"""
        self._exact[merchant] = (code, name)

    def save_exact(self, path: Path):
        """현재 정확 매핑 테이블을 CSV로 저장"""
        rows = [{"가맹점명": k, "업종코드": v[0], "업종명": v[1]}
                for k, v in sorted(self._exact.items())]
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["가맹점명", "업종코드", "업종명"])
            writer.writeheader()
            writer.writerows(rows)
