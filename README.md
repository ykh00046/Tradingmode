# Tradingmode

암호화폐 및 한국 주식(KOSPI/KOSDAQ) 데이터를 수집하여 기술적 지표·매매 신호·추세를 분석하고 백테스팅까지 수행하는 Streamlit 기반 분석 툴.

## 상태

🚧 **개발 중** — PDCA Design 단계 완료, 구현 예정

## 기능 (계획)

- 📥 **데이터 수집**: Binance Spot (암호화폐) + pykrx / FinanceDataReader (한국 주식)
- 📊 **기술적 지표**: SMA/EMA, RSI, MACD, 볼린저밴드, ADX, Stochastic
- 🎯 **매매 신호**: 골든/데드 크로스, RSI 과매수/과매도, RSI 다이버전스, MACD 교차
- 📈 **추세 판별**: ADX + 이동평균 배열로 상승/하락/횡보 자동 분류
- 🔬 **백테스팅**: 신호 기반 진입/청산, 수익률·MDD·승률·샤프지수 산출
- 🖥️ **Streamlit 대시보드**: 캔들 차트(plotly) + 지표 오버레이 + 신호 시각화

## 기술 스택

- Python 3.11+
- Streamlit, plotly
- pandas, pandas-ta
- python-binance, pykrx, FinanceDataReader
- backtesting.py
- pyarrow (parquet 캐시)

## 문서

본 프로젝트는 PDCA 방법론으로 진행됩니다. 상세 명세는 `docs/`를 참고하세요.

| 단계 | 문서 |
|------|------|
| Plan | [docs/01-plan/features/trading-analysis-tool.plan.md](docs/01-plan/features/trading-analysis-tool.plan.md) |
| Design | [docs/02-design/features/trading-analysis-tool.design.md](docs/02-design/features/trading-analysis-tool.design.md) |

## 실행 (구현 후)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## License

TBD
