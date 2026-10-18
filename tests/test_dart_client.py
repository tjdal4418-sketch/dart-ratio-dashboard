"""dart_client.py 의 status 코드 처리 테스트 (네트워크 사용 안 함)."""

import pytest

from src.dart_client import DartApiError, NoDataError, _status_from_error_body, check_status


def test_정상코드는_통과():
    check_status("000")  # 예외가 나지 않으면 성공


def test_데이터없음은_NoDataError():
    with pytest.raises(NoDataError):
        check_status("013")


def test_한도초과는_DartApiError_그리고_설명포함():
    with pytest.raises(DartApiError, match="20,000"):
        check_status("020")


def test_XML_에러응답_해석():
    body = "<result><status>010</status><message>등록되지 않은 키</message></result>".encode()
    assert _status_from_error_body(body) == ("010", "등록되지 않은 키")


def test_JSON_에러응답_해석():
    body = '{"status": "013", "message": "조회된 데이타가 없습니다."}'.encode()
    assert _status_from_error_body(body)[0] == "013"
