// Chart primitives — pure SVG candle/line plots tuned for dense data.
// Receives already-built data from MarketData. Coordinates are computed once per render.

const { useMemo, useState, useRef, useEffect, useCallback } = React;

// ─── Format helpers ─────────────────────────────────────────
const fmt = {
  price(v, currency) {
    if (v == null) return '—';
    if (currency === 'KRW') return Math.round(v).toLocaleString('ko-KR');
    if (Math.abs(v) >= 1000) return v.toLocaleString('en-US', { maximumFractionDigits: 1 });
    if (Math.abs(v) >= 1) return v.toLocaleString('en-US', { maximumFractionDigits: 2 });
    return v.toLocaleString('en-US', { maximumFractionDigits: 4 });
  },
  pct(v, digits = 2) {
    if (v == null) return '—';
    const sign = v > 0 ? '+' : '';
    return sign + (v * 100).toFixed(digits) + '%';
  },
  signedPrice(v, currency) {
    if (v == null) return '—';
    const sign = v > 0 ? '+' : '';
    return sign + fmt.price(v, currency);
  },
  vol(v) {
    if (v == null) return '—';
    if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return v.toFixed(0);
  },
  date(t) {
    const d = new Date(t);
    return d.toLocaleDateString('ko-KR', { year: '2-digit', month: '2-digit', day: '2-digit' });
  },
  shortDate(t) {
    const d = new Date(t);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  },
};

// ─── Main candle chart with overlays ─────────────────────────
function CandleChart({ instrument, view, hoverIdx, setHoverIdx, indicators, signalsOn, trendBand, upColor, downColor, drawing, drawings, setDrawings, setDrawing }) {
  const { candles, ind, trend, signals, trades } = instrument;
  const [from, to] = view;
  const width = 1100;
  const height = 420;
  const padL = 8;
  const padR = 64;
  const padT = 14;
  const padB = 26;

  const slice = candles.slice(from, to);
  const sigSlice = signals.filter((s) => s.i >= from && s.i < to);
  const tradeSlice = trades.filter((t) => t.entryI < to && t.exitI >= from);

  const lo = Math.min(...slice.map((c) => c.l));
  const hi = Math.max(...slice.map((c) => c.h));
  const pad = (hi - lo) * 0.08;
  const yMin = lo - pad;
  const yMax = hi + pad;

  const W = width - padL - padR;
  const H = height - padT - padB;
  const cw = W / slice.length;

  const xAt = (i) => padL + (i + 0.5) * cw;
  const yAt = (p) => padT + H - ((p - yMin) / (yMax - yMin)) * H;

  // Trend band (bottom strip) ------
  const trendStrip = trendBand ? trend.slice(from, to) : [];

  // Y ticks ------
  const yTicks = useMemo(() => {
    const n = 6;
    const step = (yMax - yMin) / (n - 1);
    return Array.from({ length: n }, (_, k) => yMin + step * k);
  }, [yMin, yMax]);

  // X ticks ------
  const xTicks = useMemo(() => {
    const n = 7;
    const step = Math.max(1, Math.floor(slice.length / n));
    const arr = [];
    for (let i = 0; i < slice.length; i += step) arr.push(i);
    return arr;
  }, [slice.length]);

  // Mouse → idx + price
  const svgRef = useRef(null);
  const [pendingPt, setPendingPt] = useState(null); // first click for drawing
  const [hoverPrice, setHoverPrice] = useState(null);
  function getPos(e) {
    const r = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * width - padL;
    const yPx = ((e.clientY - r.top) / r.height) * height;
    const i = Math.floor(x / cw);
    const price = yMax - ((yPx - padT) / H) * (yMax - yMin);
    return { i: from + i, price, valid: i >= 0 && i < slice.length };
  }
  function onMove(e) {
    const p = getPos(e);
    if (p.valid) { setHoverIdx(p.i); setHoverPrice(p.price); }
    else { setHoverIdx(null); setHoverPrice(null); }
  }
  function onLeave() { setHoverIdx(null); setHoverPrice(null); }
  function onClick(e) {
    if (!drawing) return;
    const p = getPos(e);
    if (!p.valid) return;
    if (!pendingPt) {
      setPendingPt({ i: p.i, price: p.price });
    } else {
      const newDraw = { id: Date.now(), kind: drawing, a: pendingPt, b: { i: p.i, price: p.price } };
      setDrawings([...(drawings || []), newDraw]);
      setPendingPt(null);
      setDrawing(null);
    }
  }

  // Build paths for MAs / BB
  function pathFrom(arr) {
    let d = '';
    for (let i = 0; i < slice.length; i++) {
      const v = arr[from + i];
      if (v == null) continue;
      const x = xAt(i);
      const y = yAt(v);
      d += (d ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
    }
    return d;
  }

  const trendColor = (t) => (t === 'up' ? upColor : t === 'down' ? downColor : 'rgba(180,180,200,0.18)');

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height: '100%', display: 'block', cursor: drawing ? 'crosshair' : 'crosshair' }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      onClick={onClick}
    >
      {/* Grid */}
      {yTicks.map((v, k) => (
        <g key={'gy' + k}>
          <line x1={padL} x2={width - padR} y1={yAt(v)} y2={yAt(v)} stroke="rgba(255,255,255,0.04)" />
          <text x={width - padR + 4} y={yAt(v) + 3} fontSize="10" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.55)">
            {fmt.price(v, instrument.meta.currency)}
          </text>
        </g>
      ))}
      {xTicks.map((i, k) => (
        <g key={'gx' + k}>
          <line x1={xAt(i)} x2={xAt(i)} y1={padT} y2={padT + H} stroke="rgba(255,255,255,0.03)" />
          <text x={xAt(i)} y={height - 8} fontSize="10" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.5)" textAnchor="middle">
            {fmt.shortDate(slice[i].t)}
          </text>
        </g>
      ))}

      {/* Trend strip */}
      {trendBand && (
        <g>
          {trendStrip.map((t, i) => (
            <rect key={'ts' + i} x={xAt(i) - cw / 2} y={padT + H + 4} width={cw + 0.5} height={4} fill={trendColor(t)} opacity={t === 'side' ? 0.5 : 0.85} />
          ))}
        </g>
      )}

      {/* Bollinger fill */}
      {indicators.bb && (
        <g opacity="0.35">
          <path d={pathFrom(ind.bb.up) + ' ' + slice.map((_, i) => {
            const v = ind.bb.lo[from + (slice.length - 1 - i)];
            if (v == null) return '';
            return 'L' + xAt(slice.length - 1 - i).toFixed(1) + ' ' + yAt(v).toFixed(1) + ' ';
          }).join('') + 'Z'} fill="rgba(120,160,210,0.10)" stroke="none" />
          <path d={pathFrom(ind.bb.up)} fill="none" stroke="rgba(150,180,220,0.55)" strokeWidth="0.8" strokeDasharray="2 3" />
          <path d={pathFrom(ind.bb.lo)} fill="none" stroke="rgba(150,180,220,0.55)" strokeWidth="0.8" strokeDasharray="2 3" />
        </g>
      )}

      {/* MAs */}
      {indicators.ma20 && <path d={pathFrom(ind.ma20)} fill="none" stroke="oklch(0.78 0.16 75)" strokeWidth="1.2" />}
      {indicators.ma60 && <path d={pathFrom(ind.ma60)} fill="none" stroke="oklch(0.70 0.13 230)" strokeWidth="1.2" />}
      {indicators.ma120 && <path d={pathFrom(ind.ma120)} fill="none" stroke="oklch(0.62 0.18 320)" strokeWidth="1.2" opacity="0.8" />}

      {/* RSI Price Bands — Pine red(상단) / green(하단), inner 진하게 / outer 50% / mid 굵게 */}
      {indicators.rpb && ind.rpb && (() => {
        const upColorRpb = 'oklch(0.62 0.22 25)';   // red
        const dnColorRpb = 'oklch(0.65 0.18 145)';  // green
        // currentRsi가 50 이상이면 상단만, 미만이면 하단만 — Pine 모방 단방향
        // 토글로 강제 양방향 표시 가능 (indicators.rpbBoth)
        const lastRsi = ind.rsi14[ind.rsi14.length - 1];
        const showUp = indicators.rpbBoth || lastRsi == null || lastRsi >= 50;
        const showDn = indicators.rpbBoth || lastRsi == null || lastRsi < 50;
        const lineProps = (color, opacity, width, dash) => ({
          fill: 'none', stroke: color, strokeWidth: width,
          strokeOpacity: opacity, strokeDasharray: dash || undefined,
        });
        return (
          <g className="rpb-overlay">
            {showUp && (
              <>
                <path className="rpb-line" data-rpb="UP_80" d={pathFrom(ind.rpb.up[80])} {...lineProps(upColorRpb, 0.5, 1, '4 3')} />
                <path className="rpb-line" data-rpb="UP_75" d={pathFrom(ind.rpb.up[75])} {...lineProps(upColorRpb, 0.85, 2)} />
                <path className="rpb-line" data-rpb="UP_70" d={pathFrom(ind.rpb.up[70])} {...lineProps(upColorRpb, 1, 1)} />
              </>
            )}
            {showDn && (
              <>
                <path className="rpb-line" data-rpb="DN_30" d={pathFrom(ind.rpb.dn[30])} {...lineProps(dnColorRpb, 1, 1)} />
                <path className="rpb-line" data-rpb="DN_25" d={pathFrom(ind.rpb.dn[25])} {...lineProps(dnColorRpb, 0.85, 2)} />
                <path className="rpb-line" data-rpb="DN_20" d={pathFrom(ind.rpb.dn[20])} {...lineProps(dnColorRpb, 0.5, 1, '4 3')} />
              </>
            )}
            {/* Right-edge labels (Pine 모방) */}
            {[
              showUp && [80, ind.rpb.up[80], upColorRpb, 0.5],
              showUp && [75, ind.rpb.up[75], upColorRpb, 0.85],
              showUp && [70, ind.rpb.up[70], upColorRpb, 1],
              showDn && [30, ind.rpb.dn[30], dnColorRpb, 1],
              showDn && [25, ind.rpb.dn[25], dnColorRpb, 0.85],
              showDn && [20, ind.rpb.dn[20], dnColorRpb, 0.5],
            ].filter(Boolean).map(([rsi_t, series, color, op]) => {
              const lastIdx = series.length - 1;
              let v = null;
              for (let k = lastIdx; k >= 0; k--) { if (series[k] != null) { v = series[k]; break; } }
              if (v == null) return null;
              const lastClose = slice[slice.length - 1]?.c;
              const pct = lastClose ? ((v - lastClose) / lastClose * 100).toFixed(1) : '';
              const sign = pct >= 0 ? '+' : '';
              return (
                <text
                  key={'rpb-lbl-' + rsi_t}
                  className="rpb-label mono"
                  x={W - 4}
                  y={yAt(v) - 2}
                  textAnchor="end"
                  fill={color}
                  fillOpacity={op}
                  fontSize="9"
                >
                  RSI {rsi_t} ({sign}{pct}%)
                </text>
              );
            })}
          </g>
        );
      })()}

      {/* Candles */}
      {slice.map((c, i) => {
        const x = xAt(i);
        const up = c.c >= c.o;
        const color = up ? upColor : downColor;
        const yOpen = yAt(c.o);
        const yClose = yAt(c.c);
        const yHi = yAt(c.h);
        const yLo = yAt(c.l);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyH = Math.max(0.6, Math.abs(yClose - yOpen));
        const bw = Math.max(1, cw * 0.7);
        return (
          <g key={'c' + i}>
            <line x1={x} x2={x} y1={yHi} y2={yLo} stroke={color} strokeWidth="0.8" />
            <rect x={x - bw / 2} y={bodyTop} width={bw} height={bodyH} fill={color} stroke={color} />
          </g>
        );
      })}

      {/* Signal markers */}
      {signalsOn && sigSlice.map((s, k) => {
        const i = s.i - from;
        const c = candles[s.i];
        const dirFn = window.MarketData.helpers.signalDirection || ((kk) => (kk === 'golden_cross' || kk === 'rsi_oversold' || kk === 'macd_bull_cross' || kk === 'rsi_bull_div' ? 'buy' : 'sell'));
        const dir = dirFn(s.kind);
        const above = dir === 'sell';
        const y = above ? yAt(c.h) - 14 : yAt(c.l) + 14;
        const color = above ? downColor : upColor;
        const labelMap = { golden_cross: 'G', death_cross: 'D', rsi_oversold: 'OS', rsi_overbought: 'OB', macd_bull_cross: 'M↑', macd_bear_cross: 'M↓', rsi_bull_div: 'D+', rsi_bear_div: 'D−' };
        const label = labelMap[s.kind] || '?';
        return (
          <g key={'sig' + k}>
            <polygon
              points={above ? `${xAt(i)},${y + 6} ${xAt(i) - 4.5},${y - 2} ${xAt(i) + 4.5},${y - 2}` : `${xAt(i)},${y - 6} ${xAt(i) - 4.5},${y + 2} ${xAt(i) + 4.5},${y + 2}`}
              fill={color}
              opacity="0.9"
            />
            <text x={xAt(i)} y={above ? y - 6 : y + 14} fontSize="9" fontFamily="JetBrains Mono, monospace" fill={color} textAnchor="middle" fontWeight="600">{label}</text>
          </g>
        );
      })}

      {/* Trade entries/exits */}
      {tradeSlice.map((tr, k) => {
        const e = tr.entryI - from;
        const x = tr.exitI - from;
        const valid = e >= 0 && e < slice.length;
        const validX = x >= 0 && x < slice.length;
        return (
          <g key={'tr' + k}>
            {valid && (
              <g>
                <line x1={xAt(e)} x2={xAt(e)} y1={padT} y2={padT + H} stroke={upColor} strokeOpacity="0.18" strokeDasharray="3 4" />
              </g>
            )}
            {validX && (
              <line x1={xAt(x)} x2={xAt(x)} y1={padT} y2={padT + H} stroke={downColor} strokeOpacity="0.18" strokeDasharray="3 4" />
            )}
          </g>
        );
      })}

      {/* User drawings */}
      {(drawings || []).map((d) => {
        const ai = d.a.i - from, bi = d.b.i - from;
        if (d.kind === 'trend') {
          return (
            <g key={d.id}>
              <line x1={xAt(ai)} y1={yAt(d.a.price)} x2={xAt(bi)} y2={yAt(d.b.price)} stroke="oklch(0.78 0.16 75)" strokeWidth="1.4" />
              <circle cx={xAt(ai)} cy={yAt(d.a.price)} r="3" fill="oklch(0.78 0.16 75)" />
              <circle cx={xAt(bi)} cy={yAt(d.b.price)} r="3" fill="oklch(0.78 0.16 75)" />
            </g>
          );
        }
        if (d.kind === 'fib') {
          const top = Math.max(d.a.price, d.b.price);
          const bot = Math.min(d.a.price, d.b.price);
          const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
          const x1 = Math.min(xAt(ai), xAt(bi));
          const x2 = Math.max(xAt(ai), xAt(bi));
          return (
            <g key={d.id}>
              {levels.map((lv, k) => {
                const p = top - (top - bot) * lv;
                return (
                  <g key={k}>
                    <line x1={x1} y1={yAt(p)} x2={width - padR} y2={yAt(p)} stroke="oklch(0.70 0.13 230)" strokeWidth="0.7" strokeDasharray={lv === 0 || lv === 1 ? '' : '3 3'} opacity="0.7" />
                    <text x={x1 + 4} y={yAt(p) - 2} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="oklch(0.70 0.13 230)">
                      {(lv * 100).toFixed(1)}% · {fmt.price(p, instrument.meta.currency)}
                    </text>
                  </g>
                );
              })}
              <line x1={xAt(ai)} y1={yAt(d.a.price)} x2={xAt(bi)} y2={yAt(d.b.price)} stroke="oklch(0.70 0.13 230 / 0.5)" strokeWidth="0.8" strokeDasharray="2 3" />
            </g>
          );
        }
        return null;
      })}

      {/* Pending drawing point */}
      {pendingPt && hoverPrice != null && hoverIdx != null && drawing && (
        <g pointerEvents="none">
          {drawing === 'trend' && (
            <line x1={xAt(pendingPt.i - from)} y1={yAt(pendingPt.price)} x2={xAt(hoverIdx - from)} y2={yAt(hoverPrice)} stroke="oklch(0.78 0.16 75)" strokeWidth="1.2" strokeDasharray="3 3" opacity="0.8" />
          )}
          {drawing === 'fib' && (
            <rect x={Math.min(xAt(pendingPt.i - from), xAt(hoverIdx - from))} y={yAt(Math.max(pendingPt.price, hoverPrice))} width={Math.abs(xAt(hoverIdx - from) - xAt(pendingPt.i - from))} height={Math.abs(yAt(Math.min(pendingPt.price, hoverPrice)) - yAt(Math.max(pendingPt.price, hoverPrice)))} fill="oklch(0.70 0.13 230 / 0.08)" stroke="oklch(0.70 0.13 230)" strokeDasharray="3 3" />
          )}
          <circle cx={xAt(pendingPt.i - from)} cy={yAt(pendingPt.price)} r="3" fill="oklch(0.78 0.16 75)" />
        </g>
      )}

      {/* Crosshair */}
      {hoverIdx != null && hoverIdx >= from && hoverIdx < to && (
        <g>
          <line x1={xAt(hoverIdx - from)} x2={xAt(hoverIdx - from)} y1={padT} y2={padT + H} stroke="rgba(245,210,140,0.5)" strokeWidth="0.8" />
          <line x1={padL} x2={width - padR} y1={yAt(candles[hoverIdx].c)} y2={yAt(candles[hoverIdx].c)} stroke="rgba(245,210,140,0.5)" strokeWidth="0.6" strokeDasharray="2 3" />
          <rect x={width - padR + 1} y={yAt(candles[hoverIdx].c) - 8} width={padR - 4} height={16} fill="oklch(0.78 0.16 75)" />
          <text x={width - padR + 4} y={yAt(candles[hoverIdx].c) + 3} fontSize="10" fontFamily="JetBrains Mono, monospace" fontWeight="700" fill="oklch(0.16 0.005 240)">
            {fmt.price(candles[hoverIdx].c, instrument.meta.currency)}
          </text>
        </g>
      )}
    </svg>
  );
}

// ─── Volume bars ──────────────────────────────────────────────
function VolumeChart({ instrument, view, upColor, downColor, hoverIdx }) {
  const { candles } = instrument;
  const width = 1100, height = 70, padL = 8, padR = 64, padT = 4, padB = 4;
  const slice = candles.slice(view[0], view[1]);
  const max = Math.max(...slice.map((c) => c.v));
  const W = width - padL - padR, H = height - padT - padB;
  const cw = W / slice.length;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%', display: 'block' }}>
      {slice.map((c, i) => {
        const h = (c.v / max) * H;
        const up = c.c >= c.o;
        const x = padL + i * cw + cw * 0.15;
        const bw = cw * 0.7;
        return <rect key={i} x={x} y={padT + H - h} width={bw} height={h} fill={up ? upColor : downColor} opacity="0.6" />;
      })}
      <text x={width - padR + 4} y={padT + 10} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.5)">VOL</text>
      <text x={width - padR + 4} y={padT + H - 2} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.5)">{fmt.vol(max)}</text>
      {hoverIdx != null && hoverIdx >= view[0] && hoverIdx < view[1] && (
        <line x1={padL + (hoverIdx - view[0] + 0.5) * cw} x2={padL + (hoverIdx - view[0] + 0.5) * cw} y1={padT} y2={padT + H} stroke="rgba(245,210,140,0.5)" strokeWidth="0.8" />
      )}
    </svg>
  );
}

// ─── RSI ─────────────────────────────────────────────────────
function RSIChart({ instrument, view, hoverIdx }) {
  const { ind, candles } = instrument;
  const width = 1100, height = 90, padL = 8, padR = 64, padT = 6, padB = 4;
  const W = width - padL - padR, H = height - padT - padB;
  const cw = W / (view[1] - view[0]);
  const xAt = (i) => padL + (i + 0.5) * cw;
  const yAt = (v) => padT + H - (v / 100) * H;
  let d = '';
  for (let i = view[0]; i < view[1]; i++) {
    const v = ind.rsi14[i];
    if (v == null) continue;
    const x = xAt(i - view[0]), y = yAt(v);
    d += (d ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
  }
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%', display: 'block' }}>
      <rect x={padL} y={yAt(70)} width={W} height={yAt(30) - yAt(70)} fill="rgba(255,255,255,0.025)" />
      <line x1={padL} x2={width - padR} y1={yAt(70)} y2={yAt(70)} stroke="rgba(255,160,160,0.35)" strokeDasharray="2 3" />
      <line x1={padL} x2={width - padR} y1={yAt(30)} y2={yAt(30)} stroke="rgba(160,220,180,0.35)" strokeDasharray="2 3" />
      <line x1={padL} x2={width - padR} y1={yAt(50)} y2={yAt(50)} stroke="rgba(255,255,255,0.06)" />
      <path d={d} fill="none" stroke="oklch(0.78 0.16 75)" strokeWidth="1.2" />
      <text x={width - padR + 4} y={padT + 9} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.55)">RSI 14</text>
      <text x={width - padR + 4} y={yAt(70) + 3} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="rgba(255,180,180,0.7)">70</text>
      <text x={width - padR + 4} y={yAt(30) + 3} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="rgba(180,220,200,0.7)">30</text>
      {hoverIdx != null && hoverIdx >= view[0] && hoverIdx < view[1] && (
        <g>
          <line x1={xAt(hoverIdx - view[0])} x2={xAt(hoverIdx - view[0])} y1={padT} y2={padT + H} stroke="rgba(245,210,140,0.5)" strokeWidth="0.8" />
          {ind.rsi14[hoverIdx] != null && (
            <text x={width - padR + 4} y={yAt(ind.rsi14[hoverIdx]) + 3} fontSize="10" fontFamily="JetBrains Mono, monospace" fontWeight="700" fill="oklch(0.78 0.16 75)">
              {ind.rsi14[hoverIdx].toFixed(1)}
            </text>
          )}
        </g>
      )}
    </svg>
  );
}

// ─── MACD ────────────────────────────────────────────────────
function MACDChart({ instrument, view, hoverIdx, upColor, downColor }) {
  const { ind } = instrument;
  const width = 1100, height = 90, padL = 8, padR = 64, padT = 6, padB = 4;
  const W = width - padL - padR, H = height - padT - padB;
  const slice = view[1] - view[0];
  const cw = W / slice;
  const arr = ind.macd.line.slice(view[0], view[1]);
  const sigA = ind.macd.signal.slice(view[0], view[1]);
  const histA = ind.macd.hist.slice(view[0], view[1]);
  const all = [...arr, ...sigA, ...histA].filter((v) => v != null);
  const max = Math.max(...all.map(Math.abs));
  const yAt = (v) => padT + H / 2 - (v / max) * (H / 2 - 2);
  const xAt = (i) => padL + (i + 0.5) * cw;
  function path(a) {
    let d = '';
    for (let i = 0; i < a.length; i++) {
      if (a[i] == null) continue;
      d += (d ? 'L' : 'M') + xAt(i).toFixed(1) + ' ' + yAt(a[i]).toFixed(1) + ' ';
    }
    return d;
  }
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%', display: 'block' }}>
      <line x1={padL} x2={width - padR} y1={padT + H / 2} y2={padT + H / 2} stroke="rgba(255,255,255,0.07)" />
      {histA.map((v, i) => {
        if (v == null) return null;
        const y = yAt(v);
        const yz = padT + H / 2;
        return <rect key={i} x={xAt(i) - cw * 0.35} y={Math.min(y, yz)} width={cw * 0.7} height={Math.abs(y - yz) + 0.5} fill={v >= 0 ? upColor : downColor} opacity="0.55" />;
      })}
      <path d={path(arr)} fill="none" stroke="oklch(0.78 0.16 75)" strokeWidth="1.2" />
      <path d={path(sigA)} fill="none" stroke="oklch(0.70 0.13 230)" strokeWidth="1.2" />
      <text x={width - padR + 4} y={padT + 9} fontSize="9" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.55)">MACD</text>
      {hoverIdx != null && hoverIdx >= view[0] && hoverIdx < view[1] && (
        <line x1={xAt(hoverIdx - view[0])} x2={xAt(hoverIdx - view[0])} y1={padT} y2={padT + H} stroke="rgba(245,210,140,0.5)" strokeWidth="0.8" />
      )}
    </svg>
  );
}

// ─── Sparkline (watchlist) ────────────────────────────────────
function MiniSpark({ candles, upColor, downColor }) {
  const width = 96, height = 24;
  const last = candles.slice(-40);
  const lo = Math.min(...last.map((c) => c.l));
  const hi = Math.max(...last.map((c) => c.h));
  const W = width, H = height;
  const cw = W / last.length;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width, height, display: 'block' }}>
      {last.map((c, i) => {
        const yh = H - ((c.h - lo) / (hi - lo)) * H;
        const yl = H - ((c.l - lo) / (hi - lo)) * H;
        const yo = H - ((c.o - lo) / (hi - lo)) * H;
        const yc = H - ((c.c - lo) / (hi - lo)) * H;
        const up = c.c >= c.o;
        const x = i * cw + cw / 2;
        const bw = Math.max(1, cw * 0.6);
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={yh} y2={yl} stroke={up ? upColor : downColor} strokeWidth="0.5" />
            <rect x={x - bw / 2} y={Math.min(yo, yc)} width={bw} height={Math.max(0.5, Math.abs(yc - yo))} fill={up ? upColor : downColor} />
          </g>
        );
      })}
    </svg>
  );
}

// ─── Equity curve ────────────────────────────────────────────
function EquityCurve({ equity, trades, upColor, downColor }) {
  const width = 800, height = 240, padL = 36, padR = 12, padT = 12, padB = 22;
  const eqs = equity.map((e) => e.eq);
  const lo = Math.min(...eqs);
  const hi = Math.max(...eqs);
  const W = width - padL - padR;
  const H = height - padT - padB;
  const xAt = (i) => padL + (i / (equity.length - 1)) * W;
  const yAt = (v) => padT + H - ((v - lo) / (hi - lo)) * H;
  let d = '';
  let dArea = '';
  for (let i = 0; i < equity.length; i++) {
    const x = xAt(i), y = yAt(equity[i].eq);
    d += (d ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
  }
  dArea = d + ' L' + xAt(equity.length - 1) + ' ' + (padT + H) + ' L' + xAt(0) + ' ' + (padT + H) + ' Z';
  // ticks
  const yTicks = [lo, lo + (hi - lo) / 2, hi];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%', display: 'block' }}>
      <defs>
        <linearGradient id="eqfill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="oklch(0.78 0.16 75)" stopOpacity="0.32" />
          <stop offset="100%" stopColor="oklch(0.78 0.16 75)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {yTicks.map((v, k) => (
        <g key={k}>
          <line x1={padL} x2={width - padR} y1={yAt(v)} y2={yAt(v)} stroke="rgba(255,255,255,0.05)" />
          <text x={padL - 4} y={yAt(v) + 3} textAnchor="end" fontSize="10" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.55)">
            {(v * 100 - 100).toFixed(0)}%
          </text>
        </g>
      ))}
      <line x1={padL} x2={width - padR} y1={yAt(1)} y2={yAt(1)} stroke="rgba(255,255,255,0.18)" strokeDasharray="2 3" />
      <path d={dArea} fill="url(#eqfill)" />
      <path d={d} fill="none" stroke="oklch(0.78 0.16 75)" strokeWidth="1.4" />
      {trades.map((t, k) => (
        <g key={k}>
          <circle cx={xAt(t.entryI)} cy={yAt(equity[t.entryI].eq)} r="2.5" fill={upColor} />
          <circle cx={xAt(t.exitI)} cy={yAt(equity[t.exitI].eq)} r="2.5" fill={t.ret >= 0 ? upColor : downColor} />
        </g>
      ))}
    </svg>
  );
}

// ─── Drawdown ────────────────────────────────────────────────
function DrawdownChart({ equity }) {
  const width = 800, height = 90, padL = 36, padR = 12, padT = 8, padB = 16;
  let peak = -Infinity;
  const dd = equity.map((e) => {
    peak = Math.max(peak, e.eq);
    return (e.eq - peak) / peak;
  });
  const lo = Math.min(...dd);
  const W = width - padL - padR, H = height - padT - padB;
  const xAt = (i) => padL + (i / (dd.length - 1)) * W;
  const yAt = (v) => padT + (-v / -lo) * H;
  let d = '';
  for (let i = 0; i < dd.length; i++) {
    const x = xAt(i), y = yAt(dd[i]);
    d += (d ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
  }
  d += ` L${xAt(dd.length - 1)} ${padT} L${xAt(0)} ${padT} Z`;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%', display: 'block' }}>
      <text x={padL - 4} y={padT + 8} textAnchor="end" fontSize="10" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.55)">0%</text>
      <text x={padL - 4} y={padT + H + 3} textAnchor="end" fontSize="10" fontFamily="JetBrains Mono, monospace" fill="rgba(220,225,235,0.55)">{(lo * 100).toFixed(1)}%</text>
      <path d={d} fill="oklch(0.65 0.22 25 / 0.32)" stroke="oklch(0.65 0.22 25)" strokeWidth="1" />
    </svg>
  );
}

Object.assign(window, { CandleChart, VolumeChart, RSIChart, MACDChart, MiniSpark, EquityCurve, DrawdownChart, fmt });
