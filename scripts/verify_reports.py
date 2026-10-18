"""계산 결과 검증 스크립트.

우리 앱의 계산을 OpenDART 의 '다른' 두 API 와 대조한다.
  ① 계정 금액:  우리 파서(전체 재무제표 fnlttSinglAcntAll) ↔ 주요계정 API(fnlttSinglAcnt)
      → 계정 매칭·금액 변환·당기/전기 필드 선택이 맞는지 확인
  ② 재무비율:  우리 계산 ↔ 주요 재무지표 API(fnlttSinglIndx, 금융감독원이 계산해 제공)
      → 공식·평균잔액·연결 기준 처리 확인. 차이가 나면 원인을 기록한다.

실행 예)
  python -m scripts.verify_reports                         # 삼성전자·SK하이닉스·현대자동차, 2025 사업보고서
  python -m scripts.verify_reports 카카오 --year 2024
  python -m scripts.verify_reports --save docs/verification_result.md
"""

import argparse

import pandas as pd

from src.account_map import ACCOUNT_MAP
from src.corp_code import load_listed_companies, search_companies
from src.dart_client import CACHE_DIR, NoDataError, request_api
from src.financials import FS_NAMES, REPORT_MONTHS, _read_cache, _write_cache, fetch_report
from src.parser import to_number
from src.ratios import RATIO_DEFS, compute_ratios
from src import calculations as calc

DEFAULT_COMPANIES = ["삼성전자", "SK하이닉스", "현대자동차"]
TOLERANCE = 0.05  # 비율 차이 허용 범위 (%p 또는 회·배). 반올림 차이 수준

# ① 우리 계정 key → 주요계정 API 의 계정명
KEY_ACCOUNTS = {
    "current_assets": "유동자산",
    "total_assets": "자산총계",
    "current_liabilities": "유동부채",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익(손실)",
}

# ② 우리 비율 key → (지표분류코드, 지표코드, 배율)
#    DART 는 회전율을 ×100 한 값으로 제공하므로 배율 100 으로 나눠 맞춘다.
DART_INDICATORS = {
    "current_ratio": ("M220000", "M221200", 1),
    "quick_ratio": ("M220000", "M221300", 1),
    "debt_ratio": ("M220000", "M221100", 1),
    "equity_ratio": ("M220000", "M221000", 1),
    "interest_coverage": ("M220000", "M221600", 1),
    "net_margin": ("M210000", "M211200", 1),
    "roe": ("M210000", "M211550", 1),
    "asset_turnover": ("M240000", "M241000", 100),
    "receivables_turnover": ("M240000", "M241100", 100),
    "inventory_turnover": ("M240000", "M241200", 100),
    "revenue_growth": ("M230000", "M231000", 1),
    "operating_income_growth": ("M230000", "M231400", 1),
    "total_assets_growth": ("M230000", "M233000", 1),
}


def cached_api(name: str, endpoint: str, params: dict) -> dict:
    """검증용 API 호출 (파일 캐시)."""
    path = CACHE_DIR / "verify" / f"{name}.json"
    cached = _read_cache(path)
    if cached is not None:
        return cached
    try:
        data = request_api(endpoint, params)
    except NoDataError:
        data = {"list": []}
    _write_cache(path, data)
    return data


def key_accounts(corp_code, year, reprt_code, fs_div) -> dict:
    """주요계정 API → {계정명: (당기, 전기, 당기 3개월)}. 같은 이름이 두 번 나오면 처음 것.

    분기·반기 손익은 이 API 도 thstrm_amount=3개월, thstrm_add_amount=누적 이므로
    앱과 같은 '누적'끼리 비교하고, 3개월 값은 따로 비교한다.
    """
    data = cached_api(f"acnt_{corp_code}_{year}_{reprt_code}", "fnlttSinglAcnt.json",
                      {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code})
    result = {}
    for row in data["list"]:
        if row["fs_div"] == fs_div and row["account_nm"] not in result:
            if row.get("thstrm_add_amount"):  # 분기·반기 손익
                result[row["account_nm"]] = (to_number(row["thstrm_add_amount"]),
                                             to_number(row["frmtrm_add_amount"]),
                                             to_number(row["thstrm_amount"]))
            else:
                result[row["account_nm"]] = (to_number(row["thstrm_amount"]),
                                             to_number(row["frmtrm_amount"]), None)
    return result


def dart_indicators(corp_code, year, reprt_code) -> dict:
    """주요 재무지표 API → {지표코드: 값}"""
    values = {}
    for cl_code in sorted({cl for cl, _, _ in DART_INDICATORS.values()}):
        data = cached_api(f"indx_{corp_code}_{year}_{reprt_code}_{cl_code}", "fnlttSinglIndx.json",
                          {"corp_code": corp_code, "bsns_year": str(year),
                           "reprt_code": reprt_code, "idx_cl_code": cl_code})
        for row in data["list"]:
            values[row["idx_code"]] = to_number(row.get("idx_val"))
    return values


def check_accounts(report, corp_code, year, reprt_code) -> pd.DataFrame:
    official = key_accounts(corp_code, year, reprt_code, report["fs_div"])
    acc = report["accounts"]
    rows = []
    for key, name in KEY_ACCOUNTS.items():
        ours = (acc.loc[key, "current"], acc.loc[key, "prior"], acc.loc[key, "current_3m"])
        theirs = official.get(name, (None, None, None))
        checks = [("당기", ours[0], theirs[0]), ("전기", ours[1], theirs[1])]
        if theirs[2] is not None:
            checks.append(("당기 3개월", ours[2], theirs[2]))
        for period, a, b in checks:
            a = None if pd.isna(a) else a
            status = "기준없음" if b is None else ("일치" if a == b else "차이")
            rows.append({"계정": ACCOUNT_MAP[key]["label"], "기간": period,
                         "앱": a, "주요계정 API": b, "결과": status})
    return pd.DataFrame(rows)


def check_ratios(report, corp_code, year, reprt_code) -> pd.DataFrame:
    official = dart_indicators(corp_code, year, reprt_code)
    ours = compute_ratios(report)
    factor = 12 / REPORT_MONTHS[reprt_code]  # 분기·반기 연환산 배수 (사업보고서는 1)
    rows = []
    for key, (name, _, unit, _) in RATIO_DEFS.items():
        value = ours.loc[key, "value"]
        value = None if pd.isna(value) else value
        bench = None
        if key in DART_INDICATORS:
            _, idx_code, scale = DART_INDICATORS[key]
            raw = official.get(idx_code)
            bench = None if raw is None else raw / scale
        if bench is None:
            status = "기준없음"
        elif value is None:
            status = "앱 계산불가"
        else:
            status = "일치" if abs(value - bench) <= TOLERANCE else "차이"
            # DART 지표는 연환산하지 않는다. 앱 값을 배수로 나눠 같아지면 '연환산 차이'로 분류.
            annualized = "연환산" in ours.loc[key, "note"]
            if status == "차이" and annualized and abs(value / factor - bench) <= TOLERANCE:
                status = "일치(연환산 제외 시)"
        rows.append({"비율": name, "단위": unit, "앱": value, "DART 지표": bench,
                     "차이": None if (value is None or bench is None) else value - bench,
                     "결과": status, "앱 비고": ours.loc[key, "note"]})

    # 원인 확인용: 연결 ROE 를 '전체 순이익 ÷ 전체 자본' 으로 계산하면 DART 와 같은지
    acc = report["accounts"]
    total_roe = calc.roe(acc.loc["net_income", "current"], acc.loc["total_equity", "prior"],
                         acc.loc["total_equity", "current"]).value  # 연환산하지 않음
    bench = official.get("M211550")
    rows.append({"비율": "(참고) ROE-전체기준", "단위": "%", "앱": total_roe, "DART 지표": bench,
                 "차이": None if bench is None else total_roe - bench,
                 "결과": "기준없음" if bench is None else ("일치" if abs(total_roe - bench) <= TOLERANCE else "차이"),
                 "앱 비고": "당기순이익 ÷ 평균 자본총계 (연환산 없음)"})
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    """간단한 마크다운 표 (외부 라이브러리 없이)"""
    def cell(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        if isinstance(v, float):
            return f"{v:,.0f}" if abs(v) >= 1e6 else f"{v:,.3f}"
        if isinstance(v, int):
            return f"{v:,}"
        return str(v)
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--report", default="11011")
    ap.add_argument("--save", help="결과를 저장할 마크다운 파일 경로")
    args = ap.parse_args()

    companies = load_listed_companies()
    out = [f"# 검증 결과 ({args.year}년, 보고서 {args.report})", "",
           "자동 생성: `python -m scripts.verify_reports` · 원인 분석은 docs/verification.md 참고", ""]
    summary = []
    for name in args.names or DEFAULT_COMPANIES:
        corp = search_companies(companies, name).iloc[0]
        report = fetch_report(corp["corp_code"], args.year, args.report)
        accounts = check_accounts(report, corp["corp_code"], args.year, args.report)
        ratios = check_ratios(report, corp["corp_code"], args.year, args.report)
        link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={report['rcept_no']}"
        out += [f"## {corp['corp_name']} ({FS_NAMES[report['fs_div']]}) · [공시 원문]({link})", "",
                "### ① 계정 금액 (원)", "", to_markdown(accounts), "",
                "### ② 재무비율", "", to_markdown(ratios), ""]
        summary.append({
            "회사": corp["corp_name"],
            "계정 일치": f"{(accounts['결과'] == '일치').sum()}/{(accounts['결과'] != '기준없음').sum()}",
            "비율 일치": f"{ratios['결과'].str.startswith('일치').sum()}/{(~ratios['결과'].isin(['기준없음', '앱 계산불가'])).sum()}",
            "비율 차이": ", ".join(ratios.loc[ratios["결과"] == "차이", "비율"]),
        })
    text = "\n".join(out[:4] + ["## 요약", "", to_markdown(pd.DataFrame(summary)), ""] + out[4:])
    print(text)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
