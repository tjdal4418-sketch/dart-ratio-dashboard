"""금융업 판별.

은행·보험·증권사는 재무상태표에 유동/비유동 구분이 없고, 영업수익 구조도 달라
유동비율·매출액영업이익률 같은 일반 비율이 맞지 않는다. 그래서 화면에 경고를 띄운다.

업종코드(induty_code)는 한국표준산업분류(KSIC) 기준이다.
  64 금융업 / 65 보험 및 연금업 / 66 금융 및 보험 관련 서비스업
주의: 64992(지주회사)에는 SK·LG 같은 일반 지주회사와 KB금융·신한지주 같은
     금융지주회사가 섞여 있어 코드만으로 구분할 수 없다. → 회사명에 '금융'이 있으면 금융업으로 본다.
"""

FINANCIAL_PREFIXES = ("64", "65", "66")
HOLDING_COMPANY_CODE = "64992"

# 기업개황 corp_cls: Y 유가증권, K 코스닥, N 코넥스, E 기타(상장폐지 등)
MARKET_NAMES = {"Y": "유가증권시장", "K": "코스닥", "N": "코넥스", "E": "기타(비상장·상장폐지)"}


def is_financial(induty_code: str, corp_name: str = "") -> bool:
    code = (induty_code or "").strip()
    if code.startswith(HOLDING_COMPANY_CODE):
        return "금융" in corp_name
    return code.startswith(FINANCIAL_PREFIXES)
