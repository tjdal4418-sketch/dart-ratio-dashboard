"""재무비율 계산 (순수 함수).

- 모든 함수는 숫자만 받고 Ratio(value, note)를 돌려준다. API·화면과 무관하므로 테스트하기 쉽다.
- 계산할 수 없으면 value=None 이고 note 에 사유를 적는다. (분모 0, 자본잠식, 데이터 없음 등)
- docstring 첫 줄 = 공식. 화면 툴팁에도 이 첫 줄을 그대로 쓴다. (ratios_meta.py)
- 평균 잔액 = (기초 + 기말) / 2,  기초 잔액은 전기말(frmtrm_amount) 값.

단위: % 비율은 ×100 한 값, 회전율은 '회', 이자보상배율은 '배'.
"""

from dataclasses import dataclass


@dataclass
class Ratio:
    value: float | None
    note: str = ""  # None 이면 계산 불가 사유, 값이 있으면 참고 사항(예: 연환산, 대용치)


# ── 공통 도우미 ──────────────────────────────────────────────
def _missing(**inputs) -> Ratio | None:
    """입력값 중 None 이 있으면 '데이터 없음' 결과를, 모두 있으면 None 을 돌려준다."""
    names = [name for name, value in inputs.items() if value is None]
    if names:
        return Ratio(None, "데이터 없음: " + ", ".join(names))
    return None


def _divide(numerator, denominator, scale=1.0, negative_reason="분모가 음수") -> Ratio:
    """분자/분모 × scale. 분모가 0 이거나 음수면 None + 사유."""
    if denominator == 0:
        return Ratio(None, "분모가 0")
    if denominator < 0:
        return Ratio(None, negative_reason)
    return Ratio(numerator / denominator * scale)


def average(begin, end):
    """(기초 + 기말) / 2"""
    return (begin + end) / 2


# ── 안정성 ───────────────────────────────────────────────────
def current_ratio(current_assets, current_liabilities) -> Ratio:
    """유동비율 = 유동자산 ÷ 유동부채 × 100"""
    return (_missing(유동자산=current_assets, 유동부채=current_liabilities)
            or _divide(current_assets, current_liabilities, 100))


def quick_ratio(current_assets, inventories, current_liabilities) -> Ratio:
    """당좌비율 = (유동자산 − 재고자산) ÷ 유동부채 × 100"""
    if inventories is None and current_assets is not None:
        inventories = 0  # 재고자산 계정이 없는 회사(서비스업 등)는 재고 0 으로 본다.
    return (_missing(유동자산=current_assets, 유동부채=current_liabilities)
            or _divide(current_assets - inventories, current_liabilities, 100))


def debt_ratio(total_liabilities, total_equity) -> Ratio:
    """부채비율 = 부채총계 ÷ 자본총계 × 100"""
    return (_missing(부채총계=total_liabilities, 자본총계=total_equity)
            or _divide(total_liabilities, total_equity, 100, "자본잠식(자본총계 음수)"))


def equity_ratio(total_equity, total_assets) -> Ratio:
    """자기자본비율 = 자본총계 ÷ 자산총계 × 100"""
    return (_missing(자본총계=total_equity, 자산총계=total_assets)
            or _divide(total_equity, total_assets, 100))


def interest_coverage(operating_income, interest_expense) -> Ratio:
    """이자보상배율 = 영업이익 ÷ 이자비용 (배)"""
    missing = _missing(영업이익=operating_income, 이자비용=interest_expense)
    if missing:
        return missing
    if interest_expense == 0:
        return Ratio(None, "이자비용이 0 (무차입 등)")
    return _divide(operating_income, abs(interest_expense))  # 이자비용은 부호와 무관하게 크기로 본다.


# ── 수익성 ───────────────────────────────────────────────────
def operating_margin(operating_income, revenue) -> Ratio:
    """매출액영업이익률 = 영업이익 ÷ 매출액 × 100"""
    return _missing(영업이익=operating_income, 매출액=revenue) or _divide(operating_income, revenue, 100)


def net_margin(net_income, revenue) -> Ratio:
    """매출액순이익률 = 당기순이익 ÷ 매출액 × 100"""
    return _missing(당기순이익=net_income, 매출액=revenue) or _divide(net_income, revenue, 100)


def roe(net_income, equity_begin, equity_end) -> Ratio:
    """ROE = 당기순이익 ÷ 평균 자기자본 × 100  (평균 = (기초+기말)/2, 연결은 지배기업 소유주 기준)"""
    missing = _missing(당기순이익=net_income, 기초자본=equity_begin, 기말자본=equity_end)
    if missing:
        return missing
    return _divide(net_income, average(equity_begin, equity_end), 100, "자본잠식(평균 자본 음수)")


def roa(net_income, assets_begin, assets_end) -> Ratio:
    """ROA = 당기순이익 ÷ 평균 총자산 × 100  (평균 = (기초+기말)/2)"""
    missing = _missing(당기순이익=net_income, 기초자산=assets_begin, 기말자산=assets_end)
    if missing:
        return missing
    return _divide(net_income, average(assets_begin, assets_end), 100)


# ── 활동성 ───────────────────────────────────────────────────
def asset_turnover(revenue, assets_begin, assets_end) -> Ratio:
    """총자산회전율 = 매출액 ÷ 평균 총자산 (회)"""
    missing = _missing(매출액=revenue, 기초자산=assets_begin, 기말자산=assets_end)
    if missing:
        return missing
    return _divide(revenue, average(assets_begin, assets_end))


def receivables_turnover(revenue, receivables_begin, receivables_end) -> Ratio:
    """매출채권회전율 = 매출액 ÷ 평균 매출채권 (회)"""
    missing = _missing(매출액=revenue, 기초매출채권=receivables_begin, 기말매출채권=receivables_end)
    if missing:
        return missing
    return _divide(revenue, average(receivables_begin, receivables_end))


def inventory_turnover(revenue, inventories_begin, inventories_end) -> Ratio:
    """재고자산회전율 = 매출액 ÷ 평균 재고자산 (회)

    ※ 매출원가 기준을 쓰기도 하지만, 성격별 손익계산서를 쓰는 회사는 매출원가가 없어
      한국은행 기업경영분석과 같은 매출액 기준으로 통일했다.
    """
    missing = _missing(매출액=revenue, 기초재고=inventories_begin, 기말재고=inventories_end)
    if missing:
        return missing
    return _divide(revenue, average(inventories_begin, inventories_end))


# ── 성장성 ───────────────────────────────────────────────────
def growth_rate(current, prior, account="") -> Ratio:
    """증가율 = (당기 − 전기) ÷ 전기 × 100

    전기 값이 0 이하(적자)이면 증가율이 의미 없으므로 None. (흑자전환 / 적자지속으로 표시)
    account: 사유 메시지에 쓸 계정 이름 (예: '매출액')
    """
    missing = _missing(**{f"당기 {account}".strip(): current, f"전기 {account}".strip(): prior})
    if missing:
        return missing
    if prior == 0:
        return Ratio(None, "전기 값이 0")
    if prior < 0:
        return Ratio(None, "흑자전환" if current > 0 else "적자지속")
    result = Ratio((current - prior) / prior * 100)
    if current < 0:
        result.note = "적자전환"
    return result


def revenue_growth(revenue, revenue_prior) -> Ratio:
    """매출액증가율 = (당기 매출액 − 전기 매출액) ÷ 전기 매출액 × 100"""
    return growth_rate(revenue, revenue_prior, "매출액")


def operating_income_growth(operating_income, operating_income_prior) -> Ratio:
    """영업이익증가율 = (당기 영업이익 − 전기 영업이익) ÷ 전기 영업이익 × 100"""
    return growth_rate(operating_income, operating_income_prior, "영업이익")


def total_assets_growth(assets_end, assets_begin) -> Ratio:
    """총자산증가율 = (기말 총자산 − 기초 총자산) ÷ 기초 총자산 × 100"""
    return growth_rate(assets_end, assets_begin, "총자산")


# ── 현금흐름 ─────────────────────────────────────────────────
def ocf_to_net_income(operating_cash_flow, net_income) -> Ratio:
    """영업현금흐름 대 순이익 = 영업활동현금흐름 ÷ 당기순이익 (배)"""
    return (_missing(영업활동현금흐름=operating_cash_flow, 당기순이익=net_income)
            or _divide(operating_cash_flow, net_income, negative_reason="당기순손실"))
