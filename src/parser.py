"""OpenDART 재무제표 응답(행 목록) → 비율 계산에 쓸 계정표.

결과 표의 한 행 = 계정 하나 (account_map.py 의 key 하나)
  current : 당기 금액   (재무상태표=기말 잔액, 손익·현금흐름=당기 금액)
  prior   : 비교 금액   (재무상태표=기초 잔액(전기말), 손익·현금흐름=전년 같은 기간 금액)

보고서 종류별로 어떤 필드를 쓰는지가 이 파일의 핵심이다. (pick_fields 참고)
"""

import pandas as pd

from src.account_map import ACCOUNT_MAP, NO_STANDARD_ID

ANNUAL = "11011"  # 사업보고서
FIRST_QUARTER = "11013"  # 1분기보고서


def to_number(value):
    """'1,234' → 1234, '-5,000' → -5000, '(300)' → -300, ''·'-'·None → None"""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "-"):
        return None
    negative = text.startswith("(") and text.endswith(")")  # 괄호 표기 음수
    text = text.strip("()")
    try:
        number = int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError:
            return None
    return -number if negative else number


def normalize_name(name: str) -> str:
    """계정명 비교용: 띄어쓰기 제거"""
    return (name or "").replace(" ", "")


def pick_fields(sj_div: str, reprt_code: str) -> tuple[str, str]:
    """(당기 필드, 비교 필드) 이름을 돌려준다.

    | 구분          | 사업보고서                     | 분기·반기보고서                                   |
    |---------------|-------------------------------|--------------------------------------------------|
    | 재무상태표     | thstrm / frmtrm (전기말)       | thstrm(분기말) / frmtrm (전기말 = 기초)            |
    | 손익(IS, CIS) | thstrm / frmtrm (전기 1년)     | thstrm_add(누적) / frmtrm_add(전년 같은 기간 누적) |
    | 현금흐름(CF)  | thstrm / frmtrm               | thstrm(이미 누적) / frmtrm_q(전년 같은 기간 누적)   |

    ※ 분기 손익의 thstrm_amount 는 '3개월치'라서 누적(thstrm_add_amount)을 써야 한다.
    ※ 분기 현금흐름표는 원래 누적으로만 작성되어 thstrm_amount 가 곧 누적이다.
    """
    if reprt_code == ANNUAL or sj_div == "BS":
        return "thstrm_amount", "frmtrm_amount"
    if sj_div in ("IS", "CIS"):
        return "thstrm_add_amount", "frmtrm_add_amount"
    return "thstrm_amount", "frmtrm_q_amount"  # CF


def _amount(row: dict, field: str, reprt_code: str):
    """필드 값을 숫자로. 1분기는 누적=3개월이라 누적 칸이 비어 있으면 3개월 값으로 대체."""
    value = to_number(row.get(field))
    if value is None and reprt_code == FIRST_QUARTER and field.endswith("add_amount"):
        fallback = {"thstrm_add_amount": "thstrm_amount", "frmtrm_add_amount": "frmtrm_q_amount"}
        value = to_number(row.get(fallback[field]))
    return value


def find_account(rows: list[dict], rule: dict) -> tuple[dict | None, str]:
    """규칙에 맞는 행 하나를 찾는다. (행, 매칭 방법) 반환."""
    # 세부 항목(account_detail 이 있는 행, 주로 자본변동표)은 제외
    usable = [r for r in rows if r.get("account_detail", "-") in ("-", "", None)]

    # 1순위: 표준계정코드 — ids 목록 앞쪽이 우선
    for account_id in rule["ids"]:
        for sj in rule["statements"]:
            for row in usable:
                if row["sj_div"] == sj and row["account_id"] == account_id:
                    return row, "표준계정코드"

    # 2순위: 표준계정코드를 쓰지 않은 행만 계정명으로
    names = {normalize_name(n) for n in rule["names"]}
    for sj in rule["statements"]:
        for row in usable:
            if (row["sj_div"] == sj and row["account_id"] == NO_STANDARD_ID
                    and normalize_name(row["account_nm"]) in names):
                return row, "계정명"

    return None, "없음"


def parse_report(rows: list[dict], reprt_code: str) -> pd.DataFrame:
    """응답 행 목록 → 계정표(DataFrame). 못 찾은 계정은 금액 None, matched_by='없음'."""
    records = []
    for key, rule in ACCOUNT_MAP.items():
        row, matched_by = find_account(rows, rule)
        record = {
            "key": key,
            "label": rule["label"],
            "current": None,
            "prior": None,
            "current_3m": None,  # 분기·반기 손익의 3개월치 (참고용)
            "sj_div": None,
            "account_id": None,
            "account_nm": None,
            "matched_by": matched_by,
        }
        if row is not None:
            cur_field, prior_field = pick_fields(row["sj_div"], reprt_code)
            record.update(
                current=_amount(row, cur_field, reprt_code),
                prior=_amount(row, prior_field, reprt_code),
                sj_div=row["sj_div"],
                account_id=row["account_id"],
                account_nm=row["account_nm"],
            )
            if reprt_code != ANNUAL and row["sj_div"] in ("IS", "CIS"):
                record["current_3m"] = to_number(row.get("thstrm_amount"))
        records.append(record)
    return pd.DataFrame(records).set_index("key")
