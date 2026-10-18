"""OpenDART API 호출 공통 모듈.

- API 키 읽기 (.env 의 DART_API_KEY)
- 요청 보내기 + 응답 status 코드별 에러 처리
- 캐시 폴더 위치 정의

※ 보안: requests 의 에러 메시지에는 요청 URL(=API 키 포함)이 그대로 들어갈 수 있다.
  그래서 네트워크 에러를 잡아 URL이 없는 메시지로 바꿔서 다시 던진다.
"""

import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_URL = "https://opendart.fss.or.kr/api"

# 프로젝트 루트/.cache  (git 에 올라가지 않음)
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

# OpenDART 응답 status 코드 → 사용자에게 보여줄 설명
# (출처: OpenDART 개발가이드 '메시지 설명')
STATUS_MESSAGES = {
    "000": "정상",
    "010": "등록되지 않은 인증키입니다.",
    "011": "사용할 수 없는 인증키입니다.",
    "012": "접근할 수 없는 IP입니다.",
    "013": "조회된 데이터가 없습니다.",
    "014": "파일이 존재하지 않습니다.",
    "020": "요청 제한을 초과했습니다. (일일 20,000건)",
    "021": "조회 가능한 회사 개수를 초과했습니다. (최대 100건)",
    "100": "필드에 부적절한 값이 있습니다.",
    "101": "부적절한 접근입니다.",
    "800": "OpenDART 시스템 점검 중입니다.",
    "900": "정의되지 않은 오류가 발생했습니다.",
    "901": "개인정보 보유기간이 만료되어 사용할 수 없는 키입니다.",
}


class DartApiError(Exception):
    """OpenDART 호출 실패. status 에 응답 코드(또는 자체 코드)를 담는다."""

    def __init__(self, status: str, message: str):
        self.status = status
        super().__init__(f"[{status}] {message}")


class NoDataError(DartApiError):
    """status 013: 데이터 없음.
    오류라기보다 '해당 보고서가 없다'는 정상적인 결과라서 따로 구분한다.
    (예: 연결재무제표가 없으면 별도재무제표로 다시 조회)"""


def _key_from_streamlit_secrets() -> str:
    """Streamlit Cloud 의 Secrets 에서 키를 읽는다. Secrets 가 없거나 Streamlit 밖이면 ''."""
    try:
        import streamlit as st

        return str(st.secrets.get("DART_API_KEY", ""))
    except Exception:  # 로컬에 secrets.toml 이 없으면 예외가 나므로 빈 값으로 본다.
        return ""


def get_api_key() -> str:
    """DART_API_KEY 를 읽는다.

    순서: ① 환경변수 / .env 파일 (로컬 개발)  ② Streamlit Secrets (Streamlit Cloud 배포)
    """
    load_dotenv()
    key = os.getenv("DART_API_KEY", "").strip() or _key_from_streamlit_secrets().strip()
    if not key:
        raise DartApiError(
            "NO_KEY",
            "DART_API_KEY가 없습니다. 로컬은 .env 파일에, "
            "Streamlit Cloud는 앱 설정의 Secrets에 인증키를 넣어주세요.",
        )
    return key


def check_status(status: str, message: str = "") -> None:
    """status 가 '000'(정상)이 아니면 알맞은 예외를 던진다."""
    if status == "000":
        return
    text = STATUS_MESSAGES.get(status, message or "알 수 없는 오류")
    if status == "013":
        raise NoDataError(status, text)
    raise DartApiError(status, text)


def _status_from_error_body(content: bytes) -> tuple[str, str]:
    """에러 응답(JSON 또는 XML)에서 status, message 를 꺼낸다."""
    text = content.decode("utf-8", errors="ignore")
    try:
        data = json.loads(text)
        return data.get("status", "900"), data.get("message", "")
    except ValueError:
        pass
    status = re.search(r"<status>(\d+)</status>", text)
    message = re.search(r"<message>(.*?)</message>", text)
    return (
        status.group(1) if status else "900",
        message.group(1) if message else "응답을 해석할 수 없습니다.",
    )


def request_api(endpoint: str, params: dict | None = None, binary: bool = False):
    """OpenDART API 를 호출한다.

    endpoint: 예) "corpCode.xml", "fnlttSinglAcntAll.json"
    binary:   True 면 zip 파일(bytes)을, False 면 JSON(dict)을 돌려준다.
    """
    query = {"crtfc_key": get_api_key(), **(params or {})}
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", params=query, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        # e 를 그대로 보여주면 URL 속 API 키가 노출될 수 있어 예외 종류만 남긴다.
        raise DartApiError("NETWORK", f"네트워크 오류: {type(e).__name__}") from None

    if binary:
        # 정상 응답은 zip 파일이고, zip 은 항상 b"PK" 로 시작한다.
        if response.content[:2] == b"PK":
            return response.content
        check_status(*_status_from_error_body(response.content))
        raise DartApiError("900", "zip 파일이 아닌 응답을 받았습니다.")

    data = response.json()
    check_status(data.get("status", "900"), data.get("message", ""))
    return data
