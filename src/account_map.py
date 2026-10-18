"""계정 매칭 규칙 (설정 파일).

비율 계산에 필요한 계정을 OpenDART 응답에서 찾는 규칙이다.
매칭 순서:
  1) account_id(IFRS 표준계정코드)가 "ids" 목록에 있으면 매칭  ← 우선
  2) account_id 가 "-표준계정코드 미사용-" 인 행에 한해, 계정명이 "names" 목록에 있으면 매칭
     (계정명은 띄어쓰기를 지우고 비교한다)
"statements" 는 찾을 재무제표 종류와 순서다.
  BS=재무상태표, IS=손익계산서, CIS=포괄손익계산서, CF=현금흐름표
  손익 계정은 IS 가 없고 CIS 에만 있는 회사도 있어서 ["IS", "CIS"] 순으로 찾는다.

새 회사에서 계정이 안 잡히면 여기 ids / names 에 추가하면 된다.
"""

NO_STANDARD_ID = "-표준계정코드 미사용-"

ACCOUNT_MAP = {
    # ── 재무상태표 (잔액: 기말 / 기초) ─────────────────────────────
    "total_assets": {
        "label": "자산총계",
        "statements": ["BS"],
        "ids": ["ifrs-full_Assets"],
        "names": ["자산총계"],
    },
    "current_assets": {
        "label": "유동자산",
        "statements": ["BS"],
        "ids": ["ifrs-full_CurrentAssets"],
        "names": ["유동자산"],
    },
    "inventories": {
        "label": "재고자산",
        "statements": ["BS"],
        "ids": ["ifrs-full_Inventories", "ifrs-full_InventoriesTotal"],
        "names": ["재고자산"],
    },
    "trade_receivables": {
        "label": "매출채권",
        "statements": ["BS"],
        # 매출채권을 따로 공시하지 않으면 '매출채권및기타채권'으로 대체 (앞쪽이 우선)
        "ids": ["ifrs-full_CurrentTradeReceivables", "ifrs-full_TradeAndOtherCurrentReceivables"],
        "names": ["매출채권", "매출채권및기타채권", "매출채권및기타유동채권"],
    },
    "current_liabilities": {
        "label": "유동부채",
        "statements": ["BS"],
        "ids": ["ifrs-full_CurrentLiabilities"],
        "names": ["유동부채"],
    },
    "total_liabilities": {
        "label": "부채총계",
        "statements": ["BS"],
        "ids": ["ifrs-full_Liabilities"],
        "names": ["부채총계"],
    },
    "total_equity": {
        "label": "자본총계",
        "statements": ["BS"],
        "ids": ["ifrs-full_Equity"],
        "names": ["자본총계"],
    },
    "parent_equity": {
        "label": "지배기업 소유주지분",
        "statements": ["BS"],
        "ids": ["ifrs-full_EquityAttributableToOwnersOfParent"],
        "names": ["지배기업소유주지분", "지배기업의소유주에게귀속되는자본", "지배기업소유지분"],
    },
    # ── 손익계산서 (기간: 당기 / 비교기간) ────────────────────────
    "revenue": {
        "label": "매출액",
        "statements": ["IS", "CIS"],
        "ids": ["ifrs-full_Revenue"],
        "names": ["매출액", "매출", "수익(매출액)", "영업수익"],
    },
    "operating_income": {
        "label": "영업이익",
        "statements": ["IS", "CIS"],
        "ids": ["dart_OperatingIncomeLoss"],
        "names": ["영업이익", "영업이익(손실)", "영업손실"],
    },
    "net_income": {
        "label": "당기순이익",
        "statements": ["IS", "CIS"],
        "ids": ["ifrs-full_ProfitLoss"],
        "names": ["당기순이익", "당기순이익(손실)", "반기순이익", "분기순이익",
                  "반기순이익(손실)", "분기순이익(손실)"],
    },
    "parent_net_income": {
        "label": "지배기업 소유주 귀속 순이익",
        "statements": ["IS", "CIS"],
        "ids": ["ifrs-full_ProfitLossAttributableToOwnersOfParent"],
        "names": [],  # 계정명이 '지배기업소유주지분'처럼 자본·포괄손익과 겹쳐 이름 매칭은 하지 않는다.
    },
    "interest_expense": {
        "label": "이자비용",
        "statements": ["IS", "CIS"],
        "ids": ["ifrs-full_InterestExpense", "dart_InterestExpense",
                "ifrs-full_InterestExpenseOnBorrowings"],
        "names": ["이자비용"],
    },
    # ── 현금흐름표 ────────────────────────────────────────────────
    "operating_cash_flow": {
        "label": "영업활동현금흐름",
        "statements": ["CF"],
        "ids": ["ifrs-full_CashFlowsFromUsedInOperatingActivities"],
        "names": ["영업활동현금흐름", "영업활동으로인한현금흐름"],
    },
    # 이자비용을 손익계산서에 따로 표시하지 않는 회사(삼성전자 등은 '금융비용'으로만 표시)가 많아
    # 이자보상배율 계산 시 대용치로 쓴다. (현금 기준이라 발생 기준 이자비용과 다를 수 있음)
    "interest_paid": {
        "label": "이자의 지급(현금흐름표)",
        "statements": ["CF"],
        "ids": ["ifrs-full_InterestPaidClassifiedAsOperatingActivities",
                "ifrs-full_InterestPaidClassifiedAsFinancingActivities"],
        "names": ["이자의지급", "이자지급", "이자의지급(영업)", "이자지급액"],
    },
}
