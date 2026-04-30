// Signals page — full inventory of detected signals across all instruments
// Plus per-instrument detail with chart context.

const { useState: useStateS, useMemo: useMemoS } = React;

function SignalsPage({ universe, data, currentSymbol, setCurrent, upColor, downColor }) {
  const [filter, setFilter] = useStateS('all'); // all | buy | sell
  const [marketFilter, setMarketFilter] = useStateS('all');
  const [recencyDays, setRecencyDays] = useStateS(60);
  const [expandedKey, setExpandedKey] = useStateS(null);
  const [aiCache, setAiCache] = useStateS({}); // key -> {state:'idle'|'loading'|'ready'|'error', data, error}
  const [aiEnabled, setAiEnabled] = useStateS(true);

  // Aggregate signals across universe
  const allSignals = useMemoS(() => {
    const out = [];
    universe.forEach((u) => {
      const d = data[u.symbol];
      const lastT = d.candles[d.candles.length - 1].t;
      d.signals.forEach((s) => {
        const ageDays = Math.round((lastT - s.t) / (24 * 3600 * 1000));
        out.push({ ...s, symbol: u.symbol, market: u.market, name: u.name, exch: u.exch, currency: u.currency, ageDays, candle: d.candles[s.i] });
      });
    });
    return out.sort((a, b) => b.t - a.t);
  }, [universe, data]);

  const dirOf = window.MarketData.helpers.signalDirection || ((k) => (k === 'golden_cross' || k === 'rsi_oversold' || k === 'macd_bull_cross' || k === 'rsi_bull_div' ? 'buy' : 'sell'));
  const filtered = allSignals.filter((s) => {
    if (s.ageDays > recencyDays) return false;
    if (marketFilter !== 'all' && s.market !== marketFilter) return false;
    const isBuy = dirOf(s.kind) === 'buy';
    if (filter === 'buy' && !isBuy) return false;
    if (filter === 'sell' && isBuy) return false;
    return true;
  });

  // Stats
  const buys = filtered.filter((s) => dirOf(s.kind) === 'buy').length;
  const sells = filtered.length - buys;
  const last7 = filtered.filter((s) => s.ageDays <= 7).length;

  // AI explainer — calls Groq llama-3.3-70b-versatile via window.api.aiExplain.
  // Demo mode synthesises a plausible response so the UI is testable without a backend.
  function keyOf(s) {
    return s.symbol + '|' + s.kind + '|' + s.t;
  }

  async function explain(s) {
    const key = keyOf(s);
    if (aiCache[key]?.state === 'ready' || aiCache[key]?.state === 'loading') return;
    setAiCache((c) => ({ ...c, [key]: { state: 'loading' } }));

    // Demo mode: synthesise a plausible-looking response so the UI is testable
    // without a backend. Real mode (default) calls the FastAPI Groq adapter.
    if (window.DEMO_MODE) {
      await new Promise((r) => setTimeout(r, 300));
      setAiCache((c) => ({
        ...c,
        [key]: {
          state: 'ready',
          data: {
            summary: '[데모] ' + (s.label || s.kind) + ' 발생',
            detail: '데모 모드입니다. 실제 LLM 해설은 백엔드(GROQ_API_KEY) 설정 후 사용 가능합니다.',
            confidence: 'medium',
            disclaimer: '본 해설은 참고용이며 투자 자문이 아닙니다.',
          },
        },
      }));
      return;
    }

    try {
      const inst = data[s.symbol];
      const i = s.i;
      const candle = inst.candles[i];
      const ind = inst.ind;

      // Backend rebuilds its own indicator context from the OHLCV cache, but
      // we forward what the chart is currently showing so the LLM and the user
      // see the same numbers. Backend ignores keys it doesn't need.
      const indicators_at_signal = {
        rsi:        ind.rsi14[i] != null ? Number(ind.rsi14[i]) : null,
        macd:       ind.macd.line[i] != null ? Number(ind.macd.line[i]) : null,
        macd_signal: ind.macd.signal[i] != null ? Number(ind.macd.signal[i]) : null,
        sma_short:  ind.ma20[i] != null ? Number(ind.ma20[i]) : null,
        sma_long:   ind.ma60[i] != null ? Number(ind.ma60[i]) : null,
        bb_upper:   ind.bb.up[i] != null ? Number(ind.bb.up[i]) : null,
        bb_lower:   ind.bb.lo[i] != null ? Number(ind.bb.lo[i]) : null,
      };

      const body = {
        market:       s.market === 'kr' ? 'kr_stock' : 'crypto',
        symbol:       (s.symbol || '').replace('/', ''),
        interval:     '1d',
        signal_kind:  s.kind,
        timestamp:    s.t,
        price:        candle.c,
        indicators_at_signal,
      };

      const resp = await window.api.aiExplain(body, { timeout: 20000 });
      setAiCache((c) => ({
        ...c,
        [key]: {
          state: 'ready',
          data: {
            summary:    resp.summary,
            detail:     resp.detail,
            confidence: resp.confidence,
            model:      resp.model,
            disclaimer: resp.disclaimer,
          },
        },
      }));
    } catch (e) {
      const msg = e && e.code === 'AI_SERVICE_ERROR'
        ? 'AI 해설 사용 불가 — GROQ_API_KEY 설정 필요'
        : (e && e.message) || String(e);
      setAiCache((c) => ({ ...c, [key]: { state: 'error', error: msg } }));
    }
  }

  function toggleExpand(s) {
    const key = keyOf(s);
    if (expandedKey === key) {
      setExpandedKey(null);
    } else {
      setExpandedKey(key);
      if (aiEnabled && !aiCache[key]) explain(s);
    }
  }

  // Group by symbol — for the heatmap
  const bySymbol = useMemoS(() => {
    const m = {};
    universe.forEach((u) => (m[u.symbol] = { instrument: u, signals: [] }));
    filtered.forEach((s) => m[s.symbol].signals.push(s));
    return m;
  }, [filtered, universe]);

  return (
    <div className="signals-page" data-screen-label="02 매매신호">
      <div className="sp-header">
        <div className="sp-title-block">
          <div className="sp-title">매매 신호</div>
          <div className="sp-sub muted">전 종목 통합 신호 피드 · 최근 {recencyDays}일</div>
        </div>
        <div className="sp-stats">
          <SpStat label="총 신호" value={filtered.length} />
          <SpStat label="매수" value={buys} tone="up" />
          <SpStat label="매도" value={sells} tone="down" />
          <SpStat label="최근 7일" value={last7} />
        </div>
      </div>

      <div className="sp-toolbar">
        <div className="sp-filter-group">
          <span className="sp-filter-label">방향</span>
          {[['all', '전체'], ['buy', '매수'], ['sell', '매도']].map(([k, l]) => (
            <button key={k} className={'sp-chip' + (filter === k ? ' active' : '')} onClick={() => setFilter(k)}>{l}</button>
          ))}
        </div>
        <div className="sp-filter-group">
          <span className="sp-filter-label">시장</span>
          {[['all', '전체'], ['kr', 'KR'], ['crypto', 'CRYPTO']].map(([k, l]) => (
            <button key={k} className={'sp-chip' + (marketFilter === k ? ' active' : '')} onClick={() => setMarketFilter(k)}>{l}</button>
          ))}
        </div>
        <div className="sp-filter-group">
          <span className="sp-filter-label">기간</span>
          {[7, 30, 60, 120, 240].map((d) => (
            <button key={d} className={'sp-chip' + (recencyDays === d ? ' active' : '')} onClick={() => setRecencyDays(d)}>{d}일</button>
          ))}
        </div>
        <div className="sp-filter-group sp-filter-end">
          <span className="sp-filter-label">AI 해설</span>
          <button className={'sp-chip ai-chip' + (aiEnabled ? ' active' : '')} onClick={() => setAiEnabled(!aiEnabled)}>
            <span className="ai-dot" />
            {aiEnabled ? 'ON' : 'OFF'}
          </button>
          <span className="sp-model-tag mono muted">{aiCache[expandedKey]?.data?.model || 'llama-3.3-70b-versatile'}</span>
        </div>
      </div>

      <div className="sp-grid">
        {/* Left: heatmap by symbol */}
        <div className="sp-heatmap">
          <div className="panel-header"><span className="panel-title">종목별 신호 히트맵</span></div>
          <div className="hm-rows">
            {universe.map((u) => {
              const ent = bySymbol[u.symbol];
              const buy = ent.signals.filter((s) => dirOf(s.kind) === 'buy').length;
              const sell = ent.signals.length - buy;
              const total = buy + sell;
              return (
                <button
                  key={u.symbol}
                  className={'hm-row' + (currentSymbol === u.symbol ? ' active' : '')}
                  onClick={() => setCurrent(u.symbol)}
                >
                  <div className="hm-sym">
                    <span className={'market-tag ' + u.market}>{u.exch}</span>
                    <span className="mono hm-code">{u.symbol}</span>
                    <span className="hm-name">{u.name}</span>
                  </div>
                  <div className="hm-bar">
                    <div className="hm-buy" style={{ width: total ? (buy / Math.max(total, 1)) * 100 + '%' : '0%' }} title={buy + '건 매수'} />
                    <div className="hm-sell" style={{ width: total ? (sell / Math.max(total, 1)) * 100 + '%' : '0%' }} title={sell + '건 매도'} />
                  </div>
                  <div className="hm-counts mono">
                    <span className="up">{buy}</span>
                    <span className="muted">/</span>
                    <span className="down">{sell}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: feed */}
        <div className="sp-feed">
          <div className="panel-header"><span className="panel-title">신호 피드</span><span className="panel-count mono">{filtered.length}</span></div>
          <div className="feed-table">
            <div className="feed-head">
              <span>방향</span>
              <span>종목</span>
              <span>유형</span>
              <span>발생일</span>
              <span>가격</span>
              <span>경과</span>
              <span>강도</span>
              <span></span>
            </div>
            <div className="feed-body">
              {filtered.length === 0 && <div className="empty">조건에 맞는 신호가 없습니다.</div>}
              {filtered.slice(0, 80).map((s, i) => {
                const isBuy = dirOf(s.kind) === 'buy';
                const k = keyOf(s);
                const expanded = expandedKey === k;
                const ai = aiCache[k];
                return (
                  <div key={k} className={'feed-item ' + (isBuy ? 'buy' : 'sell') + (expanded ? ' expanded' : '')}>
                    <div className="feed-row" onClick={() => toggleExpand(s)} role="button">
                      <span className={'sig-badge ' + (isBuy ? 'up' : 'down')}>{isBuy ? 'BUY' : 'SELL'}</span>
                      <span className="feed-sym">
                        <span className={'market-tag ' + s.market}>{s.exch}</span>
                        <span className="mono">{s.symbol}</span>
                        <span className="muted feed-name">{s.name}</span>
                      </span>
                      <span className="feed-kind">
                        {s.label}
                        {aiEnabled && (
                          <span className={'ai-pill ' + (ai?.state || 'idle')} title={ai?.state === 'ready' ? 'AI 해설 준비됨' : ai?.state === 'loading' ? 'AI 해설 생성 중' : ai?.state === 'error' ? 'AI 해설 실패' : 'AI 해설 사용 가능'}>
                            {ai?.state === 'loading' ? '···' : 'AI'}
                          </span>
                        )}
                      </span>
                      <span className="mono">{fmt.date(s.t)}</span>
                      <span className="mono">{fmt.price(s.candle.c, s.currency)}</span>
                      <span className="mono muted">{s.ageDays}d</span>
                      <span className="feed-strength">
                        <span className="feed-strength-bar" style={{ width: (s.strength * 100) + '%' }} />
                      </span>
                      <span className={'feed-caret' + (expanded ? ' open' : '')}>▾</span>
                    </div>
                    {expanded && (
                      <AIExplainer
                        signal={s}
                        ai={ai}
                        aiEnabled={aiEnabled}
                        onRetry={() => explain(s)}
                        onJumpChart={() => setCurrent(s.symbol)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SpStat({ label, value, tone }) {
  return (
    <div className={'sp-stat tone-' + (tone || 'side')}>
      <div className="sp-stat-label">{label}</div>
      <div className="sp-stat-value mono">{value}</div>
    </div>
  );
}

// ─── AI Explainer panel ────────────────────────────────────
function AIExplainer({ signal, ai, aiEnabled, onRetry, onJumpChart }) {
  const data = ai?.data;
  const state = ai?.state || (aiEnabled ? 'idle' : 'disabled');

  return (
    <div className="ai-panel">
      <div className="ai-panel-grid">
        {/* Left: signal context */}
        <div className="ai-context">
          <div className="ai-section-label">신호 컨텍스트</div>
          <div className="ai-ctx-grid">
            <div><span className="muted">유형</span><span className="mono">{signal.kind}</span></div>
            <div><span className="muted">방향</span><span className={'mono ' + (signal.direction === 'buy' ? 'up' : 'down')}>{signal.direction || (ai?.data?.direction)}</span></div>
            <div><span className="muted">강도</span><span className="mono">{(signal.strength * 100).toFixed(0)}%</span></div>
            <div><span className="muted">발생가</span><span className="mono">{fmt.price(signal.candle.c, signal.currency)}</span></div>
            <div><span className="muted">경과</span><span className="mono">{signal.ageDays}일 전</span></div>
            <div><span className="muted">시장</span><span className="mono">{signal.exch}</span></div>
          </div>
          <div className="ai-actions">
            <button className="ai-btn" onClick={onJumpChart}>차트로 이동 →</button>
          </div>
        </div>

        {/* Right: AI output */}
        <div className="ai-output">
          <div className="ai-output-head">
            <span className="ai-section-label">AI 해설</span>
            <span className="ai-meta mono muted">{data?.model || 'llama-3.3-70b-versatile'} · Groq</span>
            {state === 'ready' && data?.confidence && (
              <span className={'ai-conf ai-conf-' + data.confidence}>신뢰도 {data.confidence}</span>
            )}
            {state === 'ready' && (
              <button className="ai-btn-mini" onClick={onRetry} title="다시 생성">⟳</button>
            )}
          </div>

          {state === 'disabled' && (
            <div className="ai-msg muted">AI 해설이 비활성화되었습니다. 상단 토글로 켜세요.</div>
          )}
          {state === 'idle' && aiEnabled && (
            <div className="ai-msg">
              <button className="ai-btn primary" onClick={onRetry}>AI 해설 생성</button>
            </div>
          )}
          {state === 'loading' && (
            <div className="ai-loading">
              <div className="ai-skel ai-skel-1" />
              <div className="ai-skel ai-skel-2" />
              <div className="ai-skel ai-skel-3" />
              <div className="ai-loading-label muted mono">생성 중…</div>
            </div>
          )}
          {state === 'error' && (
            <div className="ai-msg error">
              <div>해설 생성 실패</div>
              <div className="muted mono ai-err-detail">{ai.error}</div>
              <button className="ai-btn" onClick={onRetry}>다시 시도</button>
            </div>
          )}
          {state === 'ready' && data && (
            <div className="ai-result">
              <div className="ai-summary">{data.summary}</div>
              <div className="ai-detail">{data.detail}</div>
              {data.watch && (
                <div className="ai-watch">
                  <span className="ai-watch-label">모니터링</span>
                  <span>{data.watch}</span>
                </div>
              )}
              {Array.isArray(data.rationale_keys) && data.rationale_keys.length > 0 && (
                <div className="ai-keys">
                  {data.rationale_keys.map((k, i) => <span key={i} className="ai-key-chip">{k}</span>)}
                </div>
              )}
              <div className="ai-disclaimer muted">
                ⚠ 본 해설은 LLM이 생성한 자동 분석이며 투자 판단 근거로 사용해서는 안 됩니다. 실제 매매는 본인의 판단과 책임으로 진행하세요.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { SignalsPage });
