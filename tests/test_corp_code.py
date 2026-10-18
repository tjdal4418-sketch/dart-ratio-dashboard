"""corp_code.py 테스트 — 저장해 둔 샘플 XML 을 사용하므로 API 를 호출하지 않는다."""

from pathlib import Path

import pytest

from src.corp_code import parse_listed_companies, search_companies

SAMPLE = Path(__file__).parent / "fixtures" / "corpcode_sample.xml"


@pytest.fixture
def companies():
    return parse_listed_companies(SAMPLE.read_bytes())


def test_비상장사는_제외된다(companies):
    # 샘플 8개 중 '삼성전자서비스'는 stock_code 가 공백 → 비상장
    assert len(companies) == 7
    assert "삼성전자서비스" not in companies["corp_name"].values


def test_정확히_일치하는_회사가_맨_앞(companies):
    result = search_companies(companies, "삼성전자")
    assert result.iloc[0]["corp_code"] == "00126380"


def test_시작하는_회사가_포함하는_회사보다_앞(companies):
    names = list(search_companies(companies, "삼성")["corp_name"])
    assert names[-1] == "한국삼성테스트"   # 이름 중간에 포함 → 마지막
    assert set(names[:3]) == {"삼성전자", "삼성전기", "삼성에스디에스"}


def test_대소문자와_띄어쓰기_무시(companies):
    assert search_companies(companies, "sk 하이닉스").iloc[0]["corp_name"] == "SK하이닉스"


def test_종목코드로_검색(companies):
    assert search_companies(companies, "005930").iloc[0]["corp_name"] == "삼성전자"


def test_빈_검색어는_빈_결과(companies):
    assert search_companies(companies, "  ").empty


def test_이름이_같으면_최근_변경된_회사가_앞(companies):
    # 옛 SK(003600, 2017년 변경)는 상장폐지, 현재 SK는 034730
    result = search_companies(companies, "SK")
    assert list(result["stock_code"][:2]) == ["034730", "003600"]
