"""DART 재무비율 대시보드 — Streamlit 화면.

실행:  streamlit run app.py

화면 구성
  사이드바   회사 검색 · 기준연도 · 보고서 종류 · 연결/별도 · 추이 기간
  ① 회사 정보와 경고 (별도 대체, 금융업, 상장폐지)
  ② 요약 카드 (핵심 비율 6개 + 전년 대비 증감)
  ③ 분류별 탭 (추이 차트 + 표)
  ④ 원본 데이터 (계산에 쓴 계정과 금액, CSV 다운로드)
  ⑤ 데이터 출처와 기준일

이 파일은 화면만 담당하고, 계산은 src/ 의 함수를 불러 쓴다.
"""

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.corp_code import load_listed_companies, search_companies
from src.dart_client import DartApiError
from src.financials import FS_NAMES, REPORT_NAMES, fetch_company, fetch_reports, period_label
from src.industry import MARKET_NAMES, is_financial
from src.ratios import CATEGORIES, ratio_trend

st.set_page_config(page_title="DART 재무비율 대시보드", page_icon="📊", layout="wide")

REPORT_ORDER = ["11011", "11013", "11012", "11014"]  # 사업 · 1분기 · 반기 · 3분기
SERIES_COLOR = "#2a78d6"  # 단일 계열 선 색 (색각이상 검증된 팔레트의 1번)
SUMMARY_KEYS = ["debt_ratio", "current_ratio", "operating_margin", "roe", "revenue_growth", "interest_coverage"]
LOWER_IS_BETTER = {"debt_ratio"}  # 낮을수록 좋은 비율 → 증감 색을 반대로
FIRST_YEAR = 2015  # OpenDART 재무제표 API 제공 시작 연도


# ── 데이터 불러오기 (st.cache_data: 같은 입력이면 다시 계산하지 않음) ──────────
@st.cache_data(ttl=86400, show_spinner="상장사 목록을 불러오는 중...")
def get_companies():
    return load_listed_companies()


@st.cache_data(ttl=86400, show_spinner=False)
def get_company(corp_code):
    return fetch_company(corp_code)


@st.cache_data(show_spinner="재무제표를 불러오는 중...")
def get_reports(corp_code, end_year, reprt_code, n_years, fs_pref):
    return fetch_reports(corp_code, end_year, reprt_code, n_years, fs_pref)


def fmt(value, unit):
    """화면 표시용 숫자 형식"""
    if value is None or pd.isna(value):
        return "-"
    if unit == "%":
        return f"{value:,.1f}%"
    return f"{value:,.2f}{unit}"


# ── 사이드바 ─────────────────────────────────────────────────────────────
def sidebar():
    st.sidebar.header("🔍 조회 조건")
    query = st.sidebar.text_input("회사명 또는 종목코드", value="삼성전자",
                                  help="띄어쓰기·대소문자 무시, 6자리 숫자는 종목코드로 검색")
    results = search_companies(get_companies(), query, limit=30)
    if results.empty:
        st.sidebar.warning("검색 결과가 없습니다. 정식 회사명으로 검색해 보세요. (예: 현대차 → 현대자동차)")
        st.stop()
    labels = [f"{r.corp_name} ({r.stock_code})" for r in results.itertuples()]
    index = st.sidebar.selectbox("회사 선택", range(len(results)), format_func=lambda i: labels[i])
    corp = results.iloc[index]

    this_year = dt.date.today().year
    years = list(range(this_year, FIRST_YEAR - 1, -1))
    year = st.sidebar.selectbox("기준연도", years, index=1, help="사업연도 기준")
    reprt_code = st.sidebar.radio("보고서 종류", REPORT_ORDER, format_func=REPORT_NAMES.get)
    fs_pref = st.sidebar.radio("재무제표", ["CFS", "OFS"], horizontal=True,
                               format_func=lambda x: FS_NAMES[x],
                               help="연결을 선택했는데 연결재무제표가 없으면 별도로 자동 대체합니다.")
    n_years = st.sidebar.slider("추이 기간(년)", 3, 5, 5)
    return corp, year, reprt_code, fs_pref, n_years


# ── ① 회사 정보와 경고 ──────────────────────────────────────────────────
def show_header(corp, info, reports, fs_pref, n_years):
    latest = reports[-1]
    market = MARKET_NAMES.get(info.get("corp_cls"), "-")
    st.title(corp["corp_name"])
    st.caption(
        f"종목코드 {corp['stock_code']} · {market} · 업종코드 {info.get('induty_code', '-')} · "
        f"{period_label(latest['year'], latest['reprt_code'])} {REPORT_NAMES[latest['reprt_code']]} · "
        f"**{FS_NAMES[latest['fs_div']]}재무제표**"
    )

    fallback_periods = [period_label(r["year"], r["reprt_code"]) for r in reports if r["fallback"]]
    if fallback_periods:
        st.info(f"ℹ️ 연결재무제표가 없어 **별도재무제표로 대체**한 기간: {', '.join(fallback_periods)}")
    found = {r["year"] for r in reports}
    skipped = [str(y) for y in range(latest["year"] - n_years + 1, latest["year"]) if y not in found]
    if skipped:
        st.info(f"ℹ️ OpenDART에 재무제표 데이터가 없어 제외한 연도: {', '.join(skipped)}")
    if fs_pref == "CFS" and len({r["fs_div"] for r in reports}) > 1:
        st.caption("※ 기간마다 연결/별도가 달라 추이 비교 시 주의가 필요합니다.")
    if info.get("corp_cls") == "E":
        st.warning("⚠️ 현재 상장사가 아닙니다(상장폐지 등). 과거 데이터만 있을 수 있습니다.")
    if is_financial(info.get("induty_code"), info.get("corp_name", "")):
        st.warning(
            "⚠️ **금융업**(은행·보험·증권·금융지주)입니다. 재무상태표에 유동/비유동 구분이 없고 "
            "매출 구조가 달라 유동비율·영업이익률 등 일반 비율이 적합하지 않습니다. "
            "(금융업은 BIS 비율, 지급여력비율, NIM 등 업종 전용 지표로 분석합니다)"
        )


# ── ② 요약 카드 ──────────────────────────────────────────────────────────
def show_summary(trend, reports):
    latest = reports[-1]
    current = trend[trend["year"] == latest["year"]].set_index("key")
    previous = trend[trend["year"] == latest["year"] - 1].set_index("key")

    st.subheader("요약", help="전년 같은 보고서 대비 증감 (%p = 퍼센트포인트)")
    cols = st.columns(3) + st.columns(3)  # 3개씩 2줄 (값이 잘리지 않도록)
    for col, key in zip(cols, SUMMARY_KEYS):
        row = current.loc[key]
        delta = None
        if key in previous.index and pd.notna(row["value"]) and pd.notna(previous.loc[key, "value"]):
            diff = row["value"] - previous.loc[key, "value"]
            delta = f"{diff:+,.1f}%p" if row["unit"] == "%" else f"{diff:+,.2f}{row['unit']}"
        col.metric(row["name"], fmt(row["value"], row["unit"]), delta,
                   delta_color="inverse" if key in LOWER_IS_BETTER else "normal",
                   help=row["formula"], border=True)
        if row["note"]:
            col.caption(row["note"])


# ── ③ 분류별 탭 ──────────────────────────────────────────────────────────
def line_chart(data, unit):
    """한 비율의 기간별 추이 (선 1개). 값이 없는 기간은 선이 끊긴다."""
    values = data["value"].tolist()
    # 마지막 값에만 직접 라벨 (모든 점에 숫자를 달면 복잡해진다)
    last_index = max((i for i, v in enumerate(values) if pd.notna(v)), default=None)
    labels = [fmt(v, unit) if i == last_index else "" for i, v in enumerate(values)]

    # pandas 3 의 문자열 타입 대신 파이썬 리스트로 넘긴다.
    fig = go.Figure(go.Scatter(
        x=data["period"].tolist(), y=values,
        mode="lines+markers+text", text=labels, textposition="top center",
        line=dict(color=SERIES_COLOR, width=2),
        marker=dict(size=8, color=SERIES_COLOR),
        customdata=data["note"].tolist(),
        hovertemplate="%{x}<br><b>%{y:,.2f}" + unit + "</b><br>%{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=240, margin=dict(l=8, r=8, t=24, b=8), showlegend=False,
        xaxis=dict(type="category", showgrid=False),
        yaxis=dict(ticksuffix="%" if unit == "%" else "", gridcolor="rgba(128,128,128,0.18)",
                   zeroline=True, zerolinecolor="rgba(128,128,128,0.35)"),
    )
    return fig


def show_category_tabs(trend):
    st.subheader("분류별 추이")
    for tab, category in zip(st.tabs(CATEGORIES), CATEGORIES):
        with tab:
            part = trend[trend["category"] == category]
            keys = list(dict.fromkeys(part["key"]))  # 순서 유지한 중복 제거
            cols = st.columns(2)
            for i, key in enumerate(keys):
                data = part[part["key"] == key]
                first = data.iloc[0]
                with cols[i % 2]:
                    st.markdown(f"**{first['name']}**", help=first["formula"])
                    if data["value"].isna().all():
                        st.info("계산할 수 없습니다: " + (data["note"].iloc[-1] or "데이터 없음"))
                    else:
                        st.plotly_chart(line_chart(data, first["unit"]), width="stretch",
                                        config={"displayModeBar": False}, key=f"chart_{key}")

            # 표 보기: 행 = 비율, 열 = 기간 (+ 최근 기간 비고)
            table = part.assign(display=[fmt(v, u) for v, u in zip(part["value"], part["unit"])])
            pivot = table.pivot(index="name", columns="period", values="display").reindex(
                list(dict.fromkeys(part["name"])))
            latest_period = part["period"].iloc[-1]
            notes = part[part["period"] == latest_period].set_index("name")["note"]
            pivot[f"비고({latest_period})"] = notes
            pivot = pivot.rename_axis(index="비율", columns=None)
            st.dataframe(pivot, width="stretch")


# ── ④ 원본 데이터 ────────────────────────────────────────────────────────
ACCOUNT_COLUMNS = {
    "period": "기간", "label": "계정", "current": "당기(기말)", "prior": "비교(기초·전기)",
    "current_3m": "당기 3개월", "sj_div": "재무제표", "account_nm": "공시 계정명",
    "account_id": "표준계정코드", "matched_by": "매칭 방법", "fs_div": "연결/별도",
}


def show_raw_data(reports, trend, corp_name):
    st.subheader("원본 데이터", help="비율 계산에 사용한 계정과 금액(원)")
    frames = []
    for r in reports:
        accounts = r["accounts"].reset_index(drop=True)
        accounts.insert(0, "period", period_label(r["year"], r["reprt_code"]))
        accounts["fs_div"] = FS_NAMES[r["fs_div"]]
        frames.append(accounts)
    all_accounts = pd.concat(frames, ignore_index=True)[list(ACCOUNT_COLUMNS)].rename(columns=ACCOUNT_COLUMNS)

    periods = list(dict.fromkeys(all_accounts["기간"]))
    chosen = st.selectbox("기간 선택", periods, index=len(periods) - 1)
    view = all_accounts[all_accounts["기간"] == chosen].drop(columns=["기간"])
    view = view.dropna(axis=1, how="all")  # 사업보고서에는 '당기 3개월' 칸이 비어 있으므로 숨긴다.
    st.dataframe(
        view, width="stretch", hide_index=True,
        column_config={c: st.column_config.NumberColumn(format="localized")
                       for c in ["당기(기말)", "비교(기초·전기)", "당기 3개월"]},
    )

    # utf-8-sig: 엑셀에서 한글이 깨지지 않도록 BOM 을 붙인다.
    col1, col2 = st.columns(2)
    col1.download_button("⬇️ 계정 원본 CSV (전체 기간)",
                         all_accounts.to_csv(index=False).encode("utf-8-sig"),
                         file_name=f"{corp_name}_계정원본.csv", mime="text/csv")
    ratio_csv = trend[["period", "category", "name", "value", "unit", "note", "formula"]].rename(
        columns={"period": "기간", "category": "분류", "name": "비율", "value": "값",
                 "unit": "단위", "note": "비고", "formula": "공식"})
    col2.download_button("⬇️ 비율 추이 CSV",
                         ratio_csv.to_csv(index=False).encode("utf-8-sig"),
                         file_name=f"{corp_name}_재무비율.csv", mime="text/csv")


# ── ⑤ 출처와 기준일 ─────────────────────────────────────────────────────
def show_footer(reports):
    st.divider()
    latest = reports[-1]
    rcept_no = latest["rcept_no"]
    # 접수번호 앞 8자리 = 공시 접수일(YYYYMMDD)
    filed = f"{rcept_no[:4]}-{rcept_no[4:6]}-{rcept_no[6:8]}" if len(rcept_no) >= 8 else "-"
    links = " · ".join(
        f"[{period_label(r['year'], r['reprt_code'])}](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']})"
        for r in reports
    )
    st.caption(
        f"데이터 출처: 금융감독원 전자공시시스템 [OpenDART](https://opendart.fss.or.kr) · "
        f"기준: {period_label(latest['year'], latest['reprt_code'])} {REPORT_NAMES[latest['reprt_code']]} "
        f"(공시 접수일 {filed}) · 조회일 {dt.date.today():%Y-%m-%d}  \n"
        f"공시 원문: {links}"
    )


# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    corp, year, reprt_code, fs_pref, n_years = sidebar()
    try:
        info = get_company(corp["corp_code"])
        reports = get_reports(corp["corp_code"], year, reprt_code, n_years, fs_pref)
    except DartApiError as e:
        st.error(f"OpenDART 조회 중 오류가 발생했습니다: {e}")
        st.stop()

    if not reports or reports[-1]["year"] != year:
        st.title(corp["corp_name"])
        if info.get("corp_cls") == "E":
            st.warning("⚠️ 현재 상장사가 아닙니다(상장폐지 등). 상장 기간의 연도를 선택해 보세요.")
        st.warning(f"{year}년 {REPORT_NAMES[reprt_code]}가 없습니다. "
                   "아직 제출 전이거나, 상장 전·상장폐지 후 기간일 수 있습니다. 기준연도를 바꿔 보세요.")
        st.stop()

    trend = ratio_trend(reports)
    show_header(corp, info, reports, fs_pref, n_years)
    show_summary(trend, reports)
    show_category_tabs(trend)
    show_raw_data(reports, trend, corp["corp_name"])
    show_footer(reports)


main()
