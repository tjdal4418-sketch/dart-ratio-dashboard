"""비율 목록(이름·분류·단위·공식) + 계정표 → 비율표 조립.

calculations.py 는 숫자만 다루는 순수 함수이고,
이 파일은 '어떤 계정을 어떤 함수에 넣을지'와 연환산·대용치 같은 규칙을 담당한다.
"""

import inspect

import pandas as pd

from src import calculations as calc
from src.financials import REPORT_MONTHS, period_label

# key: (이름, 분류, 단위, 계산 함수)
#   공식(툴팁)은 계산 함수 docstring 의 첫 줄을 그대로 쓴다. → 공식이 코드와 화면에서 항상 같다.
RATIO_DEFS = {
    "current_ratio": ("유동비율", "안정성", "%", calc.current_ratio),
    "quick_ratio": ("당좌비율", "안정성", "%", calc.quick_ratio),
    "debt_ratio": ("부채비율", "안정성", "%", calc.debt_ratio),
    "equity_ratio": ("자기자본비율", "안정성", "%", calc.equity_ratio),
    "interest_coverage": ("이자보상배율", "안정성", "배", calc.interest_coverage),
    "operating_margin": ("매출액영업이익률", "수익성", "%", calc.operating_margin),
    "net_margin": ("매출액순이익률", "수익성", "%", calc.net_margin),
    "roe": ("ROE", "수익성", "%", calc.roe),
    "roa": ("ROA", "수익성", "%", calc.roa),
    "asset_turnover": ("총자산회전율", "활동성", "회", calc.asset_turnover),
    "receivables_turnover": ("매출채권회전율", "활동성", "회", calc.receivables_turnover),
    "inventory_turnover": ("재고자산회전율", "활동성", "회", calc.inventory_turnover),
    "revenue_growth": ("매출액증가율", "성장성", "%", calc.revenue_growth),
    "operating_income_growth": ("영업이익증가율", "성장성", "%", calc.operating_income_growth),
    "total_assets_growth": ("총자산증가율", "성장성", "%", calc.total_assets_growth),
    "ocf_to_net_income": ("영업현금흐름/순이익", "현금흐름", "배", calc.ocf_to_net_income),
}

CATEGORIES = ["안정성", "수익성", "활동성", "성장성", "현금흐름"]


def formula(key: str) -> str:
    """비율 공식 문자열 (= 계산 함수 docstring 첫 줄)"""
    return inspect.getdoc(RATIO_DEFS[key][3]).splitlines()[0]


def compute_ratios(report: dict) -> pd.DataFrame:
    """financials.fetch_report() 결과 하나 → 비율표 (행 = 비율 16개)

    규칙
      - 분기·반기: ROE·ROA·회전율의 손익(분자)은 누적값 × 12/누적개월 로 연환산
        (이익률·성장률·현금흐름 비율은 같은 기간끼리 나누므로 연환산 불필요)
      - 연결(CFS) ROE: 지배기업 소유주 귀속 순이익 ÷ 지배기업 소유주지분. 계정이 없으면 전체 기준으로 대체.
      - 이자비용이 손익계산서에 없으면 현금흐름표 '이자의 지급'을 대용치로 사용.
    """
    acc = report["accounts"]

    def cur(key):  # 당기 (재무상태표=기말)
        value = acc.loc[key, "current"]
        return None if pd.isna(value) else value

    def prior(key):  # 비교 (재무상태표=기초, 손익=전기)
        value = acc.loc[key, "prior"]
        return None if pd.isna(value) else value

    months = REPORT_MONTHS[report["reprt_code"]]
    factor = 12 / months
    annual_note = f"연환산(×12/{months})" if months != 12 else ""

    def annualize(value):
        return None if value is None else value * factor

    # ROE: 연결이면 지배기업 소유주 기준
    roe_note = ""
    roe_income, equity_key = cur("net_income"), "total_equity"
    if report["fs_div"] == "CFS":
        if cur("parent_net_income") is not None and cur("parent_equity") is not None:
            roe_income, equity_key = cur("parent_net_income"), "parent_equity"
        else:
            roe_note = "지배기업 귀속 계정이 없어 전체 순이익·자본 기준"

    # 이자비용: 없으면 '이자의 지급'(현금 기준) 대용
    interest, interest_note = cur("interest_expense"), ""
    if interest is None and cur("interest_paid") is not None:
        interest, interest_note = abs(cur("interest_paid")), "이자비용 대신 '이자의 지급'(현금기준) 사용"

    results = {
        "current_ratio": calc.current_ratio(cur("current_assets"), cur("current_liabilities")),
        "quick_ratio": calc.quick_ratio(cur("current_assets"), cur("inventories"), cur("current_liabilities")),
        "debt_ratio": calc.debt_ratio(cur("total_liabilities"), cur("total_equity")),
        "equity_ratio": calc.equity_ratio(cur("total_equity"), cur("total_assets")),
        "interest_coverage": calc.interest_coverage(cur("operating_income"), interest),
        "operating_margin": calc.operating_margin(cur("operating_income"), cur("revenue")),
        "net_margin": calc.net_margin(cur("net_income"), cur("revenue")),
        "roe": calc.roe(annualize(roe_income), prior(equity_key), cur(equity_key)),
        "roa": calc.roa(annualize(cur("net_income")), prior("total_assets"), cur("total_assets")),
        "asset_turnover": calc.asset_turnover(
            annualize(cur("revenue")), prior("total_assets"), cur("total_assets")),
        "receivables_turnover": calc.receivables_turnover(
            annualize(cur("revenue")), prior("trade_receivables"), cur("trade_receivables")),
        "inventory_turnover": calc.inventory_turnover(
            annualize(cur("revenue")), prior("inventories"), cur("inventories")),
        "revenue_growth": calc.revenue_growth(cur("revenue"), prior("revenue")),
        "operating_income_growth": calc.operating_income_growth(
            cur("operating_income"), prior("operating_income")),
        "total_assets_growth": calc.total_assets_growth(cur("total_assets"), prior("total_assets")),
        "ocf_to_net_income": calc.ocf_to_net_income(cur("operating_cash_flow"), cur("net_income")),
    }

    # 값이 계산된 경우에만 붙는 참고 사항
    extra_notes = {"roe": [roe_note], "interest_coverage": [interest_note]}
    for key in ["roe", "roa", "asset_turnover", "receivables_turnover", "inventory_turnover"]:
        extra_notes.setdefault(key, []).append(annual_note)
    if months != 12:
        # 분기 재무상태표의 비교값은 '전년 같은 분기말'이 아니라 '전기말'이다.
        extra_notes["total_assets_growth"] = ["전기말 대비"]

    rows = []
    for key, (name, category, unit, _) in RATIO_DEFS.items():
        result = results[key]
        notes = [result.note]
        if result.value is not None:
            notes += extra_notes.get(key, [])
        rows.append({
            "key": key, "name": name, "category": category, "unit": unit,
            "value": result.value,
            "note": " · ".join(n for n in notes if n),
            "formula": formula(key),
        })
    return pd.DataFrame(rows).set_index("key")



def ratio_trend(reports: list[dict]) -> pd.DataFrame:
    """여러 기간의 보고서 → 추이표 (긴 형식: 기간 × 비율 한 행씩). 차트와 CSV 에 쓴다."""
    frames = []
    for report in reports:
        table = compute_ratios(report).reset_index()
        table["period"] = period_label(report["year"], report["reprt_code"])
        table["year"] = report["year"]
        table["fs_div"] = report["fs_div"]
        frames.append(table)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def compare_ratios(trends: dict[str, pd.DataFrame], year: int) -> pd.DataFrame:
    """기업별 추이표 {회사명: ratio_trend 결과} → 기준연도의 비교표 (긴 형식, company 열 추가).
    기준연도 보고서가 없는 회사는 빠진다."""
    frames = []
    for company, trend in trends.items():
        if trend.empty:
            continue
        part = trend[trend["year"] == year].copy()
        part.insert(0, "company", company)
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

if __name__ == "__main__":
    # 실행 예)  python -m src.ratios 삼성전자 2025 11011
    import sys

    from src.corp_code import load_listed_companies, search_companies
    from src.financials import FS_NAMES, REPORT_NAMES, fetch_report

    name = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    reprt = sys.argv[3] if len(sys.argv) > 3 else "11011"

    corp = search_companies(load_listed_companies(), name).iloc[0]
    report = fetch_report(corp["corp_code"], year, reprt)
    print(f"{corp['corp_name']} {year}년 {REPORT_NAMES[reprt]} · {FS_NAMES[report['fs_div']]}")
    table = compute_ratios(report)
    table["value"] = table["value"].map(lambda v: "-" if pd.isna(v) else f"{v:,.2f}")
    pd.set_option("display.width", 200)
    print(table[["category", "name", "value", "unit", "note"]].to_string(index=False))
