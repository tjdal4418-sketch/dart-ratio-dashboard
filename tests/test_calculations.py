"""calculations.py 단위 테스트: 정상값 / 분모 0 / 음수 자본(자본잠식) / 데이터 없음"""

import pytest

from src import calculations as calc


# ── 안정성 ───────────────────────────────────────────────
def test_유동비율_정상():
    assert calc.current_ratio(200, 100).value == pytest.approx(200.0)


def test_유동비율_분모0():
    r = calc.current_ratio(200, 0)
    assert r.value is None and r.note == "분모가 0"


def test_유동비율_데이터없음():
    r = calc.current_ratio(None, 100)
    assert r.value is None and "유동자산" in r.note


def test_당좌비율_정상():
    # (200 - 50) / 100 = 150%
    assert calc.quick_ratio(200, 50, 100).value == pytest.approx(150.0)


def test_당좌비율_재고없는_회사는_재고0():
    assert calc.quick_ratio(200, None, 100).value == pytest.approx(200.0)


def test_부채비율_정상():
    assert calc.debt_ratio(300, 200).value == pytest.approx(150.0)


def test_부채비율_자본잠식():
    r = calc.debt_ratio(300, -50)
    assert r.value is None and "자본잠식" in r.note


def test_부채비율_자본0():
    assert calc.debt_ratio(300, 0).value is None


def test_자기자본비율_자본잠식이면_음수값_그대로():
    # 분모(자산총계)가 양수라 계산 가능. 음수 비율 자체가 자본잠식 정보다.
    assert calc.equity_ratio(-50, 500).value == pytest.approx(-10.0)


def test_이자보상배율_정상():
    assert calc.interest_coverage(500, 100).value == pytest.approx(5.0)


def test_이자보상배율_영업손실이면_음수배율():
    assert calc.interest_coverage(-200, 100).value == pytest.approx(-2.0)


def test_이자보상배율_이자비용0():
    r = calc.interest_coverage(500, 0)
    assert r.value is None and "이자비용이 0" in r.note


def test_이자보상배율_이자비용_음수표기도_크기로_계산():
    assert calc.interest_coverage(500, -100).value == pytest.approx(5.0)


# ── 수익성 ───────────────────────────────────────────────
def test_영업이익률_정상():
    assert calc.operating_margin(50, 1000).value == pytest.approx(5.0)


def test_영업이익률_매출0():
    assert calc.operating_margin(50, 0).value is None


def test_순이익률_순손실이면_음수():
    assert calc.net_margin(-30, 1000).value == pytest.approx(-3.0)


def test_ROE_평균자본_사용():
    # 평균 자본 = (80 + 120) / 2 = 100 → 10 / 100 = 10%
    assert calc.roe(10, 80, 120).value == pytest.approx(10.0)


def test_ROE_자본잠식():
    r = calc.roe(10, -100, -20)
    assert r.value is None and "자본잠식" in r.note


def test_ROE_평균자본0():
    r = calc.roe(10, -50, 50)
    assert r.value is None and r.note == "분모가 0"


def test_ROE_기말만_잠식이어도_평균이_양수면_계산():
    # 평균 = (100 + -20) / 2 = 40 → 10 / 40 = 25%
    assert calc.roe(10, 100, -20).value == pytest.approx(25.0)


def test_ROA_정상():
    assert calc.roa(30, 900, 1100).value == pytest.approx(3.0)


# ── 활동성 ───────────────────────────────────────────────
def test_총자산회전율():
    assert calc.asset_turnover(1500, 900, 1100).value == pytest.approx(1.5)


def test_매출채권회전율():
    assert calc.receivables_turnover(1200, 100, 140).value == pytest.approx(10.0)


def test_재고자산회전율_평균재고0():
    assert calc.inventory_turnover(1200, 0, 0).value is None


# ── 성장성 ───────────────────────────────────────────────
def test_매출액증가율_정상():
    assert calc.revenue_growth(1100, 1000).value == pytest.approx(10.0)


def test_영업이익증가율_흑자전환():
    r = calc.operating_income_growth(50, -20)
    assert r.value is None and r.note == "흑자전환"


def test_영업이익증가율_적자지속():
    assert calc.operating_income_growth(-50, -20).note == "적자지속"


def test_영업이익증가율_적자전환은_값과_표시():
    r = calc.operating_income_growth(-50, 100)
    assert r.value == pytest.approx(-150.0) and r.note == "적자전환"


def test_증가율_전기0():
    assert calc.total_assets_growth(100, 0).value is None


# ── 현금흐름 ─────────────────────────────────────────────
def test_영업현금흐름_대_순이익():
    assert calc.ocf_to_net_income(150, 100).value == pytest.approx(1.5)


def test_영업현금흐름_대_순이익_순손실():
    r = calc.ocf_to_net_income(150, -100)
    assert r.value is None and r.note == "당기순손실"
