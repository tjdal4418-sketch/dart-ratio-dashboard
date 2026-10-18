"""parser.py 테스트 — 응답 행을 직접 만들어 사용 (API 호출 없음)."""

import pytest

from src.account_map import NO_STANDARD_ID
from src.industry import is_financial
from src.parser import parse_report, pick_fields, to_number


def row(sj_div, account_id, account_nm, **amounts):
    """테스트용 응답 행 하나"""
    return {"sj_div": sj_div, "account_id": account_id, "account_nm": account_nm,
            "account_detail": "-", **amounts}


# ── 금액 변환 ────────────────────────────────────────────
@pytest.mark.parametrize("text, expected", [
    ("1,234,567", 1234567),
    ("-5,000", -5000),
    ("(300)", -300),
    ("0", 0),
    ("", None),
    ("-", None),
    (None, None),
    ("12.5", 12.5),
])
def test_to_number(text, expected):
    assert to_number(text) == expected


# ── 필드 선택 ────────────────────────────────────────────
def test_분기_손익은_누적필드_사용():
    assert pick_fields("IS", "11014") == ("thstrm_add_amount", "frmtrm_add_amount")


def test_분기_현금흐름은_thstrm이_누적():
    assert pick_fields("CF", "11012") == ("thstrm_amount", "frmtrm_q_amount")


def test_재무상태표는_항상_당기말과_전기말():
    assert pick_fields("BS", "11013") == ("thstrm_amount", "frmtrm_amount")


# ── 계정 매칭 ────────────────────────────────────────────
def test_표준계정코드로_매칭():
    rows = [row("BS", "ifrs-full_Assets", "자산 총계", thstrm_amount="1,000", frmtrm_amount="800")]
    acc = parse_report(rows, "11011")
    assert acc.loc["total_assets", "current"] == 1000
    assert acc.loc["total_assets", "prior"] == 800
    assert acc.loc["total_assets", "matched_by"] == "표준계정코드"


def test_표준코드_미사용이면_계정명으로_매칭_띄어쓰기무시():
    rows = [row("BS", NO_STANDARD_ID, "재고 자산", thstrm_amount="50", frmtrm_amount="40")]
    acc = parse_report(rows, "11011")
    assert acc.loc["inventories", "current"] == 50
    assert acc.loc["inventories", "matched_by"] == "계정명"


def test_다른_표준코드가_있는_행은_계정명이_같아도_매칭하지_않음():
    # 계정명은 '재고자산'이지만 다른 표준코드가 붙어 있으면 그 코드의 의미를 따른다.
    rows = [row("BS", "ifrs-full_OtherInventories", "재고자산", thstrm_amount="50")]
    assert parse_report(rows, "11011").loc["inventories", "matched_by"] == "없음"


def test_IS가_없으면_CIS에서_찾음():
    rows = [row("CIS", "ifrs-full_Revenue", "매출액", thstrm_amount="900", frmtrm_amount="700")]
    acc = parse_report(rows, "11011")
    assert acc.loc["revenue", "current"] == 900
    assert acc.loc["revenue", "sj_div"] == "CIS"


def test_IS와_CIS_모두_있으면_IS_우선():
    rows = [
        row("CIS", "ifrs-full_ProfitLoss", "당기순이익", thstrm_amount="1"),
        row("IS", "ifrs-full_ProfitLoss", "당기순이익", thstrm_amount="2"),
    ]
    assert parse_report(rows, "11011").loc["net_income", "current"] == 2


def test_매출채권_코드_우선순위():
    rows = [
        row("BS", "ifrs-full_TradeAndOtherCurrentReceivables", "매출채권및기타채권", thstrm_amount="30"),
        row("BS", "ifrs-full_CurrentTradeReceivables", "매출채권", thstrm_amount="20"),
    ]
    assert parse_report(rows, "11011").loc["trade_receivables", "current"] == 20


def test_분기보고서_손익은_누적값과_3개월값을_구분():
    rows = [row("IS", "ifrs-full_Revenue", "매출액",
                thstrm_amount="100", thstrm_add_amount="300",
                frmtrm_q_amount="90", frmtrm_add_amount="250")]
    acc = parse_report(rows, "11014")
    assert acc.loc["revenue", "current"] == 300      # 누적
    assert acc.loc["revenue", "prior"] == 250        # 전년 같은 기간 누적
    assert acc.loc["revenue", "current_3m"] == 100   # 3개월


def test_1분기_누적칸이_비어있으면_3개월값_사용():
    rows = [row("IS", "ifrs-full_Revenue", "매출액", thstrm_amount="100", thstrm_add_amount="",
                frmtrm_q_amount="90", frmtrm_add_amount="")]
    acc = parse_report(rows, "11013")
    assert acc.loc["revenue", "current"] == 100
    assert acc.loc["revenue", "prior"] == 90


def test_자본변동표_세부항목은_제외():
    rows = [{"sj_div": "BS", "account_id": "ifrs-full_Equity", "account_nm": "자본총계",
             "account_detail": "이익잉여금 [member]", "thstrm_amount": "5"}]
    assert parse_report(rows, "11011").loc["total_equity", "matched_by"] == "없음"


# ── 금융업 판별 ──────────────────────────────────────────
@pytest.mark.parametrize("code, name, expected", [
    ("264", "삼성전자", False),
    ("65110", "삼성생명보험", True),
    ("64121", "기업은행", True),
    ("64992", "SK", False),          # 일반 지주회사
    ("64992", "KB금융지주", True),    # 금융지주회사
])
def test_is_financial(code, name, expected):
    assert is_financial(code, name) == expected
