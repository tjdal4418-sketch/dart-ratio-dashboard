# DART 재무비율 대시보드

회사명을 검색하면 [OpenDART](https://opendart.fss.or.kr) API로 재무제표를 가져와
주요 재무비율(안정성·수익성·활동성·성장성·현금흐름)을 계산하고,
연도별 추이와 기업 간 비교를 시각화하는 Streamlit 웹앱입니다.

> 🚧 개발 중입니다. 진행 과정은 [docs/devlog.md](docs/devlog.md)에 기록하고 있습니다.

## 실행 방법 (로컬)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # .env 파일에 본인의 DART_API_KEY 입력
```
