"""app.py 기본 점검: 문법 오류가 있으면 배포 후 화면 전체가 깨지므로 미리 잡는다."""

import py_compile
from pathlib import Path


def test_app_문법_오류_없음():
    py_compile.compile(str(Path(__file__).parent.parent / "app.py"), doraise=True)
