"""기업 고유번호(corp_code) 다운로드 · 캐시 · 회사명 검색.

OpenDART 의 재무제표 API 는 회사명이 아니라 8자리 '고유번호(corp_code)'로 조회한다.
그래서 전체 기업 목록(corpCode.xml, zip 압축)을 한 번 받아 로컬에 저장해 두고,
회사명 → corp_code 를 찾는 데 사용한다.

실행 예)  python -m src.corp_code 삼성
"""

import io
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from src.dart_client import CACHE_DIR, request_api

CORP_XML_PATH = CACHE_DIR / "CORPCODE.xml"
CACHE_DAYS = 7  # 신규 상장사 반영을 위해 7일이 지나면 다시 받는다.


def download_corp_xml(force: bool = False) -> bytes:
    """corpCode.xml 을 돌려준다. 캐시가 있고 7일 이내면 API 를 호출하지 않는다."""
    if CORP_XML_PATH.exists() and not force:
        age_days = (time.time() - CORP_XML_PATH.stat().st_mtime) / 86400
        if age_days < CACHE_DAYS:
            return CORP_XML_PATH.read_bytes()

    zip_bytes = request_api("corpCode.xml", binary=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # zip 안에는 CORPCODE.xml 하나만 들어 있다. 디스크에 풀지 않고 메모리에서 읽는다.
        xml_bytes = zf.read(zf.namelist()[0])

    CACHE_DIR.mkdir(exist_ok=True)
    CORP_XML_PATH.write_bytes(xml_bytes)
    return xml_bytes


def parse_listed_companies(xml_bytes: bytes) -> pd.DataFrame:
    """XML 을 표로 바꾸고, 상장사(stock_code 가 있는 기업)만 남긴다.

    XML 구조:  <result><list><corp_code>00126380</corp_code>
               <corp_name>삼성전자</corp_name><stock_code>005930</stock_code>
               <modify_date>20240101</modify_date></list> ... </result>
    비상장사는 stock_code 가 공백(" ")이다.
    """
    root = ET.fromstring(xml_bytes)
    rows = [
        {
            "corp_code": (item.findtext("corp_code") or "").strip(),
            "corp_name": (item.findtext("corp_name") or "").strip(),
            "stock_code": (item.findtext("stock_code") or "").strip(),
            "modify_date": (item.findtext("modify_date") or "").strip(),
        }
        for item in root.iter("list")
    ]
    df = pd.DataFrame(rows, columns=["corp_code", "corp_name", "stock_code", "modify_date"])
    listed = df[df["stock_code"] != ""]
    return listed.sort_values("corp_name").reset_index(drop=True)


def load_listed_companies(force: bool = False) -> pd.DataFrame:
    """상장사 목록 (다운로드/캐시 + 파싱)."""
    return parse_listed_companies(download_corp_xml(force))


def search_companies(companies: pd.DataFrame, query: str, limit: int = 20) -> pd.DataFrame:
    """회사명(또는 종목코드)으로 검색한다.

    정렬 순서: ① 이름이 정확히 같은 회사 → ② 이름이 검색어로 시작 → ③ 이름에 포함
    같은 순위 안에서는 이름이 짧은 회사를 먼저 보여준다.
    이름이 같은 회사가 여럿이면(예: 상장폐지된 옛 'SK'와 현재 'SK') 최근 변경일이 늦은 쪽을 먼저.
    ※ corpCode.xml 에는 상장폐지 기업도 옛 종목코드를 가진 채 남아 있다.
    (예: '삼성전자' 검색 시 '삼성전자'가 맨 위, 그다음 '삼성전자서비스'처럼 시작하는 회사,
         마지막으로 이름 중간에 포함된 회사)
    띄어쓰기와 영문 대소문자는 무시한다.
    """
    q = query.replace(" ", "").lower()
    if not q:
        return companies.head(0)

    names = companies["corp_name"].str.replace(" ", "").str.lower()
    matched = names.str.contains(q, regex=False)
    if q.isdigit():  # 숫자만 입력하면 종목코드로도 찾는다. (예: 005930)
        matched |= companies["stock_code"].str.startswith(q)

    result = companies[matched].copy()
    hit_names = names[matched]
    result["_rank"] = 2
    result.loc[hit_names.str.startswith(q), "_rank"] = 1
    result.loc[hit_names == q, "_rank"] = 0
    result["_len"] = result["corp_name"].str.len()

    result = result.sort_values(
        ["_rank", "_len", "corp_name", "modify_date"],
        ascending=[True, True, True, False],
    )
    return result.drop(columns=["_rank", "_len"]).head(limit).reset_index(drop=True)


if __name__ == "__main__":
    keyword = " ".join(sys.argv[1:]) or "삼성"
    companies = load_listed_companies()
    print(f"상장사 {len(companies):,}개 중 '{keyword}' 검색 결과:")
    print(search_companies(companies, keyword).to_string(index=False))
