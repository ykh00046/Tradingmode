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

// ─── Helpers (Design v0.3 §4.2, §4.3) ─────────────────────────
function formatPriceCompact(v) {
  if (v == null || isNaN(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return v.toFixed(2);
}

// Parse a user-typed symbol into a watchlist meta. A 6-digit string is a
// Korean stock code; anything else is treated as a crypto pair (quote
// defaults to USDT). Returns null when the input can't be interpreted.
function parseSymbolInput(raw) {
  const s = String(raw || '').trim().toUpperCase();
  if (!s) return null;
  if (/^\d{6}$/.test(s)) {
    return { symbol: s, name: '', exch: 'KRX', market: 'kr', currency: 'KRW' };
  }
  if (/^\d+$/.test(s)) return null;            // numeric but not a 6-digit KR code
  let base, quote;
  if (s.includes('/')) {
    const parts = s.split('/');
    base = parts[0]; quote = parts[1] || 'USDT';
  } else {
    const m = s.match(/^([A-Z0-9]+?)(USDT|USDC|BUSD|BTC|ETH)$/);
    if (m) { base = m[1]; quote = m[2]; }
    else { base = s; quote = 'USDT'; }
  }
  if (!/^[A-Z0-9]{1,12}$/.test(base) || !/^[A-Z0-9]{2,6}$/.test(quote)) return null;
  return { symbol: base + '/' + quote, name: base, exch: 'Binance', market: 'crypto', currency: quote };
}

function useViewportWidth() {
  const [w, setW] = useState(window.innerWidth);
  useEffect(() => {
    const onResize = () => setW(window.innerWidth);
    window.addEventListener('resize', onResize, { passive: true });
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return w;
}

// ─── Top bar (responsive 1280/1024 — Design v0.3 §5.3) ───────
function TopBar({ now, fxKRW, btcSpot, marketState, snapStale }) {
  const vw = useViewportWidth();
  // Breakpoints are tuned to the actual fit budget: topbar chrome (logo +
  // version on the left, market-state + clock on the right) eats ~570px, so
  // six full tapes (~990px) only fit above ~1560px, and six compact tapes
  // (~810px) only fit above ~1340px. Below that, drop to the 3 essential
  // tapes — otherwise the overflow:hidden on .topbar-mid clips a tape
  // mid-glyph and silently hides the rest (DXY/VIX).
  const compact = vw < 1580;
  const minimal = vw < 1440;

  // All 6 tapes as raw numeric values so we can compact-format consistently.
  const allTapes = [
    { id: 'kospi',   label: 'KOSPI',   raw: 2748.31, change: +0.42, full: '2,748.31',          essential: true  },
    { id: 'kosdaq',  label: 'KOSDAQ',  raw: 887.04,  change: -0.31, full: '887.04',            essential: false },
    { id: 'usdkrw',  label: 'USD/KRW', raw: fxKRW,   change: +0.18, full: fmt.price(fxKRW, 'KRW'), essential: true },
    { id: 'btc',     label: 'BTC',     raw: btcSpot, change: +1.94, full: '$' + fmt.price(btcSpot), essential: true, prefix: '$' },
    { id: 'dxy',     label: 'DXY',     raw: 104.62,  change: -0.07, full: '104.62',            essential: false },
    { id: 'vix',     label: 'VIX',     raw: 14.83,   change: +2.10, full: '14.83',             essential: false },
  ];

  const tapes = minimal ? allTapes.filter((t) => t.essential) : allTapes;

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
        {tapes.map((t) => (
          <Tape
            key={t.id}
            label={t.label}
            value={compact ? (t.prefix || '') + formatPriceCompact(t.raw) : t.full}
            change={t.change}
            title={t.full}
          />
        ))}
      </div>
      <div className="topbar-right">
        <div className="market-state" title={snapStale ? '시세 업데이트 지연 — 마지막 성공 후 60초 경과' : marketState}>
          <span className={'dot ' + (snapStale ? 'stale' : 'live')} />
          <span>{snapStale ? marketState + ' · STALE' : marketState}</span>
        </div>
        <div className="clock">
          <span className="muted">KST</span>
          <span className="mono">{new Date(now).toLocaleTimeString('ko-KR', { hour12: false })}</span>
        </div>
      </div>
    </div>
  );
}

function Tape({ label, value, change, title }) {
  const up = change >= 0;
  return (
    <div className="tape" title={title}>
      <span className="tape-label">{label}</span>
      <span className="tape-value">{value}</span>
      <span className={'tape-change ' + (up ? 'up' : 'down')}>
        {up ? '▲' : '▼'} {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  );
}

// ─── Watchlist (favorites + sort, Design v0.3 §5.4 / §4.4) ───
function Watchlist({ universe, data, current, setCurrent, upColor, downColor, onAddSymbol, onRemoveSymbol, addState }) {
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [favs, setFavs] = useState(() =>
    (window.tmStorage && window.tmStorage.get('wl-favs', [])) || []
  );

  // Stale favorites cleanup — drop symbols not in current universe.
  useEffect(() => {
    if (!window.tmStorage) return;
    const validSyms = new Set(universe.map((u) => u.symbol));
    const cleaned = favs.filter((s) => validSyms.has(s));
    if (cleaned.length !== favs.length) {
      setFavs(cleaned);
      window.tmStorage.set('wl-favs', cleaned);
    }
  }, [universe]);

  function toggleFav(sym, e) {
    e.stopPropagation();
    const next = favs.includes(sym) ? favs.filter((s) => s !== sym) : [...favs, sym];
    setFavs(next);
    if (window.tmStorage) window.tmStorage.set('wl-favs', next);
  }

  const q = query.trim().toLowerCase();
  const filtered = universe.filter((u) =>
    (filter === 'all' || u.market === filter) &&
    (q === '' ||
     u.symbol.toLowerCase().includes(q) ||
     (u.name || '').toLowerCase().includes(q))
  );
  // No existing row matches the query → offer to add it as a new symbol.
  const showAdd = q !== '' && filtered.length === 0;

  async function doAdd() {
    const ok = await onAddSymbol(query);
    if (ok) setQuery('');
  }
  function onSearchKeyDown(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (filtered.length > 0) setCurrent(filtered[0].symbol);
    else if (q !== '') doAdd();
  }

  // Sort: favorites first (in fav-array order), then non-favs (universe order).
  const favSet = new Set(favs);
  const favRows = favs.map((s) => filtered.find((u) => u.symbol === s)).filter(Boolean);
  const nonFavRows = filtered.filter((u) => !favSet.has(u.symbol));
  const showDivider = favRows.length > 0 && nonFavRows.length > 0;

  function renderRow(u) {
    const d = data[u.symbol];
    const last = d.candles[d.candles.length - 1];
    const prev = d.candles[d.candles.length - 2];
    const ch = (last.c - prev.c) / prev.c;
    const up = ch >= 0;
    const isFav = favSet.has(u.symbol);
    // NB: row is a div (not button) so the favorite star — itself an interactive
    // element — is not nested inside a button (invalid HTML). Keyboard a11y is
    // preserved via tabIndex + Enter/Space handler.
    return (
      <div
        key={u.symbol}
        className={'wl-row' + (u.symbol === current ? ' active' : '') + (isFav ? ' is-fav' : '')}
        onClick={() => setCurrent(u.symbol)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setCurrent(u.symbol); } }}
        role="button"
        tabIndex={0}
        aria-pressed={u.symbol === current}
      >
        <span
          className={'wl-fav' + (isFav ? ' on' : '')}
          onClick={(e) => toggleFav(u.symbol, e)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); e.preventDefault(); toggleFav(u.symbol, e); } }}
          role="button"
          tabIndex={0}
          title={isFav ? '즐겨찾기 해제' : '즐겨찾기'}
          aria-label={isFav ? '즐겨찾기 해제' : '즐겨찾기 추가'}
          aria-pressed={isFav}
        >
          {isFav ? '★' : '☆'}
        </span>
        <div className="wl-sym">
          <span className={'market-tag ' + u.market}>{u.exch}</span>
          <span className="wl-code mono">{u.symbol}</span>
          <span className="wl-name">{u.name}</span>
          {d.synthetic && (
            <span
              className="wl-synth-tag mono"
              title={`라이브 데이터 로드 실패 — 합성 데이터 표시 중 (${d.syntheticReason || 'unknown'})`}
              aria-label="합성 데이터"
            >
              SYNTH
            </span>
          )}
        </div>
        <div className="wl-price mono">{fmt.price(last.c, u.currency)}</div>
        <div className={'wl-chg mono ' + (up ? 'up' : 'down')}>
          {up ? '+' : ''}{(ch * 100).toFixed(2)}%
        </div>
        <div className="wl-spark"><MiniSpark candles={d.candles} upColor={upColor} downColor={downColor} /></div>
        {u.added && (
          <button
            className="wl-del"
            onClick={(e) => { e.stopPropagation(); onRemoveSymbol(u.symbol); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation(); e.preventDefault(); onRemoveSymbol(u.symbol);
              }
            }}
            title="목록에서 삭제"
            aria-label={u.symbol + ' 목록에서 삭제'}
          >
            ×
          </button>
        )}
      </div>
    );
  }

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
      <div className="watchlist-search">
        <input
          className="wl-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onSearchKeyDown}
          placeholder="종목 검색 / 추가 (예: 035720, DOGE/USDT)"
          aria-label="종목 검색 또는 추가"
        />
        {query && (
          <button className="wl-search-clear" onClick={() => setQuery('')} aria-label="검색 지우기" title="지우기">×</button>
        )}
      </div>
      <div className="watchlist-head">
        <span>SYMBOL</span>
        <span>PRICE</span>
        <span>%CHG</span>
        <span>30D</span>
      </div>
      <div className="watchlist-rows">
        {favRows.map(renderRow)}
        {showDivider && <div className="wl-favs-divider" aria-hidden="true" />}
        {nonFavRows.map(renderRow)}
        {showAdd && (
          <div className="wl-add">
            <button
              className="wl-add-btn"
              onClick={doAdd}
              disabled={addState.status === 'loading'}
            >
              {addState.status === 'loading'
                ? addState.message
                : `+ "${query.trim()}" 종목 추가`}
            </button>
            {addState.status === 'error' && (
              <div className="wl-add-err" role="alert">{addState.message}</div>
            )}
          </div>
        )}
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

// ─── Interval error message localization (v0.8 cleanup L-2) ────
// Maps backend English error patterns to Korean user-facing messages.
// Backend convention is English in `e.message` + machine-readable `e.details`;
// this layer turns that into something a Korean user can act on.
function localizeIntervalError(e, iv, symbol) {
  const ivLabel = (INTERVAL_LABELS[iv] && INTERVAL_LABELS[iv].label) || iv;
  if (!e || !e.message) return `${ivLabel} 데이터 로드 실패`;
  const msg = String(e.message);
  if (/insufficient daily data/i.test(msg)) {
    const details = (e && e.details) || {};
    const have = details.daily_rows;
    const need = details.min_required;
    if (have != null && need != null) {
      return `${symbol} ${ivLabel}봉 데이터 부족 — 일봉 ${have}일 (최소 ${need}일 필요)`;
    }
    return `${symbol} ${ivLabel}봉 데이터 부족`;
  }
  if (/unsupported.*interval/i.test(msg)) {
    return `${symbol} 종목은 ${ivLabel}봉 미지원`;
  }
  if (/no data for/i.test(msg) || /unknown.*symbol/i.test(msg)) {
    return `${symbol} 데이터 없음`;
  }
  if (/timeout/i.test(msg)) {
    return `${ivLabel}봉 데이터 시간 초과 — 잠시 후 재시도`;
  }
  if (/rate limit/i.test(msg) || /429/.test(msg)) {
    return `요청 한도 초과 — 60초 후 재시도`;
  }
  // Fall back to the raw message so we don't lose information.
  return `${ivLabel}봉 데이터 로드 실패: ${msg}`;
}

// ─── Interval label/group mapping (Design v0.3 §3.2 + v0.8 §3.4) ─
// NB: '1m' (minute) and '1M' (month) are case-sensitive — DO NOT confuse them.
const INTERVAL_LABELS = {
  '1m':  { label: '1분',   group: 'minute' },   // minute
  '5m':  { label: '5분',   group: 'minute' },
  '15m': { label: '15분',  group: 'minute' },
  '1h':  { label: '1시간', group: 'hour'   },
  '4h':  { label: '4시간', group: 'hour'   },
  '1d':  { label: '일',    group: 'day'    },
  '1w':  { label: '주',    group: 'longer' },   // ✨ v0.8 weekly
  '1M':  { label: '월',    group: 'longer' },   // ✨ v0.8 monthly (note uppercase M)
};
const INTERVAL_GROUP_ORDER = ['minute', 'hour', 'day', 'longer'];

// Runtime sanity check (v0.8 cleanup L-4) — JS Object keys are case-sensitive
// per spec, but a regression where '1m'/'1M' get unified or duplicated would be
// a silent disaster. Trip a console.error if anyone ever breaks this.
(function _assertIntervalKeysDistinct() {
  const keys = Object.keys(INTERVAL_LABELS);
  if (keys.length !== 8) {
    console.error('[INTERVAL_LABELS] expected 8 keys, got', keys.length, keys);
  }
  if (INTERVAL_LABELS['1m'] === INTERVAL_LABELS['1M']) {
    console.error('[INTERVAL_LABELS] 1m and 1M collapsed to same entry — case sensitivity broken!');
  }
  if (INTERVAL_LABELS['1m'].group !== 'minute' || INTERVAL_LABELS['1M'].group !== 'longer') {
    console.error('[INTERVAL_LABELS] 1m/1M group misassigned', INTERVAL_LABELS['1m'], INTERVAL_LABELS['1M']);
  }
})();

// ─── Chart Analysis page ──────────────────────────────────────
function ChartPage({ instrument: instrumentProp, upColor, downColor, indicators, setIndicators, signalsOn, setSignalsOn, trendBand, setTrendBand, dataState, setDataState }) {
  // Per-interval override — when user picks 1h/4h/etc we refetch and store
  // the result here without mutating the parent's daily DATA cache wholesale.
  const [localInstrument, setLocalInstrument] = useState(null);
  const instrument = localInstrument || instrumentProp;

  // NB: clamp lower bound to 0 — a negative `from` makes slice() return the
  // whole array which then breaks the min/max axis tick computation downstream.
  const initialFrom = Math.max(0, instrument.candles.length - 120);
  const [view, setView] = useState([initialFrom, instrument.candles.length]);
  const [hoverIdx, setHoverIdx] = useState(null);
  const [interval, setIntervalTf] = useState('1d');
  const [zoomLevel, setZoomLevel] = useState('3M');
  const [drawing, setDrawing] = useState(null); // 'trend' | 'fib' | null
  const [drawings, setDrawings] = useState([]);
  const intervalReqRef = useRef(0); // race-condition guard for fast clicks

  // Reset everything when the parent's symbol changes (Watchlist click).
  useEffect(() => {
    setLocalInstrument(null);
    setIntervalTf('1d');
    const n = instrumentProp.candles.length;
    setView([Math.max(0, n - 120), n]);
    setDrawings([]);
    setDrawing(null);
  }, [instrumentProp.meta.symbol]);

  // Real interval refetch — hits backend with the chosen timeframe.
  async function changeInterval(iv) {
    if (iv === interval) return;
    setIntervalTf(iv);

    const source = instrumentProp.meta.market === 'crypto' ? 'Binance Spot' : 'pykrx';

    // Demo / no-loader: fall back to the previous mock behavior so the UI
    // doesn't appear broken in synthetic mode.
    if (window.DEMO_MODE || !window.loader) {
      setDataState({ status: 'loading', message: `${instrumentProp.meta.symbol} ${iv} 데이터 수집 중… (데모)`, source: 'Synthetic' });
      setTimeout(() => setDataState({ status: 'ok', message: '데모 — 인터벌 전환은 시뮬레이션', source: 'Synthetic' }), 500);
      return;
    }

    setDataState({ status: 'loading', message: `${instrumentProp.meta.symbol} ${iv} 데이터 수집 중…`, source });

    const reqId = ++intervalReqRef.current;
    try {
      const fresh = await window.loader.loadInstrument(instrumentProp.meta, { interval: iv });
      // Stale request — user clicked again before this finished. Drop it.
      if (reqId !== intervalReqRef.current) return;
      setLocalInstrument(fresh);
      setView([Math.max(0, fresh.candles.length - 120), fresh.candles.length]);
      setHoverIdx(null);
      setDataState({ status: 'ok', message: '캐시 적중', source });
    } catch (e) {
      if (reqId !== intervalReqRef.current) return;
      console.error('[ChartPage] interval fetch failed', iv, e);
      setDataState({ status: 'error', message: localizeIntervalError(e, iv, instrumentProp.meta.symbol), source });
    }
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
          {INTERVAL_GROUP_ORDER.map((g, gi) => {
            const ivs = Object.keys(INTERVAL_LABELS).filter((iv) => INTERVAL_LABELS[iv].group === g);
            return (
              <React.Fragment key={g}>
                {gi > 0 && <div className="tf-divider" />}
                <div className={'tf-group tf-group--' + g} title={'타임프레임 (' + g + ')'}>
                  {ivs.map((iv) => (
                    <button
                      key={iv}
                      className={'tf-btn' + (interval === iv ? ' active' : '')}
                      onClick={() => changeInterval(iv)}
                    >
                      {INTERVAL_LABELS[iv].label}
                    </button>
                  ))}
                </div>
              </React.Fragment>
            );
          })}
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
          <div className="tf-group zoom-fab" title="기간 (줌)">
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
        {signalsOn && (
          <div className="chart-legend">
            <span className="cl-dir"><span className="cl-tri up">▲</span>매수</span>
            <span className="cl-dir"><span className="cl-tri down">▼</span>매도</span>
            <span className="cl-sep" />
            <span className="cl-item"><b>GC</b>골든크로스</span>
            <span className="cl-item"><b>DC</b>데드크로스</span>
            <span className="cl-item"><b>OB</b>과매수</span>
            <span className="cl-item"><b>OS</b>과매도</span>
            <span className="cl-item"><b>M↑/M↓</b>MACD 교차</span>
            <span className="cl-item"><b>DV↑/DV↓</b>RSI 다이버전스</span>
            <span className="cl-sep" />
            <span className="cl-note">흐린 마커 = 현재 국면에 부적합 (ADX 게이트)</span>
          </div>
        )}
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

// ─── Indicator groups (Design v0.3 §3.4) ──────────────────────
// Real toggles, not raw indicator columns. dependsOn renders only when parent is on.
const INDICATOR_GROUPS = [
  {
    id: 'trend', label: '추세',
    items: [
      { key: 'ma20',  type: 'indicator', label: 'MA 20',  color: 'oklch(0.78 0.16 75)'  },
      { key: 'ma60',  type: 'indicator', label: 'MA 60',  color: 'oklch(0.70 0.13 230)' },
      { key: 'ma120', type: 'indicator', label: 'MA 120', color: 'oklch(0.62 0.18 320)' },
    ],
  },
  {
    id: 'volatility', label: '변동성',
    items: [
      { key: 'bb', type: 'indicator', label: '볼린저밴드 (20,2)', color: 'rgba(150,180,220,0.7)' },
    ],
  },
  {
    id: 'leading', label: '선행 (RPB)',
    items: [
      { key: 'rpb',     type: 'indicator', label: 'RSI Price Band', color: 'oklch(0.62 0.22 25)', testid: 'indicator-toggle-rpb' },
      { key: 'rpbBoth', type: 'indicator', label: '└ 양방향 표시', color: 'rgba(180,180,180,0.5)', dependsOn: 'rpb' },
    ],
  },
  {
    id: 'display', label: '표시',
    items: [
      { key: 'signalsOn', type: 'flat', label: '신호 마커',      color: 'oklch(0.78 0.16 75)' },
      { key: 'trendBand', type: 'flat', label: '추세 영역 음영', color: 'oklch(0.72 0.18 145)' },
    ],
  },
];

// ─── Collapsible panel section helper (Design v0.3 §5.2) ─────
// Persists collapsed state per sectionId in tmStorage 'ws-right-collapsed'.
function CollapsibleSection({ sectionId, title, count, grow, children }) {
  const stored = (window.tmStorage && window.tmStorage.get('ws-right-collapsed', {})) || {};
  const [collapsed, setCollapsed] = useState(!!stored[sectionId]);

  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    if (!window.tmStorage) return;
    const all = window.tmStorage.get('ws-right-collapsed', {}) || {};
    window.tmStorage.set('ws-right-collapsed', { ...all, [sectionId]: next });
  }

  const cls = 'panel-section' + (grow ? ' grow' : '') + (collapsed ? ' collapsed' : '');
  return (
    <div className={cls} data-section-id={sectionId}>
      <div className="panel-header" onClick={toggle} role="button" aria-expanded={!collapsed} tabIndex={0}
           onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}>
        <span className="panel-title">{title}</span>
        {count != null && <span className="panel-count mono">{count}</span>}
      </div>
      {children}
    </div>
  );
}

const SIGNALS_LIMIT_OPTIONS = [10, 20, 50, 100];

// ─── Right side panel: indicator toggles + signal feed ──────
function RightPanel({ instrument, indicators, setIndicators, signalsOn, setSignalsOn, trendBand, setTrendBand, upColor, downColor }) {
  const last = instrument.candles[instrument.candles.length - 1];
  const lastRsi = instrument.ind.rsi14[instrument.ind.rsi14.length - 1];
  const lastMacd = instrument.ind.macd.line[instrument.ind.macd.line.length - 1];
  const lastSig = instrument.ind.macd.signal[instrument.ind.macd.signal.length - 1];
  const lastTrend = instrument.trend[instrument.trend.length - 1];

  // Signals limit (Design v0.3 §5.5) — clamped to allowed options.
  const [signalsLimit, setSignalsLimit] = useState(() => {
    const v = (window.tmStorage && window.tmStorage.get('signals-limit', 20)) || 20;
    return SIGNALS_LIMIT_OPTIONS.includes(v) ? v : 20;
  });
  function changeSignalsLimit(v) {
    setSignalsLimit(v);
    if (window.tmStorage) window.tmStorage.set('signals-limit', v);
  }
  const recentSignals = instrument.signals.slice(-signalsLimit).reverse();

  function getValue(item) {
    if (item.type === 'flat') return item.key === 'signalsOn' ? signalsOn : trendBand;
    return indicators[item.key];
  }
  function getSetter(item) {
    if (item.type === 'flat') return item.key === 'signalsOn' ? setSignalsOn : setTrendBand;
    return (v) => setIndicators({ ...indicators, [item.key]: v });
  }

  return (
    <div className="right-panel">
      <CollapsibleSection sectionId="current-status" title="현재 상태">
        <div className="status-grid">
          <StatusCell label="추세" value={lastTrend === 'up' ? '상승' : lastTrend === 'down' ? '하락' : '횡보'} tone={lastTrend} />
          <StatusCell label="RSI 14" value={lastRsi?.toFixed(1)} tone={lastRsi > 70 ? 'down' : lastRsi < 30 ? 'up' : 'side'} sub={lastRsi > 70 ? '과매수' : lastRsi < 30 ? '과매도' : '중립'} />
          <StatusCell label="MACD" value={lastMacd?.toFixed(2)} tone={lastMacd > lastSig ? 'up' : 'down'} sub={lastMacd > lastSig ? '시그널 위' : '시그널 아래'} />
          <StatusCell label="MA20→60" value={instrument.ind.ma20[instrument.ind.ma20.length - 1] > instrument.ind.ma60[instrument.ind.ma60.length - 1] ? '정배열' : '역배열'} tone={instrument.ind.ma20[instrument.ind.ma20.length - 1] > instrument.ind.ma60[instrument.ind.ma60.length - 1] ? 'up' : 'down'} />
        </div>
      </CollapsibleSection>

      <CollapsibleSection sectionId="indicators-overlay" title="지표 오버레이">
        <div className="ind-list">
          {INDICATOR_GROUPS.map((group) => (
            <React.Fragment key={group.id}>
              <div className="ind-group-header" data-group-id={group.id}>{group.label}</div>
              {group.items.map((item) => {
                if (item.dependsOn && !indicators[item.dependsOn]) return null;
                const extra = item.testid ? { 'data-testid': item.testid } : {};
                return (
                  <IndToggle
                    key={item.key}
                    label={item.label}
                    color={item.color}
                    on={getValue(item)}
                    onChange={getSetter(item)}
                    {...extra}
                  />
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </CollapsibleSection>

      <CollapsibleSection sectionId="recent-signals" title="최근 신호" count={instrument.signals.length} grow>
        <div className="signal-limit-row">
          <label className="signal-limit-label">표시</label>
          <select
            className="signal-limit-select mono"
            value={signalsLimit}
            onChange={(e) => changeSignalsLimit(Number(e.target.value))}
            aria-label="최근 신호 표시 개수"
          >
            {SIGNALS_LIMIT_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
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
      </CollapsibleSection>
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

function IndToggle({ label, color, on, onChange, ...rest }) {
  return (
    <button className={'ind-toggle' + (on ? ' on' : '')} onClick={() => onChange(!on)} {...rest}>
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

      {instrument.backtestStatus === 'unavailable' && (
        <div className="data-status data-status-error" style={{ marginBottom: 10 }}>
          <span className="ds-left">
            <span className="ds-dot" style={{ background: 'var(--down)' }} />
            <span className="ds-status mono" style={{ color: 'var(--down)' }}>BACKTEST OFFLINE</span>
            <span className="ds-msg">백테스트 결과를 불러오지 못해 차트 데이터만 표시합니다.</span>
          </span>
          <span className="ds-right mono muted">{instrument.backtestError || 'UNKNOWN'}</span>
        </div>
      )}

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

  const [indicators, setIndicators] = useState({ ma20: true, ma60: true, ma120: false, bb: true, rpb: false, rpbBoth: false });
  const [rightCollapsed, setRightCollapsed] = useState(() =>
    Boolean(window.tmStorage && window.tmStorage.get('right-panel-collapsed', false))
  );
  function toggleRightPanel() {
    const next = !rightCollapsed;
    setRightCollapsed(next);
    if (window.tmStorage) window.tmStorage.set('right-panel-collapsed', next);
  }
  // Left watchlist sidebar collapse. Honors a stored preference; otherwise
  // defaults to collapsed on narrow viewports (≤1100px) so the chart isn't
  // squeezed between two 320px sidebars.
  const [leftCollapsed, setLeftCollapsed] = useState(() => {
    const stored = window.tmStorage ? window.tmStorage.get('left-panel-collapsed', null) : null;
    if (stored === true || stored === false) return stored;
    return window.innerWidth < 1100;
  });
  function toggleLeftPanel() {
    const next = !leftCollapsed;
    setLeftCollapsed(next);
    if (window.tmStorage) window.tmStorage.set('left-panel-collapsed', next);
  }
  // Ad-hoc symbol add. Bumping universeVersion forces a re-render after the
  // (in-place) mutation of window.MarketData.UNIVERSE / DATA. addState drives
  // the watchlist's loading / error feedback. Added symbols last for the
  // session only — they are not persisted across reloads.
  const [, setUniverseVersion] = useState(0);
  const [addState, setAddState] = useState({ status: 'idle', message: '' });
  async function handleAddSymbol(rawInput) {
    const meta = parseSymbolInput(rawInput);
    if (!meta) {
      setAddState({ status: 'error', message: '심볼 형식 오류 — KR 6자리 코드 또는 BTC/USDT 형식' });
      return false;
    }
    meta.added = true;     // marks the row as user-added → removable
    const existing = window.MarketData.UNIVERSE.find((u) => u.symbol === meta.symbol);
    if (existing) {
      setCurrent(meta.symbol);
      setAddState({ status: 'idle', message: '' });
      return true;
    }
    setAddState({ status: 'loading', message: meta.symbol + ' 불러오는 중…' });
    try {
      let inst;
      if (window.DEMO_MODE) {
        inst = window.MarketData.makeSyntheticInstrument(meta);
      } else {
        inst = await window.loader.loadInstrument(meta, { interval: '1d' });
        inst.synthetic = false;
      }
      if (!inst || !inst.candles || inst.candles.length < 2) {
        throw new Error(meta.symbol + ' 데이터가 없습니다');
      }
      window.MarketData.DATA[meta.symbol] = inst;
      window.MarketData.UNIVERSE.push(meta);
      // Persist so the symbol is restored on the next reload.
      if (window.tmStorage) {
        const saved = window.tmStorage.get('wl-added', []) || [];
        if (!saved.some((m) => m.symbol === meta.symbol)) {
          window.tmStorage.set('wl-added', saved.concat([meta]));
        }
      }
      setUniverseVersion((v) => v + 1);
      setCurrent(meta.symbol);
      setAddState({ status: 'idle', message: '' });
      return true;
    } catch (e) {
      setAddState({ status: 'error', message: (e && e.message) || '종목 로드 실패' });
      return false;
    }
  }
  // Remove a user-added symbol. Seed symbols (no `added` flag) are protected.
  function handleRemoveSymbol(symbol) {
    const uni = window.MarketData.UNIVERSE;
    const idx = uni.findIndex((u) => u.symbol === symbol);
    if (idx < 0 || !uni[idx].added) return;
    uni.splice(idx, 1);
    delete window.MarketData.DATA[symbol];
    if (window.tmStorage) {
      const saved = (window.tmStorage.get('wl-added', []) || []).filter((m) => m.symbol !== symbol);
      window.tmStorage.set('wl-added', saved);
    }
    // If the removed symbol was being viewed, fall back to the first symbol.
    if (current === symbol) setCurrent(uni[0] ? uni[0].symbol : 'BTC/USDT');
    setUniverseVersion((v) => v + 1);
  }
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
  // Tracks when marketSnap was last successfully updated, in ms. Used together
  // with the `now` 1s ticker to render a STALE badge when polling has been
  // failing for >60s without forcing the UI to drop the last good value.
  const [marketSnapAt, setMarketSnapAt] = useState(0);

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

  // Restore user-added symbols (persisted in tmStorage 'wl-added') once the
  // seed universe is ready. Demo mode regenerates synthetic data; live mode
  // re-fetches from the backend. Failures are skipped so a delisted saved
  // symbol can't break startup. Runs exactly once via the ref guard.
  const rehydratedRef = useRef(false);
  useEffect(() => {
    if (rehydratedRef.current) return;
    if (!window.DEMO_MODE && !dataReady) return;     // wait for the seed load
    rehydratedRef.current = true;
    const saved = (window.tmStorage && window.tmStorage.get('wl-added', [])) || [];
    if (!saved.length) return;
    let cancelled = false;
    (async () => {
      let restored = 0;
      for (const meta of saved) {
        if (cancelled) return;
        if (window.MarketData.UNIVERSE.some((u) => u.symbol === meta.symbol)) continue;
        try {
          let inst;
          if (window.DEMO_MODE) {
            inst = window.MarketData.makeSyntheticInstrument(meta);
          } else {
            inst = await window.loader.loadInstrument(meta, { interval: '1d' });
            inst.synthetic = false;
          }
          if (!inst || !inst.candles || inst.candles.length < 2) throw new Error('no data');
          meta.added = true;     // restored symbols stay removable
          window.MarketData.DATA[meta.symbol] = inst;
          window.MarketData.UNIVERSE.push(meta);
          restored += 1;
        } catch (e) {
          console.warn('[App] could not restore added symbol', meta.symbol, e && e.message);
        }
      }
      if (!cancelled && restored > 0) setUniverseVersion((v) => v + 1);
    })();
    return () => { cancelled = true; };
  }, [dataReady]);

  // TopBar market snapshot polling (30s, paused when tab is hidden).
  useEffect(() => {
    if (window.DEMO_MODE || !dataReady) return;
    let alive = true;
    let timerId = null;
    let reqSeq = 0;                              // monotonically increasing token
    let lastApplied = 0;                          // highest token whose result was applied
    const ctlRef = { current: null };

    async function tick() {
      if (!alive) return;
      // Always abort any in-flight request — both on visibility transitions and
      // on the next interval boundary — to prevent a stale promise from
      // overwriting newer data via a later setMarketSnap.
      if (ctlRef.current) ctlRef.current.abort();
      if (document.visibilityState !== 'visible') return;
      ctlRef.current = new AbortController();
      const mySeq = ++reqSeq;
      try {
        const snap = await window.api.marketSnapshot({ signal: ctlRef.current.signal, timeout: 8000 });
        // Reject out-of-order results: only apply if this is the newest response
        // and the component is still mounted.
        if (alive && mySeq > lastApplied) {
          lastApplied = mySeq;
          setMarketSnap(snap);
          setMarketSnapAt(Date.now());
        }
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
  const snapStale = marketSnapAt > 0 && (now - marketSnapAt > 60_000);
  const fxKRW = (marketSnap && marketSnap.usd_krw && marketSnap.usd_krw.value) || 1382.40;
  const btcSpot = (marketSnap && marketSnap.btc && marketSnap.btc.value)
    || data['BTC/USDT'].candles[data['BTC/USDT'].candles.length - 1].c;

  return (
    <div className="app" style={{ ['--up']: upColor, ['--down']: downColor }}>
      <TopBar now={now} fxKRW={fxKRW} btcSpot={btcSpot} marketState="MARKET OPEN · KOSPI" snapStale={snapStale} />

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
        <button className={'pt-btn' + (page === 'coach' ? ' active' : '')} onClick={() => setPage('coach')}>
          <span className="pt-num mono">05</span>
          <span>Strategy Coach</span>
        </button>
        <div className="pt-spacer" />
        <div className="pt-meta mono">
          {fmt.date(Date.now())} · {instrument.candles.length}봉 로드됨 · 캐시 HIT
        </div>
      </div>

      <div className="workspace">
        <div className={'ws-left' + (leftCollapsed ? ' collapsed' : '')}>
          <button
            className="ws-left-toggle"
            onClick={toggleLeftPanel}
            title={leftCollapsed ? '관심 종목 펼치기' : '관심 종목 접기'}
            aria-label={leftCollapsed ? '관심 종목 사이드바 펼치기' : '관심 종목 사이드바 접기'}
            aria-expanded={!leftCollapsed}
          >
            <span className="ws-left-toggle-icon">{leftCollapsed ? '▶' : '◀'}</span>
          </button>
          <Watchlist universe={universe} data={data} current={current} setCurrent={setCurrent} upColor={upColor} downColor={downColor} onAddSymbol={handleAddSymbol} onRemoveSymbol={handleRemoveSymbol} addState={addState} />
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
          ) : page === 'coach' ? (
            <StrategyCoachPage universe={universe} currentSymbol={current} setCurrent={setCurrent} upColor={upColor} downColor={downColor} />
          ) : (
            <BacktestPage instrument={instrument} upColor={upColor} downColor={downColor} />
          )}
        </div>
        {page === 'chart' && (
          <div className={'ws-right' + (rightCollapsed ? ' collapsed' : '')}>
            <button
              className="ws-right-toggle"
              onClick={toggleRightPanel}
              title={rightCollapsed ? '패널 펼치기' : '패널 접기'}
              aria-label={rightCollapsed ? '오른쪽 패널 펼치기' : '오른쪽 패널 접기'}
              aria-expanded={!rightCollapsed}
            >
              <span className="ws-right-toggle-icon">{rightCollapsed ? '◀' : '▶'}</span>
            </button>
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
