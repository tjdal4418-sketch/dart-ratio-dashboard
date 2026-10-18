"""ratios.compute_ratios 테스트: 연환산, 연결 ROE, 이자비용 대용치, 공식 문자열"""

import pandas as pd
import pytest

from src.account_map import ACCOUNT_MAP
from src.ratios import RATIO_DEFS, compute_ratios, formula


def make_report(values: dict, reprt_code="11011", fs_div="CFS"):
    """values = {계정 key: (당기, 비교)} 로 가짜 fetch_report 결과를 만든다."""
    accounts = pd.DataFrame(
        [{"key": k, "current": values.get(k, (None, None))[0], "prior": values.get(k, (None, None))[1]}
         for k in ACCOUNT_MAP]
    ).set_index("key")
    return {"reprt_code": reprt_code, "fs_div": fs_div, "accounts": accounts}


BASE = {
    "total_assets": (1100, 900),
    "current_assets": (400, 350),
    "inventories": (100, 80),
    "trade_receivables": (140, 100),
    "current_liabilities": (200, 180),
    "total_liabilities": (500, 400),
    "total_equity": (600, 500),
    "parent_equity": (550, 450),
    "revenue": (1500, 1200),
    "operating_income": (150, 100),
    "net_income": (110, 90),
    "parent_net_income": (100, 80),
    "operating_cash_flow": (165, 120),
    "interest_paid": (-30, -20),
}


def test_16개_비율이_모두_나온다():
    assert len(compute_ratios(make_report(BASE))) == 16


def test_연결_ROE는_지배기업_기준():
    # 100 / ((450 + 550) / 2) = 20%
    assert compute_ratios(make_report(BASE)).loc["roe", "value"] == pytest.approx(20.0)


def test_별도_ROE는_전체_기준():
    # 110 / ((500 + 600) / 2) = 20%
    r = compute_ratios(make_report(BASE, fs_div="OFS"))
    assert r.loc["roe", "value"] == pytest.approx(20.0)
    assert r.loc["roe", "note"] == ""


def test_연결인데_지배기업계정_없으면_대체하고_표시():
    values = {k: v for k, v in BASE.items() if k != "parent_net_income"}
    r = compute_ratios(make_report(values))
    assert r.loc["roe", "value"] == pytest.approx(20.0)
    assert "전체 순이익" in r.loc["roe", "note"]


def test_이자비용_없으면_이자의지급_대용():
    r = compute_ratios(make_report(BASE))
    assert r.loc["interest_coverage", "value"] == pytest.approx(5.0)  # 150 / |-30|
    assert "이자의 지급" in r.loc["interest_coverage", "note"]


def test_이자비용_있으면_이자비용_우선():
    values = {**BASE, "interest_expense": (50, 40)}
    r = compute_ratios(make_report(values))
    assert r.loc["interest_coverage", "value"] == pytest.approx(3.0)
    assert r.loc["interest_coverage", "note"] == ""


def test_3분기는_손익을_12_9로_연환산():
    r = compute_ratios(make_report(BASE, reprt_code="11014"))
    # ROA = 110 × 12/9 / 1000 × 100
    assert r.loc["roa", "value"] == pytest.approx(110 * 12 / 9 / 1000 * 100)
    assert "연환산" in r.loc["roa", "note"]
    # 이익률은 연환산하지 않는다
    assert r.loc["operating_margin", "value"] == pytest.approx(10.0)
    assert r.loc["operating_margin", "note"] == ""
    assert r.loc["total_assets_growth", "note"] == "전기말 대비"


def test_자본잠식이면_None과_사유():
    values = {**BASE, "total_equity": (-100, -50)}
    r = compute_ratios(make_report(values, fs_div="OFS"))
    assert pd.isna(r.loc["debt_ratio", "value"])
    assert "자본잠식" in r.loc["debt_ratio", "note"]


def test_공식은_docstring_첫줄():
    assert formula("current_ratio") == "유동비율 = 유동자산 ÷ 유동부채 × 100"
    for key in RATIO_DEFS:
        assert "=" in formula(key)
