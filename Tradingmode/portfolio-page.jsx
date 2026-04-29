// Portfolio page — holdings, P&L, allocation, performance.
// Mock portfolio derived deterministically from universe data.

const { useState: useStateP, useMemo: useMemoP } = React;

// ─── Mock portfolio holdings ─────────────────────────────────
// (symbol, qty, avgCost) — avgCost expressed in instrument's native currency
const MOCK_HOLDINGS = [
  { symbol: 'BTC/USDT',  qty: 0.42,    avgCost: 58400 },
  { symbol: 'ETH/USDT',  qty: 4.8,     avgCost: 2780 },
  { symbol: 'SOL/USDT',  qty: 95,      avgCost: 118 },
  { symbol: '005930',    qty: 320,     avgCost: 71200 },   // 삼성전자
  { symbol: '000660',    qty: 42,      avgCost: 162000 },  // SK하이닉스
  { symbol: '035420',    qty: 28,      avgCost: 215000 },  // NAVER
  { symbol: '373220',    qty: 8,       avgCost: 445000 },  // LG엔솔
  { symbol: '247540',    qty: 14,      avgCost: 198000 },  // 에코프로비엠
];

const FX_KRW_PER_USD = 1382.40; // single FX assumption used across this page

function PortfolioPage({ universe, data, setCurrent, upColor, downColor }) {
  const [period, setPeriod] = useStateP('3M'); // 1M | 3M | 6M | 1Y | ALL
  const [allocBy, setAllocBy] = useStateP('symbol'); // symbol | market

  // ─── Build holdings rows ─────────────────────────────────────
  const rows = useMemoP(() => {
    return MOCK_HOLDINGS.map((h) => {
      const inst = data[h.symbol];
      if (!inst) return null;
      const last = inst.candles[inst.candles.length - 1];
      const prev = inst.candles[inst.candles.length - 2];
      const dayChg = (last.c - prev.c) / prev.c;
      const cur = inst.meta.currency;
      const fx = cur === 'KRW' ? 1 : FX_KRW_PER_USD; // value everything in KRW
      const value = h.qty * last.c * fx;
      const cost = h.qty * h.avgCost * fx;
      const pnl = value - cost;
      const pnlPct = pnl / cost;
      return {
        ...h,
        meta: inst.meta,
        last: last.c,
        prev: prev.c,
        dayChg,
        value,    // KRW
        cost,     // KRW
        pnl,      // KRW
        pnlPct,
        candles: inst.candles,
      };
    }).filter(Boolean);
  }, [data]);

  const totals = useMemoP(() => {
    const value = rows.reduce((a, r) => a + r.value, 0);
    const cost  = rows.reduce((a, r) => a + r.cost, 0);
    const dayPnl = rows.reduce((a, r) => a + r.value * r.dayChg / (1 + r.dayChg), 0);
    return {
      value,
      cost,
      pnl: value - cost,
      pnlPct: cost > 0 ? (value - cost) / cost : 0,
      dayPnl,
      dayPct: value > 0 ? dayPnl / value : 0,
    };
  }, [rows]);

  // Sort holdings by value desc for table + treemap
  const sortedRows = useMemoP(() => [...rows].sort((a, b) => b.value - a.value), [rows]);

  // ─── Performance series (portfolio value over time, in KRW) ──
  const periodMap = { '1M': 30, '3M': 90, '6M': 130, '1Y': 200, 'ALL': 240 };
  const lookback = periodMap[period];

  const perfSeries = useMemoP(() => {
    // Real backend feeds different bar counts per market (crypto 365 vs KR 244),
    // so align from the end using the *shortest* series. Skip bars where any
    // holding is missing data.
    if (!rows.length) return [];
    const minN = Math.min.apply(null, rows.map((r) => r.candles.length));
    const start = Math.max(0, minN - lookback);
    const refRow = rows.reduce(
      (best, r) => (r.candles.length < best.candles.length ? r : best),
      rows[0],
    );
    const series = [];
    for (let i = start; i < minN; i++) {
      let total = 0;
      let usable = true;
      for (const r of rows) {
        // Each row aligns from the end of its own series, so map global index
        // i (relative to refRow) onto the row's own offset.
        const offset = r.candles.length - (minN - i);
        const candle = r.candles[offset];
        if (!candle || candle.c == null) { usable = false; break; }
        const fx = r.meta.currency === 'KRW' ? 1 : FX_KRW_PER_USD;
        total += r.qty * candle.c * fx;
      }
      if (!usable) continue;
      const t = refRow.candles[i]?.t;
      if (t == null) continue;
      series.push({ t, v: total });
    }
    return series;
  }, [rows, lookback]);

  const periodReturn = perfSeries.length > 1
    ? (perfSeries[perfSeries.length - 1].v - perfSeries[0].v) / perfSeries[0].v
    : 0;

  // Benchmark: equal-weight buy-and-hold of just KOSPI names (proxy)
  // — we cheat: use 005930 returns scaled
  const benchmarkSeries = useMemoP(() => {
    const krInst = data['005930'];
    if (!krInst) return [];
    const N = krInst.candles.length;
    const start = Math.max(0, N - lookback);
    const base = krInst.candles[start].c;
    return krInst.candles.slice(start).map((c) => ({ t: c.t, v: c.c / base }));
  }, [data, lookback]);

  const benchReturn = benchmarkSeries.length > 1
    ? benchmarkSeries[benchmarkSeries.length - 1].v - 1
    : 0;

  // ─── Allocation ──────────────────────────────────────────────
  const allocation = useMemoP(() => {
    if (allocBy === 'market') {
      const groups = {};
      for (const r of sortedRows) {
        const k = r.meta.market === 'crypto' ? 'CRYPTO' : (r.meta.exch || 'KR');
        if (!groups[k]) groups[k] = { key: k, value: 0, count: 0, market: r.meta.market };
        groups[k].value += r.value;
        groups[k].count += 1;
      }
      return Object.values(groups).sort((a, b) => b.value - a.value);
    }
    return sortedRows.map((r) => ({
      key: r.meta.symbol,
      label: r.meta.name,
      value: r.value,
      market: r.meta.market,
    }));
  }, [sortedRows, allocBy]);

  return (
    <div className="portfolio-page" data-screen-label="04 포트폴리오">
      {/* ─── Header / KPIs ─── */}
      <div className="pf-header">
        <div className="pf-title-block">
          <div className="pf-title">포트폴리오</div>
          <div className="pf-sub">
            <span className="muted">보유 종목</span>
            <span className="mono">{rows.length}</span>
            <span className="muted">· 통합 평가 통화</span>
            <span className="mono">KRW</span>
            <span className="muted">· FX</span>
            <span className="mono">USD/KRW {fmt.price(FX_KRW_PER_USD, 'KRW')}</span>
          </div>
        </div>
        <div className="pf-actions">
          <button className="pf-btn ghost">＋ 수동 거래 추가</button>
          <button className="pf-btn">⟳ 가격 동기화</button>
        </div>
      </div>

      <div className="pf-kpi-row">
        <PfKpi label="총 평가금액" value={fmt.price(totals.value, 'KRW')} sub="KRW" big />
        <PfKpi
          label="평가손익"
          value={(totals.pnl >= 0 ? '+' : '') + fmt.price(totals.pnl, 'KRW')}
          sub={(totals.pnlPct * 100).toFixed(2) + '%'}
          tone={totals.pnl >= 0 ? 'up' : 'down'}
          big
        />
        <PfKpi
          label="당일 손익"
          value={(totals.dayPnl >= 0 ? '+' : '') + fmt.price(totals.dayPnl, 'KRW')}
          sub={(totals.dayPct * 100).toFixed(2) + '%'}
          tone={totals.dayPnl >= 0 ? 'up' : 'down'}
        />
        <PfKpi label="투자원금" value={fmt.price(totals.cost, 'KRW')} sub="KRW" />
        <PfKpi
          label={period + ' 수익률'}
          value={(periodReturn * 100).toFixed(2) + '%'}
          tone={periodReturn >= 0 ? 'up' : 'down'}
          sub={'벤치 ' + (benchReturn >= 0 ? '+' : '') + (benchReturn * 100).toFixed(2) + '%'}
        />
      </div>

      {/* ─── 2-col body ─── */}
      <div className="pf-body">
        {/* Left: performance + holdings table */}
        <div className="pf-col-main">
          <div className="pf-card">
            <div className="pf-card-header">
              <div className="pf-card-title">자산 곡선</div>
              <div className="pf-period-tabs">
                {['1M', '3M', '6M', '1Y', 'ALL'].map((p) => (
                  <button key={p} className={'tf-btn' + (period === p ? ' active' : '')} onClick={() => setPeriod(p)}>{p}</button>
                ))}
              </div>
            </div>
            <div className="pf-chart-wrap" style={{ height: 240 }}>
              <PortfolioCurve
                series={perfSeries}
                benchmark={benchmarkSeries}
                upColor={upColor}
                downColor={downColor}
              />
            </div>
            <div className="pf-curve-legend">
              <span className="legend-item"><span className="dot" style={{ background: periodReturn >= 0 ? upColor : downColor }} /> 포트폴리오 ({(periodReturn * 100).toFixed(2)}%)</span>
              <span className="legend-item"><span className="dot" style={{ background: 'oklch(0.62 0.10 230)' }} /> 벤치마크 KOSPI ({(benchReturn * 100).toFixed(2)}%)</span>
              <span className="legend-item muted">초과수익 {((periodReturn - benchReturn) * 100).toFixed(2)}%p</span>
            </div>
          </div>

          <div className="pf-card">
            <div className="pf-card-header">
              <div className="pf-card-title">보유 종목 <span className="muted mono">{rows.length}</span></div>
              <div className="muted mono">평가금액 내림차순</div>
            </div>
            <div className="pf-table-wrap">
              <table className="pf-table">
                <thead>
                  <tr>
                    <th>종목</th>
                    <th className="num">수량</th>
                    <th className="num">평균단가</th>
                    <th className="num">현재가</th>
                    <th className="num">평가금액 (KRW)</th>
                    <th className="num">평가손익</th>
                    <th className="num">수익률</th>
                    <th className="num">당일</th>
                    <th className="num">비중</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((r) => {
                    const weight = totals.value > 0 ? r.value / totals.value : 0;
                    return (
                      <tr key={r.symbol}>
                        <td>
                          <div className="pf-sym-cell">
                            <span className={'market-tag ' + r.meta.market}>{r.meta.exch}</span>
                            <span className="mono pf-sym-code">{r.meta.symbol}</span>
                            <span className="pf-sym-name">{r.meta.name}</span>
                          </div>
                        </td>
                        <td className="num mono">{r.qty < 1 ? r.qty.toFixed(4) : r.qty.toLocaleString('ko-KR')}</td>
                        <td className="num mono">{fmt.price(r.avgCost, r.meta.currency)}</td>
                        <td className="num mono">{fmt.price(r.last, r.meta.currency)}</td>
                        <td className="num mono">{fmt.price(r.value, 'KRW')}</td>
                        <td className={'num mono ' + (r.pnl >= 0 ? 'up' : 'down')}>
                          {r.pnl >= 0 ? '+' : ''}{fmt.price(r.pnl, 'KRW')}
                        </td>
                        <td className={'num mono ' + (r.pnlPct >= 0 ? 'up' : 'down')}>
                          {(r.pnlPct * 100).toFixed(2)}%
                        </td>
                        <td className={'num mono ' + (r.dayChg >= 0 ? 'up' : 'down')}>
                          {r.dayChg >= 0 ? '+' : ''}{(r.dayChg * 100).toFixed(2)}%
                        </td>
                        <td className="num">
                          <div className="pf-weight">
                            <div className="pf-weight-bar" style={{ width: (weight * 100) + '%', background: r.meta.market === 'crypto' ? 'oklch(0.72 0.16 60)' : 'oklch(0.68 0.14 230)' }} />
                            <span className="mono">{(weight * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td>
                          <button className="pf-row-btn" onClick={() => setCurrent(r.symbol)} title="차트로 이동">→</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <td><b>합계</b></td>
                    <td colSpan={3}></td>
                    <td className="num mono"><b>{fmt.price(totals.value, 'KRW')}</b></td>
                    <td className={'num mono ' + (totals.pnl >= 0 ? 'up' : 'down')}>
                      <b>{totals.pnl >= 0 ? '+' : ''}{fmt.price(totals.pnl, 'KRW')}</b>
                    </td>
                    <td className={'num mono ' + (totals.pnlPct >= 0 ? 'up' : 'down')}>
                      <b>{(totals.pnlPct * 100).toFixed(2)}%</b>
                    </td>
                    <td className={'num mono ' + (totals.dayPct >= 0 ? 'up' : 'down')}>
                      <b>{totals.dayPct >= 0 ? '+' : ''}{(totals.dayPct * 100).toFixed(2)}%</b>
                    </td>
                    <td className="num mono"><b>100%</b></td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>

        {/* Right: allocation + risk */}
        <div className="pf-col-side">
          <div className="pf-card">
            <div className="pf-card-header">
              <div className="pf-card-title">자산 배분</div>
              <div className="pf-toggle-tabs">
                <button className={'tf-btn' + (allocBy === 'symbol' ? ' active' : '')} onClick={() => setAllocBy('symbol')}>종목</button>
                <button className={'tf-btn' + (allocBy === 'market' ? ' active' : '')} onClick={() => setAllocBy('market')}>시장</button>
              </div>
            </div>
            <div style={{ padding: '14px 16px 4px' }}>
              <DonutChart items={allocation} total={totals.value} />
            </div>
            <div className="pf-alloc-list">
              {allocation.map((a, i) => {
                const pct = totals.value > 0 ? a.value / totals.value : 0;
                const color = donutColor(i, a.market);
                return (
                  <div className="pf-alloc-row" key={a.key}>
                    <span className="pf-alloc-dot" style={{ background: color }} />
                    <span className="pf-alloc-label">
                      {allocBy === 'symbol' ? (
                        <>
                          <span className="mono">{a.key}</span>
                          <span className="muted"> · {a.label}</span>
                        </>
                      ) : (
                        <>
                          <span className="mono">{a.key}</span>
                          <span className="muted"> · {a.count}종목</span>
                        </>
                      )}
                    </span>
                    <span className="pf-alloc-pct mono">{(pct * 100).toFixed(1)}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="pf-card">
            <div className="pf-card-header">
              <div className="pf-card-title">리스크 / 집중도</div>
            </div>
            <div className="pf-risk-grid">
              <RiskCell label="최대 비중 종목"
                value={sortedRows[0] ? (sortedRows[0].value / totals.value * 100).toFixed(1) + '%' : '—'}
                sub={sortedRows[0]?.meta.name || ''} />
              <RiskCell label="암호화폐 비중"
                value={(rows.filter(r => r.meta.market === 'crypto').reduce((a, r) => a + r.value, 0) / totals.value * 100).toFixed(1) + '%'}
                tone="side" />
              <RiskCell label="국내 주식 비중"
                value={(rows.filter(r => r.meta.market === 'kr').reduce((a, r) => a + r.value, 0) / totals.value * 100).toFixed(1) + '%'}
                tone="side" />
              <RiskCell label="손실 종목"
                value={rows.filter(r => r.pnl < 0).length + '/' + rows.length}
                tone={rows.filter(r => r.pnl < 0).length > rows.length / 2 ? 'down' : 'up'} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── small subcomponents ────────────────────────────────────
function PfKpi({ label, value, sub, tone, big }) {
  return (
    <div className={'pf-kpi tone-' + (tone || 'side') + (big ? ' big' : '')}>
      <div className="pf-kpi-label">{label}</div>
      <div className="pf-kpi-value mono">{value}</div>
      {sub && <div className="pf-kpi-sub mono">{sub}</div>}
    </div>
  );
}

function RiskCell({ label, value, sub, tone }) {
  return (
    <div className={'pf-risk-cell tone-' + (tone || 'side')}>
      <div className="rc-label">{label}</div>
      <div className="rc-value mono">{value}</div>
      {sub && <div className="rc-sub">{sub}</div>}
    </div>
  );
}

// ─── Portfolio equity curve (KRW) + benchmark overlay ──────
function PortfolioCurve({ series, benchmark, upColor, downColor }) {
  if (!series || series.length === 0) return null;
  const W = 760, H = 240, padL = 56, padR = 12, padT = 14, padB = 24;
  const innerW = W - padL - padR, innerH = H - padT - padB;

  const vMin = Math.min(...series.map(s => s.v));
  const vMax = Math.max(...series.map(s => s.v));
  const span = Math.max(vMax - vMin, 1);
  const y = (v) => padT + innerH - ((v - vMin) / span) * innerH;
  const x = (i) => padL + (i / (series.length - 1)) * innerW;

  const v0 = series[0].v;
  const path = series.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(p.v).toFixed(1)}`).join(' ');
  const filled = path + ` L ${x(series.length - 1).toFixed(1)} ${(padT + innerH).toFixed(1)} L ${padL.toFixed(1)} ${(padT + innerH).toFixed(1)} Z`;

  // benchmark: scaled to same starting value
  const benchPath = benchmark && benchmark.length > 1
    ? benchmark.map((p, i) => {
        const v = v0 * p.v;
        const xi = padL + (i / (benchmark.length - 1)) * innerW;
        return `${i === 0 ? 'M' : 'L'} ${xi.toFixed(1)} ${y(v).toFixed(1)}`;
      }).join(' ')
    : '';

  const isUp = series[series.length - 1].v >= v0;
  const lineColor = isUp ? upColor : downColor;

  // y-axis grid (5 ticks)
  const ticks = [];
  for (let i = 0; i <= 4; i++) {
    const v = vMin + (span * i) / 4;
    ticks.push({ v, y: y(v) });
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
      <defs>
        <linearGradient id="pf-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.32" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* grid */}
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={t.y} y2={t.y} stroke="rgba(255,255,255,0.05)" />
          <text x={padL - 6} y={t.y + 3} textAnchor="end" fontSize="9" fill="rgba(255,255,255,0.45)" className="mono">
            {fmt.price(t.v, 'KRW')}
          </text>
        </g>
      ))}

      {/* baseline (start value) */}
      <line x1={padL} x2={W - padR} y1={y(v0)} y2={y(v0)} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 3" />

      {/* benchmark line */}
      {benchPath && <path d={benchPath} fill="none" stroke="oklch(0.62 0.10 230)" strokeWidth="1.2" strokeDasharray="4 3" opacity="0.85" />}

      {/* portfolio area + line */}
      <path d={filled} fill="url(#pf-fill)" />
      <path d={path} fill="none" stroke={lineColor} strokeWidth="1.8" />

      {/* x-axis date labels */}
      <text x={padL} y={H - 6} fontSize="9" fill="rgba(255,255,255,0.45)" className="mono">{fmt.date(series[0].t)}</text>
      <text x={W - padR} y={H - 6} fontSize="9" fill="rgba(255,255,255,0.45)" textAnchor="end" className="mono">{fmt.date(series[series.length - 1].t)}</text>
    </svg>
  );
}

// ─── Donut chart for allocation ────────────────────────────
function donutColor(i, market) {
  // Color families for visual differentiation; market hint adjusts hue
  const palette = [
    'oklch(0.72 0.16 60)',   // amber
    'oklch(0.68 0.14 230)',  // blue
    'oklch(0.66 0.18 320)',  // magenta
    'oklch(0.72 0.18 145)',  // green
    'oklch(0.70 0.14 25)',   // red-orange
    'oklch(0.65 0.13 270)',  // violet
    'oklch(0.78 0.14 90)',   // gold
    'oklch(0.62 0.13 195)',  // teal
  ];
  return palette[i % palette.length];
}

function DonutChart({ items, total }) {
  const size = 180, stroke = 28, r = (size - stroke) / 2, cx = size / 2, cy = size / 2;
  const C = 2 * Math.PI * r;
  let acc = 0;
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
        {items.map((a, i) => {
          const pct = total > 0 ? a.value / total : 0;
          const len = pct * C;
          const dasharray = `${len} ${C - len}`;
          const dashoffset = -acc * C;
          acc += pct;
          return (
            <circle
              key={a.key}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={donutColor(i, a.market)}
              strokeWidth={stroke}
              strokeDasharray={dasharray}
              strokeDashoffset={dashoffset}
              transform={`rotate(-90 ${cx} ${cy})`}
            />
          );
        })}
      </svg>
      <div style={{ position: 'absolute', textAlign: 'center', pointerEvents: 'none' }}>
        <div className="muted" style={{ fontSize: 10, letterSpacing: '0.06em' }}>총 평가금액</div>
        <div className="mono" style={{ fontSize: 16, fontWeight: 600 }}>{fmt.price(total, 'KRW')}</div>
        <div className="muted mono" style={{ fontSize: 10 }}>{items.length}개 항목</div>
      </div>
    </div>
  );
}

Object.assign(window, { PortfolioPage });
