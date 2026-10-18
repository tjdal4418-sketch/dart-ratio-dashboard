"""재무제표·기업개황 수집 (파일 캐시 포함).

- fetch_report  : 한 회사·한 연도·한 보고서의 계정표 (연결 우선, 없으면 별도)
- fetch_reports : 여러 연도를 한 번에 (추이 차트용)
- fetch_company : 기업개황 (시장 구분, 업종코드)

캐시 정책 (일일 호출 한도 20,000건 대비):
  - 정상 응답: 한 번 받은 보고서는 다시 호출하지 않는다. (과거 보고서는 바뀌지 않으므로)
  - 데이터 없음(013): 1일만 기억한다. (아직 제출 전인 보고서는 나중에 생길 수 있으므로)
  - 기업개황: 30일

실행 예)  python -m src.financials 삼성전자 2025 11011
"""

import json
import sys
import time

from src.dart_client import CACHE_DIR, NoDataError, request_api
from src.parser import parse_report

REPORT_NAMES = {"11011": "사업보고서", "11012": "반기보고서", "11013": "1분기보고서", "11014": "3분기보고서"}
REPORT_MONTHS = {"11013": 3, "11012": 6, "11014": 9, "11011": 12}  # 누적 개월 수 (연환산에 사용)
FS_NAMES = {"CFS": "연결", "OFS": "별도"}

QUARTER_SUFFIX = {"11013": "1Q", "11012": "2Q", "11014": "3Q", "11011": ""}

NO_DATA_CACHE_DAYS = 1
COMPANY_CACHE_DAYS = 30


def _read_cache(path, max_days=None):
    """캐시 파일을 읽는다. 없거나 max_days 보다 오래됐으면 None."""
    if not path.exists():
        return None
    if max_days is not None and (time.time() - path.stat().st_mtime) / 86400 >= max_days:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_cache(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def period_label(year: int, reprt_code: str) -> str:
    """차트·표에 쓸 기간 이름. 예) 2025, 2026.2Q"""
    suffix = QUARTER_SUFFIX[reprt_code]
    return f"{year}.{suffix}" if suffix else str(year)


def fetch_statement_rows(corp_code: str, year: int, reprt_code: str, fs_div: str) -> list[dict]:
    """단일회사 전체 재무제표(fnlttSinglAcntAll) 원본 행 목록. 없으면 NoDataError."""
    path = CACHE_DIR / "fs" / f"{corp_code}_{year}_{reprt_code}_{fs_div}.json"
    cached = _read_cache(path)
    if cached is not None:
        if cached["status"] == "000":
            return cached["list"]
        if _read_cache(path, NO_DATA_CACHE_DAYS) is not None:  # 하루 안에 확인한 '데이터 없음'
            raise NoDataError("013", "조회된 데이터가 없습니다.")

    params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs_div}
    try:
        data = request_api("fnlttSinglAcntAll.json", params)
    except NoDataError:
        _write_cache(path, {"status": "013"})
        raise
    _write_cache(path, {"status": "000", "list": data["list"]})
    return data["list"]


def fetch_report(corp_code: str, year: int, reprt_code: str, fs_pref: str = "CFS") -> dict:
    """한 기간의 계정표.

    fs_pref='CFS'(연결)이면 연결을 먼저 찾고, 없으면 별도(OFS)로 대체한다.
    fs_pref='OFS'(별도)이면 별도만 찾는다.
    반환: {year, reprt_code, fs_div, fallback(대체 여부), rcept_no(접수번호), accounts(DataFrame)}
    """
    order = ["CFS", "OFS"] if fs_pref == "CFS" else ["OFS"]
    for fs_div in order:
        try:
            rows = fetch_statement_rows(corp_code, year, reprt_code, fs_div)
        except NoDataError:
            continue
        return {
            "year": year,
            "reprt_code": reprt_code,
            "fs_div": fs_div,
            "fallback": fs_div != fs_pref,
            "rcept_no": rows[0]["rcept_no"] if rows else "",
            "accounts": parse_report(rows, reprt_code),
        }
    raise NoDataError("013", f"{year}년 {REPORT_NAMES[reprt_code]} 재무제표가 없습니다.")


def fetch_reports(corp_code: str, end_year: int, reprt_code: str,
                  n_years: int = 5, fs_pref: str = "CFS") -> list[dict]:
    """end_year 부터 과거 n_years 개 연도의 같은 보고서를 모은다. (오래된 연도 → 최근 순)
    중간에 보고서가 없는 연도는 건너뛴다."""
    reports = []
    for year in range(end_year - n_years + 1, end_year + 1):
        try:
            reports.append(fetch_report(corp_code, year, reprt_code, fs_pref))
        except NoDataError:
            continue
    return reports


def fetch_company(corp_code: str) -> dict:
    """기업개황(company.json): corp_name, corp_cls(시장), induty_code(업종), acc_mt(결산월) 등"""
    path = CACHE_DIR / "company" / f"{corp_code}.json"
    cached = _read_cache(path, COMPANY_CACHE_DAYS)
    if cached is not None:
        return cached
    data = request_api("company.json", {"corp_code": corp_code})
    _write_cache(path, data)
    return data


if __name__ == "__main__":
    import pandas as pd

    from src.corp_code import load_listed_companies, search_companies

    name = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    reprt = sys.argv[3] if len(sys.argv) > 3 else "11011"

    corp = search_companies(load_listed_companies(), name).iloc[0]
    report = fetch_report(corp["corp_code"], year, reprt)
    note = " (연결 없음 → 별도로 대체)" if report["fallback"] else ""
    print(f"{corp['corp_name']} {year}년 {REPORT_NAMES[reprt]} · {FS_NAMES[report['fs_div']]}{note}")
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:,.0f}".format)  # 원 단위, 쉼표
    print(report["accounts"][["label", "current", "prior", "sj_div", "matched_by", "account_nm"]])
