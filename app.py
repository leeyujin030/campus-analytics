"""캠퍼스 데일리 애널리틱스 — Streamlit 웹 대시보드"""
import io
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from pipeline import aggregator, mapper, parser

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="캠퍼스 데일리 애널리틱스",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .kpi-card {
        background: #1E3A5F; color: white;
        border-radius: 12px; padding: 20px 24px;
        text-align: center;
    }
    .kpi-label { font-size: 13px; opacity: 0.75; margin-bottom: 4px; }
    .kpi-value { font-size: 28px; font-weight: 700; }
    .kpi-sub   { font-size: 12px; opacity: 0.6; margin-top: 4px; }
    .section-title { font-size: 16px; font-weight: 600; color: #1E3A5F; margin: 24px 0 8px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_mapper():
    data_dir = ROOT / "data"
    return mapper.MerchantMapper(
        category_file=data_dir / "merchant_category.csv",
        keyword_file=data_dir / "keyword_rules.csv",
    )


@st.cache_data(show_spinner="BIP 파일 파싱 중...")
def load_data(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    df = parser.parse_bytes(file_bytes)
    mp = load_mapper()
    return mp.apply(df)


def fmt_money(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}백만원"
    return f"{v:,.0f}원"


def fmt_num(v):
    return f"{int(v):,}"


# ══════════════════════════════════════════════════════════════
# 사이드바
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("📊 캠퍼스 애널리틱스")
    st.divider()

    uploaded = st.file_uploader(
        "BIP 파일 업로드",
        type=["xlsx"],
        help="캠퍼스_PAYCO_일일상세결제_*.xlsx 파일을 올려주세요",
    )

    if not uploaded:
        st.info("BIP 파일을 업로드하면 분석이 시작됩니다.")
        st.stop()

    df_all = load_data(uploaded.getvalue(), uploaded.name)
    available_dates = sorted(df_all["날짜"].unique(), reverse=True)

    st.divider()

    date_mode = st.radio("날짜", ["최신 하루", "날짜 선택", "전체 기간"])
    if date_mode == "최신 하루":
        selected_dates = [available_dates[0]]
    elif date_mode == "날짜 선택":
        d = st.selectbox("날짜 선택", available_dates)
        selected_dates = [d]
    else:
        selected_dates = available_dates

    date_label = (
        selected_dates[0]
        if len(selected_dates) == 1
        else f"{selected_dates[-1]}~{selected_dates[0]}"
    )

    st.divider()
    all_campuses = sorted(df_all["캠퍼스"].dropna().unique())
    campus_filter = st.multiselect("캠퍼스 필터 (미선택 = 전체)", all_campuses)

    st.divider()
    st.caption(f"파일: {uploaded.name}")


# ── 필터 적용 ─────────────────────────────────────────────────
df = df_all[df_all["날짜"].isin(selected_dates)]
if campus_filter:
    df = df[df["캠퍼스"].isin(campus_filter)]

if df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

mp = load_mapper()
df_unmapped = mp.unmapped_merchants(df)
kpi        = aggregator.summary(df)
df_campus  = aggregator.by_campus(df)
df_cat     = aggregator.by_category(df)
df_merch   = aggregator.by_merchant(df)
df_trend   = aggregator.daily_trend(df)


# ══════════════════════════════════════════════════════════════
# 헤더
# ══════════════════════════════════════════════════════════════
col_title, col_badge = st.columns([5, 1])
with col_title:
    st.markdown(f"## 캠퍼스 데일리 리포트 · `{date_label}`")
with col_badge:
    if len(df_unmapped) > 0:
        st.warning(f"미분류 {len(df_unmapped)}개")

st.divider()

# ══════════════════════════════════════════════════════════════
# KPI 카드
# ══════════════════════════════════════════════════════════════
k1, k2, k3, k4 = st.columns(4)

def kpi_card(col, label, value):
    col.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

kpi_card(k1, "총 결제금액", fmt_money(kpi["총_결제금액"]))
kpi_card(k2, "총 주문건수", fmt_num(kpi["총_주문건수"]) + "건")
kpi_card(k3, "캠퍼스 수", fmt_num(kpi["캠퍼스_수"]) + "개")
kpi_card(k4, "가맹점 수", fmt_num(kpi["가맹점_수"]) + "개")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 차트 행 1 — 업종별 파이 + 결제유형별 막대
# ══════════════════════════════════════════════════════════════
c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="section-title">업종별 결제금액</div>', unsafe_allow_html=True)
    fig_cat = px.pie(
        df_cat, names="업종명", values="전체_결제",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_cat.update_traces(textposition="inside", textinfo="percent+label")
    fig_cat.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=320)
    st.plotly_chart(fig_cat, use_container_width=True)

with c2:
    st.markdown('<div class="section-title">결제유형별 비중</div>', unsafe_allow_html=True)
    df_pay = pd.DataFrame({
        "결제유형": list(kpi["결제유형별"].keys()),
        "금액": [v["금액"] for v in kpi["결제유형별"].values()],
        "비중": [v["비중"] for v in kpi["결제유형별"].values()],
    })
    fig_pay = px.bar(
        df_pay, x="결제유형", y="금액",
        text=df_pay["비중"].map(lambda x: f"{x}%"),
        color="결제유형",
        color_discrete_sequence=["#1D6DE5", "#E94560", "#16A34A", "#F59E0B"],
    )
    fig_pay.update_traces(textposition="outside")
    fig_pay.update_layout(
        showlegend=False, margin=dict(t=20, b=0, l=0, r=0), height=320,
        yaxis_title="결제금액 (원)", xaxis_title="",
    )
    st.plotly_chart(fig_pay, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# 캠퍼스 상위 15
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">캠퍼스별 결제금액 (상위 15)</div>', unsafe_allow_html=True)
top_campus = df_campus.head(15).sort_values("전체_결제")
fig_campus = px.bar(
    top_campus, x="전체_결제", y="캠퍼스", orientation="h",
    text=top_campus["전체_결제"].map(fmt_money),
    color="전체_결제",
    color_continuous_scale=["#CADCFC", "#1E3A5F"],
)
fig_campus.update_traces(textposition="outside")
fig_campus.update_layout(
    coloraxis_showscale=False,
    margin=dict(t=0, b=0, l=0, r=120), height=420,
    xaxis_title="결제금액 (원)", yaxis_title="",
)
st.plotly_chart(fig_campus, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# 일별 추이
# ══════════════════════════════════════════════════════════════
if len(df_trend) > 1:
    st.markdown('<div class="section-title">일별 결제금액 추이</div>', unsafe_allow_html=True)
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=df_trend["날짜"], y=df_trend["전체_결제"],
        mode="lines+markers",
        line=dict(color="#1D6DE5", width=2.5),
        marker=dict(size=6),
        hovertemplate="%{x}<br>%{y:,.0f}원<extra></extra>",
    ))
    fig_trend.update_layout(
        margin=dict(t=0, b=0, l=0, r=0), height=280,
        xaxis_title="날짜", yaxis_title="결제금액 (원)",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# 상세 테이블 탭
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">상세 데이터</div>', unsafe_allow_html=True)
tab1, tab2, tab3, tab4 = st.tabs(["캠퍼스별", "업종별", "가맹점별", "⚠️ 미분류 알림"])

with tab1:
    st.dataframe(df_campus, use_container_width=True, hide_index=True)

with tab2:
    st.dataframe(df_cat, use_container_width=True, hide_index=True)

with tab3:
    search = st.text_input("가맹점명 검색", placeholder="예: 스타벅스")
    df_show = df_merch[df_merch["가맹점"].str.contains(search, na=False)] if search else df_merch
    st.dataframe(df_show, use_container_width=True, hide_index=True)

with tab4:
    if df_unmapped.empty:
        st.success("미분류 가맹점 없음 — 모든 가맹점이 매핑되었습니다.")
    else:
        st.warning(f"총 {len(df_unmapped)}개 가맹점이 업종 미분류입니다.")
        st.dataframe(df_unmapped, use_container_width=True, hide_index=True)
        csv = df_unmapped.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSV 다운로드", csv, "미분류_가맹점.csv", "text/csv")
