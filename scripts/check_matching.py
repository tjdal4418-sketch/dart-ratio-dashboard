"""계정 매칭 점검 스크립트.

여러 회사의 재무제표를 받아 account_map.py 규칙으로 계정이 잘 잡히는지 확인한다.
못 잡힌 계정은 '없음'으로 표시되므로, 원본 응답을 보고 account_map.py 에 코드/이름을 추가하면 된다.

실행 예)
  python -m scripts.check_matching                     # 기본 대표 기업
  python -m scripts.check_matching --random 20         # 무작위 상장사 20개
  python -m scripts.check_matching 카카오 NAVER --year 2026 --report 11012
"""

import argparse
import random

import pandas as pd

from src.account_map import ACCOUNT_MAP
from src.corp_code import load_listed_companies, search_companies
from src.dart_client import NoDataError
from src.financials import FS_NAMES, fetch_company, fetch_report
from src.industry import is_financial

DEFAULT_COMPANIES = ["삼성전자", "SK하이닉스", "현대자동차", "카카오", "LG화학", "셀트리온",
                     "에코프로비엠", "KB금융", "삼성생명"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--report", default="11011")
    ap.add_argument("--random", type=int, default=0)
    args = ap.parse_args()

    companies = load_listed_companies()
    if args.random:
        targets = companies.sample(args.random, random_state=random.randint(0, 9999))
    else:
        names = args.names or DEFAULT_COMPANIES
        targets = pd.DataFrame([search_companies(companies, n).iloc[0] for n in names])

    summary = []
    for _, corp in targets.iterrows():
        info = fetch_company(corp["corp_code"])
        try:
            rep = fetch_report(corp["corp_code"], args.year, args.report)
        except NoDataError:
            summary.append({"회사": corp["corp_name"], "구분": "보고서 없음"})
            continue
        acc = rep["accounts"]
        missing = [ACCOUNT_MAP[k]["label"] for k in acc.index if acc.loc[k, "matched_by"] == "없음"]
        by_name = [ACCOUNT_MAP[k]["label"] for k in acc.index if acc.loc[k, "matched_by"] == "계정명"]
        summary.append({
            "회사": corp["corp_name"],
            "구분": FS_NAMES[rep["fs_div"]] + ("(대체)" if rep["fallback"] else ""),
            "금융업": "Y" if is_financial(info.get("induty_code"), info.get("corp_name", "")) else "",
            "시장": info.get("corp_cls"),
            "계정명매칭": ", ".join(by_name),
            "못찾음": ", ".join(missing),
        })

    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 80)
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
