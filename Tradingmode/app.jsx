// Trading workspace — Chart Analysis + Backtesting
// Single-page app with two main tabs and a shared watchlist sidebar.

const { useState, useEffect, useMemo, useRef, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "upDownConvention": "western"
}/*EDITMODE-END*/;

function useTweaks(defaults) {
  const [tweaks, setTweaks] = useState(defaults);
  const setTweak = useCallback((keyOrObj, value) => {
    const edits = typeof keyOrObj === 'string' ? { [keyOrObj]: value } : keyOrObj;
    setTweaks((prev) => ({ ...prev, ...edits }));
    try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*'); } catch (_) {}
  }, []);
  return [tweaks, setTweak];
}

// ─── Top bar ──────────────────────────────────────────────────
function TopBar({ now, fxKRW, btcSpot, marketState }) {
  return (
    <div className="topbar">
      <div className="topbar-left">
        <div className="logo">
          <span className="logo-mark" />
          <span className="logo-text">TRADINGMODE<span className="logo-dim">.LAB</span></span>
        </div>
        <div className="version">v0.1.0 · DEV</div>
      </div>
      <div className="topbar-mid">
        <Tape label="KOSPI" value="2,748.31" change={+0.42} />
        <Tape label="KOSDAQ" value="887.04" change={-0.31} />
        <Tape label="USD/KRW" value={fmt.price(fxKRW, 'KRW')} change={+0.18} />
        <Tape label="BTC" value={'$' + fmt.price(btcSpot)} change={+1.94} />
        <Tape label="DXY" value="104.62" change={-0.07} />
        <Tape label="VIX" value="14.83" change={+2.10} />
      </div>
      <div className="topbar-right">
        <div className="market-state">
          <span className="dot live" />
          <span>{marketState}</span>
        </div>
        <div className="clock">
          <span className="muted">KST</span>
          <span className="mono">{new Date(now).toLocaleTimeString('ko-KR', { hour12: false })}</span>
        </div>
      </div>
    </div>
  );
}

function Tape({ label, value, change }) {
  const up = change >= 0;
  return (
    <div className="tape">
      <span className="tape-label">{label}</span>
      <span className="tape-value">{value}</span>
      <span className={'tape-change ' + (up ? 'up' : 'down')}>
        {up ? '▲' : '▼'} {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  );
}

// ─── Watchlist ────────────────────────────────────────────────
function Watchlist({ universe, data, current, setCurrent, upColor, downColor }) {
  const [filter, setFilter] = useState('all');
  const filtered = universe.filter((u) => filter === 'all' || u.market === filter);
  return (
    <div className="watchlist">
      <div className="panel-header">
        <span className="panel-title">관심 종목</span>
        <span className="panel-count mono">{filtered.length}</span>
      </div>
      <div className="watchlist-tabs">
        {[['all', '전체'], ['kr', 'KR'], ['crypto', 'CRYPTO']].map(([k, l]) => (
          <button key={k} className={'wl-tab' + (filter === k ? ' active' : '')} onClick={() => setFilter(k)}>{l}</button>
        ))}
      </div>
      <div className="watchlist-head">
        <span>SYMBOL</span>
        <span>PRICE</span>
        <span>%CHG</span>
        <span>30D</span>
      </div>
      <div className="watchlist-rows">
        {filtered.map((u) => {
          const d = data[u.symbol];
          const last = d.candles[d.candles.length - 1];
          const prev = d.candles[d.candles.length - 2];
          const ch = (last.c - prev.c) / prev.c;
          const up = ch >= 0;
          return (
            <button
              key={u.symbol}
              className={'wl-row' + (u.symbol === current ? ' active' : '')}
              onClick={() => setCurrent(u.symbol)}
            >
              <div className="wl-sym">
                <span className={'market-tag ' + u.market}>{u.exch}</span>
                <span className="wl-code mono">{u.symbol}</span>
                <span className="wl-name">{u.name}</span>
              </div>
              <div className="wl-price mono">{fmt.price(last.c, u.currency)}</div>
              <div className={'wl-chg mono ' + (up ? 'up' : 'down')}>
                {up ? '+' : ''}{(ch * 100).toFixed(2)}%
              </div>
              <div className="wl-spark"><MiniSpark candles={d.candles} upColor={upColor} downColor={downColor} /></div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Data status bar (mock loading/error states) ─────────────
function DataStatusBar({ instrument, interval, dataState, setDataState }) {
  const tones = {
    ok: { dot: 'var(--up)', label: 'OK', text: 'var(--text)' },
    loading: { dot: 'oklch(0.78 0.16 75)', label: 'LOADING', text: 'oklch(0.85 0.16 75)' },
    error: { dot: 'var(--down)', label: 'ERROR', text: 'var(--down)' },
    rate_limit: { dot: 'oklch(0.72 0.18 50)', label: 'RATE LIMIT', text: 'oklch(0.85 0.18 50)' },
  };
  const t = tones[dataState.status] || tones.ok;
  return (
    <div className={'data-status data-status-' + dataState.status}>
      <span className="ds-left">
        <span className="ds-dot" style={{ background: t.dot }} />
        <span className="ds-status mono" style={{ color: t.text }}>{t.label}</span>
        <span className="ds-msg">{dataState.message}</span>
      </span>
      <span className="ds-right mono muted">
        <span>{dataState.source}</span>
        <span className="ds-sep">·</span>
        <span>{instrument.meta.symbol} / {interval}</span>
        <span className="ds-sep">·</span>
        <span>cache: data/{instrument.meta.market}/{instrument.meta.symbol}/{interval}</span>
        <span className="ds-sep">·</span>
        <span className="ds-sim-group">
          <button className="ds-sim" onClick={() => setDataState({ status: 'ok', message: '캐시 적중', source: instrument.meta.market === 'crypto' ? 'Binance Spot' : 'pykrx' })}>OK</button>
          <button className="ds-sim" onClick={() => setDataState({ status: 'loading', message: '데이터 수집 중…', source: instrument.meta.market === 'crypto' ? 'Binance Spot' : 'pykrx' })}>LOAD</button>
          <button className="ds-sim" onClick={() => setDataState({ status: 'rate_limit', message: 'Binance 1200 req/min 초과 — 60초 백오프', source: 'Binance Spot' })}>429</button>
          <button className="ds-sim" onClick={() => setDataState({ status: 'error', message: 'DataSourceError: timeout after 3 retries', source: instrument.meta.market === 'crypto' ? 'Binance Spot' : 'pykrx' })}>ERR</button>
        </span>
      </span>
    </div>
  );
}

// ─── Chart Analysis page ──────────────────────────────────────
function ChartPage({ instrument, upColor, downColor, indicators, setIndicators, signalsOn, setSignalsOn, trendBand, setTrendBand, dataState, setDataState }) {
  const [view, setView] = useState([instrument.candles.length - 120, instrument.candles.length]);
  const [hoverIdx, setHoverIdx] = useState(null);
  const [interval, setIntervalTf] = useState('1d');
  const [zoomLevel, setZoomLevel] = useState('3M');
  const [drawing, setDrawing] = useState(null); // 'trend' | 'fib' | null
  const [drawings, setDrawings] = useState([]);

  // Reset view when instrument changes
  useEffect(() => { setView([instrument.candles.length - 120, instrument.candles.length]); setDrawings([]); setDrawing(null); }, [instrument.meta.symbol]);

  // Mock loading when interval changes
  function changeInterval(iv) {
    if (iv === interval) return;
    setIntervalTf(iv);
    setDataState({ status: 'loading', message: `${instrument.meta.symbol} ${iv} 데이터 수집 중…`, source: instrument.meta.market === 'crypto' ? 'Binance Spot' : 'pykrx' });
    setTimeout(() => setDataState({ status: 'ok', message: '캐시 적중', source: instrument.meta.market === 'crypto' ? 'Binance Spot' : 'pykrx' }), 700);
  }

  const last = instrument.candles[instrument.candles.length - 1];
  const prev = instrument.candles[instrument.candles.length - 2];
  const dayChg = (last.c - prev.c) / prev.c;
  const range = view[1] - view[0];

  function pan(dir) {
    setView(([a, b]) => {
      const step = Math.floor(range * 0.25) * dir;
      const na = Math.max(0, Math.min(instrument.candles.length - range, a + step));
      return [na, na + range];
    });
  }
  function zoom(dir) {
    setView(([a, b]) => {
      const newRange = Math.max(40, Math.min(instrument.candles.length, Math.round(range * (dir > 0 ? 0.75 : 1.33))));
      const center = Math.round((a + b) / 2);
      const na = Math.max(0, Math.min(instrument.candles.length - newRange, center - Math.round(newRange / 2)));
      return [na, na + newRange];
    });
  }

  const trendCounts = useMemo(() => {
    const c = { up: 0, down: 0, side: 0 };
    instrument.trend.slice(view[0], view[1]).forEach((t) => (c[t]++));
    const total = c.up + c.down + c.side;
    return { ...c, total };
  }, [instrument, view]);

  const hovered = hoverIdx != null ? instrument.candles[hoverIdx] : last;
  const hoveredPrev = hoverIdx != null ? instrument.candles[Math.max(0, hoverIdx - 1)] : prev;
  const hChg = (hovered.c - hoveredPrev.c) / hoveredPrev.c;

  return (
    <div className="chart-page" data-screen-label="01 차트분석">
      {/* Data status bar */}
      <DataStatusBar instrument={instrument} interval={interval} dataState={dataState} setDataState={setDataState} />
      {/* Header strip */}
      <div className="instrument-header">
        <div className="ih-left">
          <div className="ih-symbol">
            <span className={'market-tag ' + instrument.meta.market}>{instrument.meta.exch}</span>
            <span className="ih-code mono">{instrument.meta.symbol}</span>
            <span className="ih-name">{instrument.meta.name}</span>
          </div>
          <div className="ih-prices">
            <span className="ih-price mono">{fmt.price(last.c, instrument.meta.currency)}</span>
            <span className={'ih-chg mono ' + (dayChg >= 0 ? 'up' : 'down')}>
              {dayChg >= 0 ? '+' : ''}{fmt.price(last.c - prev.c, instrument.meta.currency)} ({(dayChg * 100).toFixed(2)}%)
            </span>
          </div>
          <div className="ih-ohlc mono">
            <span><b>O</b> {fmt.price(last.o, instrument.meta.currency)}</span>
            <span><b>H</b> {fmt.price(last.h, instrument.meta.currency)}</span>
            <span><b>L</b> {fmt.price(last.l, instrument.meta.currency)}</span>
            <span><b>V</b> {fmt.vol(last.v)}</span>
          </div>
        </div>
        <div className="ih-right">
          <div className="tf-group" title="타임프레임 (인터벌)">
            {['1m', '5m', '15m', '1h', '4h', '1d'].map((iv) => (
              <button key={iv} className={'tf-btn' + (interval === iv ? ' active' : '')} onClick={() => changeInterval(iv)}>{iv}</button>
            ))}
          </div>
          <div className="tf-group" title="기간 (줌)">
            {['1M', '3M', '6M', '1Y', 'ALL'].map((t) => (
              <button key={t} className={'tf-btn zoom' + (zoomLevel === t ? ' active' : '')} onClick={() => {
                setZoomLevel(t);
                const N = instrument.candles.length;
                const map = { '1M': 30, '3M': 90, '6M': 130, '1Y': 200, 'ALL': N };
                const r = map[t];
                setView([Math.max(0, N - r), N]);
              }}>{t}</button>
            ))}
          </div>
          <div className="tool-group">
            <button className={'tool-btn' + (drawing === 'trend' ? ' active' : '')} onClick={() => setDrawing(drawing === 'trend' ? null : 'trend')} title="추세선">
              <svg viewBox="0 0 16 16" width="14" height="14"><path d="M2 13L13 3" stroke="currentColor" strokeWidth="1.4" /><circle cx="2" cy="13" r="1.5" fill="currentColor" /><circle cx="13" cy="3" r="1.5" fill="currentColor" /></svg>
              <span>추세선</span>
            </button>
            <button className={'tool-btn' + (drawing === 'fib' ? ' active' : '')} onClick={() => setDrawing(drawing === 'fib' ? null : 'fib')} title="피보나치">
              <svg viewBox="0 0 16 16" width="14" height="14"><line x1="1" x2="15" y1="3" y2="3" stroke="currentColor" strokeWidth="1" /><line x1="1" x2="15" y1="6" y2="6" stroke="currentColor" strokeWidth="1" /><line x1="1" x2="15" y1="10" y2="10" stroke="currentColor" strokeWidth="1" /><line x1="1" x2="15" y1="13" y2="13" stroke="currentColor" strokeWidth="1" /></svg>
              <span>피보나치</span>
            </button>
            <button className="tool-btn" onClick={() => pan(-1)} title="←"><span>◀</span></button>
            <button className="tool-btn" onClick={() => pan(1)} title="→"><span>▶</span></button>
            <button className="tool-btn" onClick={() => zoom(1)} title="확대"><span>＋</span></button>
            <button className="tool-btn" onClick={() => zoom(-1)} title="축소"><span>−</span></button>
            {drawings.length > 0 && (
              <button className="tool-btn" onClick={() => setDrawings([])} title="지우기" style={{ color: 'var(--down)' }}><span>✕</span><span>{drawings.length}</span></button>
            )}
          </div>
        </div>
      </div>

      {/* Chart stack */}
      <div className="chart-stack">
        <div className="chart-pane" style={{ height: 420 }}>
          <CandleChart
            instrument={instrument}
            view={view}
            hoverIdx={hoverIdx}
            setHoverIdx={setHoverIdx}
            indicators={indicators}
            signalsOn={signalsOn}
            trendBand={trendBand}
            upColor={upColor}
            downColor={downColor}
            drawing={drawing}
            drawings={drawings}
            setDrawings={setDrawings}
            setDrawing={setDrawing}
          />
          {drawing && (
            <div className="drawing-banner">
              <span className="dot live" /> {drawing === 'trend' ? '추세선' : '피보나치'} 도구 — 차트에서 두 점을 클릭하세요 <button onClick={() => setDrawing(null)}>취소</button>
            </div>
          )}
          {hoverIdx != null && (
            <div className="hover-readout mono">
              <span>{fmt.date(instrument.candles[hoverIdx].t)}</span>
              <span><b>O</b> {fmt.price(instrument.candles[hoverIdx].o, instrument.meta.currency)}</span>
              <span><b>H</b> {fmt.price(instrument.candles[hoverIdx].h, instrument.meta.currency)}</span>
              <span><b>L</b> {fmt.price(instrument.candles[hoverIdx].l, instrument.meta.currency)}</span>
              <span><b>C</b> {fmt.price(instrument.candles[hoverIdx].c, instrument.meta.currency)}</span>
              <span className={hChg >= 0 ? 'up' : 'down'}>{(hChg * 100).toFixed(2)}%</span>
            </div>
          )}
        </div>
        <div className="chart-pane" style={{ height: 70 }}>
          <VolumeChart instrument={instrument} view={view} upColor={upColor} downColor={downColor} hoverIdx={hoverIdx} />
        </div>
        <div className="chart-pane" style={{ height: 90 }}>
          <RSIChart instrument={instrument} view={view} hoverIdx={hoverIdx} />
        </div>
        <div className="chart-pane" style={{ height: 90 }}>
          <MACDChart instrument={instrument} view={view} hoverIdx={hoverIdx} upColor={upColor} downColor={downColor} />
        </div>
      </div>

      {/* Trend timeline */}
      <div className="trend-timeline">
        <div className="tt-label">추세 분포 (현재 뷰)</div>
        <div className="tt-bar">
          <div className="tt-seg up" style={{ width: (trendCounts.up / trendCounts.total * 100) + '%' }}><span>{Math.round(trendCounts.up / trendCounts.total * 100)}% 상승</span></div>
          <div className="tt-seg side" style={{ width: (trendCounts.side / trendCounts.total * 100) + '%' }}><span>{Math.round(trendCounts.side / trendCounts.total * 100)}% 횡보</span></div>
          <div className="tt-seg down" style={{ width: (trendCounts.down / trendCounts.total * 100) + '%' }}><span>{Math.round(trendCounts.down / trendCounts.total * 100)}% 하락</span></div>
        </div>
      </div>
    </div>
  );
}

// ─── Right side panel: indicator toggles + signal feed ──────
function RightPanel({ instrument, indicators, setIndicators, signalsOn, setSignalsOn, trendBand, setTrendBand, upColor, downColor }) {
  const last = instrument.candles[instrument.candles.length - 1];
  const lastRsi = instrument.ind.rsi14[instrument.ind.rsi14.length - 1];
  const lastMacd = instrument.ind.macd.line[instrument.ind.macd.line.length - 1];
  const lastSig = instrument.ind.macd.signal[instrument.ind.macd.signal.length - 1];
  const lastTrend = instrument.trend[instrument.trend.length - 1];
  const recentSignals = instrument.signals.slice(-12).reverse();

  return (
    <div className="right-panel">
      <div className="panel-section">
        <div className="panel-header">
          <span className="panel-title">현재 상태</span>
        </div>
        <div className="status-grid">
          <StatusCell label="추세" value={lastTrend === 'up' ? '상승' : lastTrend === 'down' ? '하락' : '횡보'} tone={lastTrend} />
          <StatusCell label="RSI 14" value={lastRsi?.toFixed(1)} tone={lastRsi > 70 ? 'down' : lastRsi < 30 ? 'up' : 'side'} sub={lastRsi > 70 ? '과매수' : lastRsi < 30 ? '과매도' : '중립'} />
          <StatusCell label="MACD" value={lastMacd?.toFixed(2)} tone={lastMacd > lastSig ? 'up' : 'down'} sub={lastMacd > lastSig ? '시그널 위' : '시그널 아래'} />
          <StatusCell label="MA20→60" value={instrument.ind.ma20[instrument.ind.ma20.length - 1] > instrument.ind.ma60[instrument.ind.ma60.length - 1] ? '정배열' : '역배열'} tone={instrument.ind.ma20[instrument.ind.ma20.length - 1] > instrument.ind.ma60[instrument.ind.ma60.length - 1] ? 'up' : 'down'} />
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-header">
          <span className="panel-title">지표 오버레이</span>
        </div>
        <div className="ind-list">
          <IndToggle label="MA 20" color="oklch(0.78 0.16 75)" on={indicators.ma20} onChange={(v) => setIndicators({ ...indicators, ma20: v })} />
          <IndToggle label="MA 60" color="oklch(0.70 0.13 230)" on={indicators.ma60} onChange={(v) => setIndicators({ ...indicators, ma60: v })} />
          <IndToggle label="MA 120" color="oklch(0.62 0.18 320)" on={indicators.ma120} onChange={(v) => setIndicators({ ...indicators, ma120: v })} />
          <IndToggle label="볼린저밴드 (20,2)" color="rgba(150,180,220,0.7)" on={indicators.bb} onChange={(v) => setIndicators({ ...indicators, bb: v })} />
          <IndToggle label="신호 마커" color="oklch(0.78 0.16 75)" on={signalsOn} onChange={setSignalsOn} />
          <IndToggle label="추세 영역 음영" color={upColor} on={trendBand} onChange={setTrendBand} />
        </div>
      </div>

      <div className="panel-section grow">
        <div className="panel-header">
          <span className="panel-title">최근 신호</span>
          <span className="panel-count mono">{instrument.signals.length}</span>
        </div>
        <div className="signal-feed">
          {recentSignals.length === 0 && <div className="empty">신호 없음</div>}
          {recentSignals.map((s, i) => {
            const c = instrument.candles[s.i];
            const dir = (window.MarketData.helpers.signalDirection || ((k) => (k === 'golden_cross' || k === 'rsi_oversold' || k === 'macd_bull_cross' || k === 'rsi_bull_div' ? 'buy' : 'sell')))(s.kind);
            const isBuy = dir === 'buy';
            return (
              <div key={i} className={'sig-row ' + (isBuy ? 'buy' : 'sell')}>
                <div className="sig-side">
                  <span className={'sig-badge ' + (isBuy ? 'up' : 'down')}>{isBuy ? 'BUY' : 'SELL'}</span>
                </div>
                <div className="sig-main">
                  <div className="sig-label">{s.label}</div>
                  <div className="sig-meta mono">
                    <span>{fmt.date(c.t)}</span>
                    <span>· {fmt.price(c.c, instrument.meta.currency)}</span>
                  </div>
                </div>
                <div className="sig-strength" title={'강도 ' + (s.strength * 100).toFixed(0) + '%'}>
                  <div className="sig-strength-bar" style={{ width: (s.strength * 100) + '%' }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatusCell({ label, value, tone, sub }) {
  return (
    <div className={'status-cell tone-' + (tone || 'side')}>
      <div className="sc-label">{label}</div>
      <div className="sc-value mono">{value}</div>
      {sub && <div className="sc-sub">{sub}</div>}
    </div>
  );
}

function IndToggle({ label, color, on, onChange }) {
  return (
    <button className={'ind-toggle' + (on ? ' on' : '')} onClick={() => onChange(!on)}>
      <span className="ind-swatch" style={{ background: color }} />
      <span className="ind-label">{label}</span>
      <span className={'ind-state mono' + (on ? ' on' : '')}>{on ? 'ON' : 'OFF'}</span>
    </button>
  );
}

// ─── Backtest page ────────────────────────────────────────────
function BacktestPage({ instrument, upColor, downColor }) {
  const [strategy, setStrategy] = useState('ma_cross');
  const [params, setParams] = useState({ fast: 20, slow: 60, capital: 10000000, fee: 0.05 });
  const [hoveredTrade, setHoveredTrade] = useState(null);

  const strategies = [
    { id: 'ma_cross', name: 'MA 크로스', desc: 'MA20 ↑ MA60 진입 / 데드크로스 청산' },
    { id: 'rsi', name: 'RSI 역추세', desc: 'RSI<30 진입 / RSI>70 청산' },
    { id: 'macd', name: 'MACD 시그널', desc: 'MACD 라인 ↑ 시그널 진입 / ↓ 청산' },
    { id: 'bb_breakout', name: '볼린저 돌파', desc: '상단 돌파 진입 / 중단선 회귀 청산' },
  ];

  const stats = instrument.stats;
  const trades = instrument.trades;
  const wins = trades.filter((t) => t.ret > 0);
  const losses = trades.filter((t) => t.ret <= 0);
  const avgWin = wins.length ? wins.reduce((a, b) => a + b.ret, 0) / wins.length : 0;
  const avgLoss = losses.length ? losses.reduce((a, b) => a + b.ret, 0) / losses.length : 0;
  const pf = losses.length && avgLoss !== 0 ? Math.abs((avgWin * wins.length) / (avgLoss * losses.length)) : 0;
  const finalEq = instrument.equity[instrument.equity.length - 1].eq;
  const finalCap = params.capital * finalEq;

  return (
    <div className="backtest-page" data-screen-label="02 백테스팅">
      <div className="bt-header">
        <div className="bt-title-block">
          <div className="bt-title">백테스팅</div>
          <div className="bt-sub">
            <span className={'market-tag ' + instrument.meta.market}>{instrument.meta.exch}</span>
            <span className="mono">{instrument.meta.symbol}</span>
            <span>{instrument.meta.name}</span>
            <span className="muted">· 240영업일</span>
          </div>
        </div>
        <div className="bt-actions">
          <button className="bt-run">▶ 백테스트 실행</button>
        </div>
      </div>

      <div className="bt-grid">
        {/* Left: strategy + params */}
        <div className="bt-config">
          <div className="panel-section">
            <div className="panel-header"><span className="panel-title">전략</span></div>
            <div className="strat-list">
              {strategies.map((s) => (
                <button key={s.id} className={'strat-row' + (strategy === s.id ? ' active' : '')} onClick={() => setStrategy(s.id)}>
                  <div className="strat-name">{s.name}</div>
                  <div className="strat-desc">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="panel-section">
            <div className="panel-header"><span className="panel-title">파라미터</span></div>
            <div className="param-grid">
              <ParamField label="Fast MA" suffix="일" value={params.fast} min={5} max={50} step={1} onChange={(v) => setParams({ ...params, fast: v })} />
              <ParamField label="Slow MA" suffix="일" value={params.slow} min={20} max={200} step={1} onChange={(v) => setParams({ ...params, slow: v })} />
              <ParamField label="초기 자본" suffix={instrument.meta.currency} value={params.capital} min={1000000} max={100000000} step={1000000} onChange={(v) => setParams({ ...params, capital: v })} format={(v) => v.toLocaleString('ko-KR')} />
              <ParamField label="수수료" suffix="%" value={params.fee} min={0} max={0.5} step={0.01} onChange={(v) => setParams({ ...params, fee: v })} format={(v) => v.toFixed(2)} />
            </div>
          </div>

          <div className="panel-section">
            <div className="panel-header"><span className="panel-title">진입/청산 규칙</span></div>
            <ul className="rule-list">
              <li><b>진입</b>: MA{params.fast} 가 MA{params.slow} 를 상향 돌파 (골든크로스)</li>
              <li><b>청산</b>: MA{params.fast} 가 MA{params.slow} 를 하향 돌파 (데드크로스)</li>
              <li><b>포지션</b>: 풀 포지션 1, 롱 전용</li>
              <li><b>슬리피지</b>: 종가 체결, {params.fee}% 편도 수수료</li>
            </ul>
          </div>
        </div>

        {/* Center: results */}
        <div className="bt-results">
          <div className="bt-stat-row">
            <BigStat label="누적 수익률" value={fmt.pct(stats.totalReturn)} tone={stats.totalReturn >= 0 ? 'up' : 'down'} />
            <BigStat label="최종 자본" value={fmt.price(finalCap, instrument.meta.currency)} sub={instrument.meta.currency} />
            <BigStat label="MDD" value={fmt.pct(stats.maxDD)} tone="down" />
            <BigStat label="샤프 지수" value={stats.sharpe.toFixed(2)} tone={stats.sharpe >= 1 ? 'up' : 'side'} />
            <BigStat label="승률" value={(stats.winRate * 100).toFixed(1) + '%'} sub={`${wins.length}W / ${losses.length}L`} />
            <BigStat label="총 거래" value={stats.trades} sub="회" />
            <BigStat label="평균 수익" value={fmt.pct(avgWin)} tone="up" />
            <BigStat label="평균 손실" value={fmt.pct(avgLoss)} tone="down" />
            <BigStat label="손익비" value={pf.toFixed(2)} tone={pf >= 1.5 ? 'up' : pf >= 1 ? 'side' : 'down'} />
            <BigStat label="평균 보유" value={Math.round(trades.reduce((a, b) => a + b.hold, 0) / Math.max(1, trades.length))} sub="일" />
          </div>

          <div className="bt-chart-block">
            <div className="bt-chart-header">
              <span className="bt-chart-title">자본 곡선</span>
              <span className="bt-chart-meta mono">매수 후 보유 대비 +{(stats.totalReturn * 100 - ((instrument.candles[instrument.candles.length - 1].c / instrument.candles[0].c - 1) * 100)).toFixed(1)}%p</span>
            </div>
            <div className="bt-chart-pane" style={{ height: 240 }}>
              <EquityCurve equity={instrument.equity} trades={trades} upColor={upColor} downColor={downColor} />
            </div>
          </div>

          <div className="bt-chart-block">
            <div className="bt-chart-header">
              <span className="bt-chart-title">최대 낙폭 (Drawdown)</span>
            </div>
            <div className="bt-chart-pane" style={{ height: 90 }}>
              <DrawdownChart equity={instrument.equity} />
            </div>
          </div>

          <div className="bt-trade-table">
            <div className="bt-chart-header"><span className="bt-chart-title">거래 내역</span><span className="bt-chart-meta mono">{trades.length}건</span></div>
            <div className="trade-table-wrap">
              <table className="trade-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>진입일</th>
                    <th>진입가</th>
                    <th>청산일</th>
                    <th>청산가</th>
                    <th>보유</th>
                    <th>수익률</th>
                    <th>누적</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    let cum = 1;
                    return trades.map((t, i) => {
                      cum *= 1 + t.ret;
                      const cumPct = (cum - 1) * 100;
                      return (
                        <tr key={i} className={'tr-' + (t.ret >= 0 ? 'win' : 'loss') + (hoveredTrade === i ? ' active' : '')} onMouseEnter={() => setHoveredTrade(i)} onMouseLeave={() => setHoveredTrade(null)}>
                          <td className="mono">{i + 1}</td>
                          <td className="mono">{fmt.date(t.entryT)}</td>
                          <td className="mono">{fmt.price(t.entryP, instrument.meta.currency)}</td>
                          <td className="mono">{t.open ? <span className="muted">보유중</span> : fmt.date(t.exitT)}</td>
                          <td className="mono">{fmt.price(t.exitP, instrument.meta.currency)}</td>
                          <td className="mono">{t.hold}일</td>
                          <td className={'mono ' + (t.ret >= 0 ? 'up' : 'down')}>{fmt.pct(t.ret)}</td>
                          <td className={'mono ' + (cumPct >= 0 ? 'up' : 'down')}>{cumPct >= 0 ? '+' : ''}{cumPct.toFixed(1)}%</td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BigStat({ label, value, sub, tone }) {
  return (
    <div className={'big-stat tone-' + (tone || 'side')}>
      <div className="bs-label">{label}</div>
      <div className="bs-value mono">{value}</div>
      {sub && <div className="bs-sub mono">{sub}</div>}
    </div>
  );
}

function ParamField({ label, value, min, max, step, suffix, onChange, format }) {
  return (
    <div className="param-field">
      <div className="pf-label">{label}</div>
      <div className="pf-row">
        <input
          type="number"
          className="pf-input mono"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span className="pf-suffix">{suffix}</span>
      </div>
      <input type="range" className="pf-slider" value={value} min={min} max={max} step={step} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

// ─── Tweaks Panel ─────────────────────────────────────────────
function TweaksContent({ tweaks, setTweak }) {
  return (
    <TweakSection title="색상 관습">
      <TweakRadio
        value={tweaks.upDownConvention}
        onChange={(v) => setTweak('upDownConvention', v)}
        options={[
          { value: 'western', label: '서양식 (상승 초록 / 하락 빨강)' },
          { value: 'eastern', label: '동양식 (상승 빨강 / 하락 파랑)' },
        ]}
      />
    </TweakSection>
  );
}

// ─── Backend loading screen (shown until /api/* fan-out completes) ──────
function LoadingScreen({ progress, onUseDemo }) {
  const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <div className="loading-screen">
      <div className="loading-card">
        <div className="loading-logo">
          <span className="logo-mark" />
          <span className="logo-text">TRADINGMODE<span className="logo-dim">.LAB</span></span>
        </div>
        <div className="loading-status">
          백엔드에서 시세·지표·신호를 불러오는 중…
        </div>
        <div className="loading-bar">
          <div className="loading-bar-fill" style={{ width: pct + '%' }} />
        </div>
        <div className="loading-meta mono muted">
          {progress.done} / {progress.total} 종목
          {progress.current ? ' · 현재: ' + progress.current : ''}
        </div>
        <button className="loading-demo-btn" onClick={onUseDemo}>
          데모 모드로 전환 (?demo=1)
        </button>
      </div>
    </div>
  );
}

function ErrorScreen({ error, onRetry, onUseDemo }) {
  return (
    <div className="loading-screen">
      <div className="loading-card error">
        <div className="loading-status">
          ⚠️ 백엔드 연결 실패
        </div>
        <div className="loading-meta mono">
          {error && (error.code || 'NETWORK')}: {error && error.message}
        </div>
        <div className="loading-meta muted" style={{ marginTop: 12 }}>
          백엔드가 실행 중인지 확인하세요:<br/>
          <code className="mono">cd backend && uvicorn main:app --port 8000</code>
        </div>
        <div className="loading-actions">
          <button className="loading-demo-btn" onClick={onRetry}>다시 시도</button>
          <button className="loading-demo-btn" onClick={onUseDemo}>데모 모드</button>
        </div>
      </div>
    </div>
  );
}

// ─── Root App ─────────────────────────────────────────────────
function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const [page, setPage] = useState('chart');
  const [current, setCurrent] = useState('BTC/USDT');
  const [now, setNow] = useState(Date.now());

  const [indicators, setIndicators] = useState({ ma20: true, ma60: true, ma120: false, bb: true });
  const [signalsOn, setSignalsOn] = useState(true);
  const [trendBand, setTrendBand] = useState(true);
  const [dataState, setDataState] = useState(
    window.DEMO_MODE
      ? { status: 'ok', message: '데모 모드 (합성 데이터)', source: 'Synthetic' }
      : { status: 'loading', message: '백엔드 연결 중…', source: 'FastAPI' }
  );

  // Backend loading state — only relevant when DEMO_MODE is off.
  const [dataReady, setDataReady] = useState(window.DEMO_MODE);
  const [loadProgress, setLoadProgress] = useState({ done: 0, total: 0, current: null });
  const [loadError, setLoadError] = useState(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const [dataVersion, setDataVersion] = useState(0);   // bumped after loader swaps DATA
  const [marketSnap, setMarketSnap] = useState(null);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Fetch real instruments from backend on mount (skipped in DEMO_MODE).
  useEffect(() => {
    if (window.DEMO_MODE || !window.loader) return;
    let alive = true;
    const ctl = new AbortController();
    (async () => {
      setLoadError(null);
      setDataState({ status: 'loading', message: '백엔드에서 데이터 수집 중…', source: 'FastAPI' });
      try {
        // Probe backend first so we fail fast with a clearer error.
        await window.api.health({ signal: ctl.signal, timeout: 5000 });
        await window.loader.loadAllInstruments(window.MarketData.UNIVERSE, {
          signal: ctl.signal,
          onProgress: (p) => { if (alive) setLoadProgress(p); },
        });
        if (!alive) return;
        setDataReady(true);
        setDataVersion((v) => v + 1);
        setDataState({ status: 'ok', message: '실데이터 로드 완료', source: 'FastAPI' });
      } catch (e) {
        if (!alive) return;
        if (e.name === 'AbortError') return;
        console.error('[App] backend load failed', e);
        setLoadError(e);
        setDataState({ status: 'error', message: e.message || '백엔드 연결 실패', source: 'FastAPI' });
      }
    })();
    return () => { alive = false; ctl.abort(); };
  }, [retryNonce]);

  // TopBar market snapshot polling (30s, paused when tab is hidden).
  useEffect(() => {
    if (window.DEMO_MODE || !dataReady) return;
    let alive = true;
    let timerId = null;
    const ctlRef = { current: null };

    async function tick() {
      if (!alive || document.visibilityState !== 'visible') return;
      if (ctlRef.current) ctlRef.current.abort();
      ctlRef.current = new AbortController();
      try {
        const snap = await window.api.marketSnapshot({ signal: ctlRef.current.signal, timeout: 8000 });
        if (alive) setMarketSnap(snap);
      } catch (_) { /* TopBar: silent fail */ }
    }
    tick();
    timerId = setInterval(tick, 30000);
    document.addEventListener('visibilitychange', tick);
    return () => {
      alive = false;
      clearInterval(timerId);
      document.removeEventListener('visibilitychange', tick);
      if (ctlRef.current) ctlRef.current.abort();
    };
  }, [dataReady]);

  // Tweaks host wiring
  useEffect(() => {
    function onMsg(e) {
      if (!e.data) return;
      if (e.data.type === '__activate_edit_mode') setTweaksOpen(true);
      if (e.data.type === '__deactivate_edit_mode') setTweaksOpen(false);
    }
    window.addEventListener('message', onMsg);
    try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch (_) {}
    return () => window.removeEventListener('message', onMsg);
  }, []);

  const upColor = tweaks.upDownConvention === 'eastern' ? 'oklch(0.65 0.22 25)' : 'oklch(0.72 0.18 145)';
  const downColor = tweaks.upDownConvention === 'eastern' ? 'oklch(0.70 0.13 250)' : 'oklch(0.65 0.22 25)';

  // Show loading / error screens before the main UI tries to read DATA — the
  // loader will have replaced window.MarketData.DATA by the time we render.
  if (!window.DEMO_MODE && !dataReady) {
    if (loadError) {
      return (
        <ErrorScreen
          error={loadError}
          onRetry={() => setRetryNonce((n) => n + 1)}
          onUseDemo={() => { window.location.search = '?demo=1'; }}
        />
      );
    }
    return (
      <LoadingScreen
        progress={loadProgress}
        onUseDemo={() => { window.location.search = '?demo=1'; }}
      />
    );
  }

  const instrument = window.MarketData.DATA[current];
  const universe = window.MarketData.UNIVERSE;
  const data = window.MarketData.DATA;

  // Skip render briefly when current symbol isn't loaded yet (race during retry).
  if (!instrument) {
    return <LoadingScreen progress={loadProgress} onUseDemo={() => { window.location.search = '?demo=1'; }} />;
  }

  // Use TopBar snapshot from backend when available, fall back to derived values.
  const fxKRW = (marketSnap && marketSnap.usd_krw && marketSnap.usd_krw.value) || 1382.40;
  const btcSpot = (marketSnap && marketSnap.btc && marketSnap.btc.value)
    || data['BTC/USDT'].candles[data['BTC/USDT'].candles.length - 1].c;

  return (
    <div className="app" style={{ ['--up']: upColor, ['--down']: downColor }}>
      <TopBar now={now} fxKRW={fxKRW} btcSpot={btcSpot} marketState="MARKET OPEN · KOSPI" />

      <div className="page-tabs">
        <button className={'pt-btn' + (page === 'chart' ? ' active' : '')} onClick={() => setPage('chart')}>
          <span className="pt-num mono">01</span>
          <span>차트 분석</span>
        </button>
        <button className={'pt-btn' + (page === 'signals' ? ' active' : '')} onClick={() => setPage('signals')}>
          <span className="pt-num mono">02</span>
          <span>매매 신호</span>
        </button>
        <button className={'pt-btn' + (page === 'backtest' ? ' active' : '')} onClick={() => setPage('backtest')}>
          <span className="pt-num mono">03</span>
          <span>백테스팅</span>
        </button>
        <button className={'pt-btn' + (page === 'portfolio' ? ' active' : '')} onClick={() => setPage('portfolio')}>
          <span className="pt-num mono">04</span>
          <span>포트폴리오</span>
        </button>
        <div className="pt-spacer" />
        <div className="pt-meta mono">
          {fmt.date(Date.now())} · {instrument.candles.length}봉 로드됨 · 캐시 HIT
        </div>
      </div>

      <div className="workspace">
        <div className="ws-left">
          <Watchlist universe={universe} data={data} current={current} setCurrent={setCurrent} upColor={upColor} downColor={downColor} />
        </div>
        <div className="ws-main">
          {page === 'chart' ? (
            <ChartPage
              instrument={instrument}
              upColor={upColor}
              downColor={downColor}
              indicators={indicators}
              setIndicators={setIndicators}
              signalsOn={signalsOn}
              setSignalsOn={setSignalsOn}
              trendBand={trendBand}
              setTrendBand={setTrendBand}
              dataState={dataState}
              setDataState={setDataState}
            />
          ) : page === 'signals' ? (
            <SignalsPage universe={universe} data={data} currentSymbol={current} setCurrent={setCurrent} upColor={upColor} downColor={downColor} />
          ) : page === 'portfolio' ? (
            <PortfolioPage universe={universe} data={data} setCurrent={setCurrent} upColor={upColor} downColor={downColor} />
          ) : (
            <BacktestPage instrument={instrument} upColor={upColor} downColor={downColor} />
          )}
        </div>
        {page === 'chart' && (
          <div className="ws-right">
            <RightPanel
              instrument={instrument}
              indicators={indicators}
              setIndicators={setIndicators}
              signalsOn={signalsOn}
              setSignalsOn={setSignalsOn}
              trendBand={trendBand}
              setTrendBand={setTrendBand}
              upColor={upColor}
              downColor={downColor}
            />
          </div>
        )}
      </div>

      {tweaksOpen && (
        <TweaksPanel onClose={() => setTweaksOpen(false)}>
          <TweaksContent tweaks={tweaks} setTweak={setTweak} />
        </TweaksPanel>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
