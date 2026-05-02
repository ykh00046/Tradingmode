// Strategy Coach — 5th tab.
// Editor → 70/30 split backtest → AI recommendations → apply → re-run.
// All persistence happens server-side via /api/strategy/{backtest,iterations}.

const { useState: useStateSC, useEffect: useEffectSC, useMemo: useMemoSC, useRef: useRefSC } = React;

const GOAL_OPTIONS = [
  ['sharpe',   '샤프 비율'],
  ['return',   '수익률'],
  ['mdd',      'MDD 최소화'],
  ['win_rate', '승률'],
];

const TEMPLATES = [
  {
    name: 'Conservative RSI',
    buy_when: 'RSI_14 < 30 and ADX_14 > 20',
    sell_when: 'RSI_14 > 70',
  },
  {
    name: 'MA Crossover',
    buy_when: 'SMA_20 > SMA_60 and SMA_60 > SMA_120',
    sell_when: 'SMA_20 < SMA_60',
  },
  {
    name: 'MACD Momentum',
    buy_when: 'MACDh_12_26_9 > 0 and MACD_12_26_9 > MACDs_12_26_9',
    sell_when: 'MACDh_12_26_9 < 0',
  },
  {
    name: 'BB Squeeze',
    buy_when: 'close < BBL_20_2.0_2.0 and RSI_14 < 40',
    sell_when: 'close > BBM_20_2.0_2.0',
  },
  {
    name: 'RSI Imminent',
    buy_when: 'close < RPB_DN_30 and RPB_DN_30_BARS > -1.5',
    sell_when: 'close > RPB_UP_70',
  },
];

// role → (target field, combinator)
const ROLE_COMBINATORS = {
  entry_filter: { field: 'buy_when',  joiner: 'and' },
  filter:       { field: 'buy_when',  joiner: 'and' },
  exit_rule:    { field: 'sell_when', joiner: 'or'  },
};

function StrategyCoachPage({ universe, currentSymbol, setCurrent, upColor, downColor }) {
  const [strategy, setStrategy] = useStateSC({
    name: TEMPLATES[1].name,
    buy_when: TEMPLATES[1].buy_when,
    sell_when: TEMPLATES[1].sell_when,
    holding_max_bars: null,
    optimization_goal: 'sharpe',
    costs: { commission_bps: 5, slippage_bps: 2, kr_sell_tax_bps: 18, apply_kr_tax: true },
  });
  const [splitResult, setSplitResult] = useStateSC(null);
  const [coachResult, setCoachResult] = useStateSC(null);
  const [history, setHistory] = useStateSC([]);
  const [error, setError] = useStateSC(null);
  const [loadingBacktest, setLoadingBacktest] = useStateSC(false);
  const [loadingCoach, setLoadingCoach] = useStateSC(false);
  const [builtins, setBuiltins] = useStateSC(null);
  const ctlRef = useRefSC(null);

  const symbolMeta = universe.find((u) => u.symbol === currentSymbol) || universe[0];
  const market = symbolMeta?.market === 'kr' ? 'kr_stock' : 'crypto';
  const symbolForBackend = (symbolMeta?.symbol || '').replace('/', '');
  const interval = '1d';

  // Load builtins once for autocomplete hints in editor.
  useEffectSC(() => {
    let alive = true;
    window.api.strategy.builtins().then(
      (b) => { if (alive) setBuiltins(b); },
      () => { /* non-fatal */ },
    );
    return () => { alive = false; };
  }, []);

  // Load history whenever the active symbol changes.
  useEffectSC(() => {
    let alive = true;
    if (!symbolForBackend) return;
    window.api.strategy.iterations({ symbol: symbolForBackend, interval, limit: 50 }).then(
      (rows) => { if (alive) setHistory(rows); },
      () => { /* non-fatal — empty history */ },
    );
    return () => { alive = false; };
  }, [symbolForBackend]);

  function applyTemplate(t) {
    setStrategy((s) => ({ ...s, name: t.name, buy_when: t.buy_when, sell_when: t.sell_when }));
    setError(null);
  }

  function setCost(key, value) {
    setStrategy((s) => ({ ...s, costs: { ...s.costs, [key]: value } }));
  }

  async function runBacktest() {
    if (!symbolForBackend) return;
    setError(null);
    setLoadingBacktest(true);
    setCoachResult(null);
    if (ctlRef.current) ctlRef.current.abort();
    const ctl = new AbortController();
    ctlRef.current = ctl;
    const range = window.api.dateRange(365);
    const body = {
      market,
      symbol: symbolForBackend,
      interval,
      start: range.start,
      end: range.end,
      split_ratio: 0.7,
      cash: 1_000_000,
      persist: true,
      strategy,
    };
    try {
      const result = await window.api.strategy.backtest(body, { signal: ctl.signal, timeout: 30000 });
      setSplitResult(result);
      // Refresh history (we just appended an entry).
      const rows = await window.api.strategy.iterations({
        symbol: symbolForBackend, interval, limit: 50,
      });
      setHistory(rows);
    } catch (e) {
      if (e?.name === 'AbortError') return;
      setError(e?.message || String(e));
    } finally {
      setLoadingBacktest(false);
    }
  }

  async function runCoach() {
    if (!splitResult) return;
    setLoadingCoach(true);
    setError(null);
    try {
      const r = splitResult.is_result;
      const body = {
        strategy,
        is_result: {
          total_return:  r.total_return,
          annual_return: r.annual_return,
          max_drawdown:  r.max_drawdown,
          win_rate:      r.win_rate,
          sharpe_ratio:  r.sharpe_ratio,
          num_trades:    r.num_trades,
        },
        history_summary: history.slice(0, 5).map((h) => ({
          attempt: h.attempt_no,
          is_return: h.is_total_return,
          oos_return: h.oos_total_return,
          sharpe: h.is_sharpe,
        })),
      };
      const resp = await window.api.aiCoach(body, { timeout: 30000 });
      setCoachResult(resp);
    } catch (e) {
      const msg = e?.code === 'AI_SERVICE_ERROR'
        ? 'AI 코치 사용 불가 — GROQ_API_KEY 설정 확인'
        : (e?.message || String(e));
      setError(msg);
      setCoachResult(null);
    } finally {
      setLoadingCoach(false);
    }
  }

  function applyRecommendation(rec) {
    if (!rec.available || !rec.sample_rule) return;
    const combinator = ROLE_COMBINATORS[rec.role];
    if (!combinator) return;
    setStrategy((s) => {
      const existing = (s[combinator.field] || '').trim();
      const next = existing
        ? `(${existing}) ${combinator.joiner} (${rec.sample_rule})`
        : rec.sample_rule;
      return { ...s, [combinator.field]: next };
    });
  }

  function loadHistoryRow(row) {
    try {
      const def = JSON.parse(row.strategy_def_json);
      setStrategy({
        name:              def.name || 'restored',
        buy_when:          def.buy_when || 'True',
        sell_when:         def.sell_when || 'False',
        holding_max_bars:  def.holding_max_bars ?? null,
        optimization_goal: def.optimization_goal || 'sharpe',
        costs: def.costs || strategy.costs,
      });
      setError(null);
    } catch (e) {
      setError('이력 복원 실패: ' + e.message);
    }
  }

  return (
    <div className="strategy-coach-page" data-screen-label="05 Strategy Coach">
      <div className="sc-header">
        <div className="sc-title-block">
          <div className="sc-title">Strategy Coach</div>
          <div className="sc-sub muted">
            {symbolMeta?.symbol} · {symbolMeta?.name} · 70/30 split · BTC 위주 시연
          </div>
        </div>
        <div className="sc-templates">
          {TEMPLATES.map((t) => (
            <button key={t.name} className="sc-template-btn" onClick={() => applyTemplate(t)}>
              {t.name}
            </button>
          ))}
        </div>
      </div>

      <div className="sc-grid">
        {/* Editor */}
        <EditorPanel
          strategy={strategy}
          setStrategy={setStrategy}
          setCost={setCost}
          builtins={builtins}
          onRun={runBacktest}
          loading={loadingBacktest}
        />
        {/* Results */}
        <ResultPanel result={splitResult} onAskCoach={runCoach} loadingCoach={loadingCoach} hasCoach={!!coachResult} />
        {/* Coach */}
        <CoachPanel
          coach={coachResult}
          loading={loadingCoach}
          onApply={applyRecommendation}
          available={!!splitResult}
        />
      </div>

      {error && <div className="sc-error">⚠️ {error}</div>}

      <HistoryTable rows={history} onLoad={loadHistoryRow} />
    </div>
  );
}

// ─── Editor ─────────────────────────────────────────────────────
function EditorPanel({ strategy, setStrategy, setCost, builtins, onRun, loading }) {
  return (
    <div className="sc-panel sc-editor">
      <div className="panel-header">
        <span className="panel-title">전략 정의</span>
      </div>
      <div className="sc-field">
        <label className="sc-label">이름</label>
        <input
          className="sc-input"
          type="text"
          value={strategy.name}
          maxLength={80}
          onChange={(e) => setStrategy((s) => ({ ...s, name: e.target.value }))}
        />
      </div>
      <div className="sc-field">
        <label className="sc-label">매수 조건 (buy_when)</label>
        <textarea
          className="sc-textarea mono"
          value={strategy.buy_when}
          rows={2}
          onChange={(e) => setStrategy((s) => ({ ...s, buy_when: e.target.value }))}
        />
      </div>
      <div className="sc-field">
        <label className="sc-label">매도 조건 (sell_when)</label>
        <textarea
          className="sc-textarea mono"
          value={strategy.sell_when}
          rows={2}
          onChange={(e) => setStrategy((s) => ({ ...s, sell_when: e.target.value }))}
        />
      </div>

      {builtins && (
        <details className="sc-builtins">
          <summary>사용 가능 컬럼 ({builtins.indicators.reduce((a, b) => a + b.columns.length, 0)})</summary>
          <div className="sc-builtin-list mono">
            {builtins.indicators.map((b) => (
              <div key={b.name} className="sc-builtin">
                <strong>{b.name}</strong>
                <span className="muted"> {b.columns.join(', ')}</span>
              </div>
            ))}
            <div className="sc-builtin"><strong>helpers</strong> <span className="muted">{builtins.helpers.join(', ')}</span></div>
          </div>
        </details>
      )}

      <div className="sc-row">
        <div className="sc-field">
          <label className="sc-label">최적화 목표</label>
          <select
            className="sc-input"
            value={strategy.optimization_goal}
            onChange={(e) => setStrategy((s) => ({ ...s, optimization_goal: e.target.value }))}
          >
            {GOAL_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="sc-field">
          <label className="sc-label">강제 청산 (봉 수)</label>
          <input
            className="sc-input"
            type="number"
            min="1"
            value={strategy.holding_max_bars ?? ''}
            placeholder="없음"
            onChange={(e) => {
              const v = e.target.value;
              setStrategy((s) => ({ ...s, holding_max_bars: v === '' ? null : Math.max(1, parseInt(v, 10) || 0) }));
            }}
          />
        </div>
      </div>

      <div className="sc-costs">
        <div className="sc-label">거래비용 (BPS)</div>
        <div className="sc-row">
          <CostInput label="수수료" value={strategy.costs.commission_bps} max={100} onChange={(v) => setCost('commission_bps', v)} />
          <CostInput label="슬리피지" value={strategy.costs.slippage_bps} max={100} onChange={(v) => setCost('slippage_bps', v)} />
          <CostInput label="KR 매도세" value={strategy.costs.kr_sell_tax_bps} max={50} onChange={(v) => setCost('kr_sell_tax_bps', v)} />
        </div>
        <label className="sc-checkbox">
          <input
            type="checkbox"
            checked={strategy.costs.apply_kr_tax}
            onChange={(e) => setCost('apply_kr_tax', e.target.checked)}
          />
          KR 종목에 매도세 적용
        </label>
      </div>

      <button className="sc-run-btn" onClick={onRun} disabled={loading}>
        {loading ? '백테스트 중…' : '▶ 70/30 백테스트 실행'}
      </button>
    </div>
  );
}

function CostInput({ label, value, max, onChange }) {
  return (
    <div className="sc-cost-input">
      <label className="sc-label-small">{label}</label>
      <input
        className="sc-input mono"
        type="number"
        min="0"
        max={max}
        step="0.5"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      />
    </div>
  );
}

// ─── Results ───────────────────────────────────────────────────
function ResultPanel({ result, onAskCoach, loadingCoach, hasCoach }) {
  if (!result) {
    return (
      <div className="sc-panel sc-results">
        <div className="panel-header">
          <span className="panel-title">백테스트 결과</span>
        </div>
        <div className="sc-empty muted">왼쪽에서 ▶ 백테스트 실행</div>
      </div>
    );
  }
  const is = result.is_result;
  const oos = result.oos_result;
  return (
    <div className="sc-panel sc-results">
      <div className="panel-header">
        <span className="panel-title">백테스트 결과</span>
        {result.overfit_warning && <span className="sc-warning">⚠️ 과적합 위험</span>}
      </div>

      <div className="sc-stats-row">
        <SplitCard title="In-sample (70%)" stats={is} period={[result.is_period_start, result.is_period_end]} />
        <SplitCard
          title="Out-of-sample (30%)"
          stats={oos}
          period={oos ? [result.oos_period_start, result.oos_period_end] : null}
          missing={!oos}
        />
      </div>

      {result.is_oos_gap_pct != null && (
        <div className="sc-gap mono">
          IS-OOS gap: <strong>{result.is_oos_gap_pct.toFixed(2)}%</strong>
          {result.overfit_warning && <span className="sc-warn-text"> · 30% 초과 → 과적합 의심</span>}
        </div>
      )}

      {result.warnings?.length > 0 && (
        <ul className="sc-warnings">
          {result.warnings.map((w, i) => <li key={i}>· {w}</li>)}
        </ul>
      )}

      <button
        className="sc-coach-btn"
        onClick={onAskCoach}
        disabled={loadingCoach}
      >
        {loadingCoach ? 'AI 분석 중…' : (hasCoach ? '🤖 AI 다시 묻기' : '🤖 AI 코치에게 추천 받기')}
      </button>
    </div>
  );
}

function SplitCard({ title, stats, period, missing }) {
  if (missing || !stats) {
    return (
      <div className="sc-split-card sc-split-missing">
        <div className="sc-split-title">{title}</div>
        <div className="sc-empty muted">검증 불가 (봉 부족)</div>
      </div>
    );
  }
  const periodStr = period ? `${fmt.date(period[0])} ~ ${fmt.date(period[1])}` : '';
  return (
    <div className="sc-split-card">
      <div className="sc-split-title">
        {title}
        {periodStr && <span className="muted sc-split-period">{periodStr}</span>}
      </div>
      <Stat label="수익률" value={stats.total_return.toFixed(2) + '%'} tone={stats.total_return >= 0 ? 'up' : 'down'} />
      <Stat label="샤프" value={stats.sharpe_ratio.toFixed(2)} />
      <Stat label="MDD" value={stats.max_drawdown.toFixed(2) + '%'} tone="down" />
      <Stat label="승률" value={stats.win_rate.toFixed(1) + '%'} />
      <Stat label="거래 수" value={stats.num_trades} />
    </div>
  );
}

function Stat({ label, value, tone }) {
  return (
    <div className="sc-stat">
      <span className="sc-stat-label">{label}</span>
      <span className={'sc-stat-value mono' + (tone ? ' ' + tone : '')}>{value}</span>
    </div>
  );
}

// ─── Coach ─────────────────────────────────────────────────────
function CoachPanel({ coach, loading, onApply, available }) {
  return (
    <div className="sc-panel sc-coach">
      <div className="panel-header">
        <span className="panel-title">AI 코치</span>
        {coach && <span className="sc-coach-model mono muted">{coach.model}</span>}
      </div>

      {!available && <div className="sc-empty muted">백테스트 후 활성화</div>}
      {available && !coach && !loading && <div className="sc-empty muted">결과 패널에서 "AI 코치에게 추천 받기" 클릭</div>}
      {loading && <div className="sc-empty">분석 중…</div>}

      {coach && (
        <>
          <div className="sc-diagnosis">
            <span className="sc-diag-label">진단</span>
            <p>{coach.diagnosis}</p>
          </div>

          <div className="sc-recs">
            {coach.recommendations.map((r, i) => (
              <RecCard key={i} rec={r} onApply={onApply} />
            ))}
          </div>

          {coach.warnings?.length > 0 && (
            <div className="sc-coach-warnings">
              <span className="sc-warn-title">⚠️ 우려점</span>
              <ul>
                {coach.warnings.map((w, i) => <li key={i}>· {w}</li>)}
              </ul>
            </div>
          )}

          <div className="sc-disclaimer muted">{coach.disclaimer}</div>
        </>
      )}
    </div>
  );
}

function RecCard({ rec, onApply }) {
  const canApply = rec.available && !!rec.sample_rule;
  const cls = 'sc-rec' + (rec.available ? ' available' : ' unavailable');
  return (
    <div className={cls}>
      <div className="sc-rec-head">
        <span className="sc-rec-name">{rec.indicator}</span>
        <span className={'sc-rec-role role-' + rec.role}>{rec.role}</span>
        {!rec.available && <span className="sc-rec-flag">⚠️ 빌트인 미존재</span>}
      </div>
      <p className="sc-rec-reason">{rec.reason}</p>
      {rec.expected_synergy && <p className="sc-rec-synergy muted">시너지: {rec.expected_synergy}</p>}
      {rec.sample_rule && (
        <div className="sc-rec-sample mono">{rec.sample_rule}</div>
      )}
      {rec.available ? (
        <button className="sc-rec-apply" onClick={() => onApply(rec)} disabled={!canApply}>
          {canApply ? '적용 + 재실행 준비' : '수식 누락'}
        </button>
      ) : (
        <div className="sc-rec-cta muted">
          이 지표를 추가하려면 Claude(개발자)에게 요청하세요. 예: "ATR(14) 지표 추가해줘"
        </div>
      )}
    </div>
  );
}

// ─── History ───────────────────────────────────────────────────
function HistoryTable({ rows, onLoad }) {
  if (!rows.length) return null;
  return (
    <div className="sc-history">
      <div className="panel-header">
        <span className="panel-title">시도 이력 ({rows.length})</span>
      </div>
      <div className="sc-history-table">
        <div className="sc-history-head mono">
          <span>#</span>
          <span>이름</span>
          <span>IS 수익</span>
          <span>OOS 수익</span>
          <span>샤프 IS</span>
          <span>MDD IS</span>
          <span>Gap</span>
          <span>목표</span>
          <span>일시</span>
          <span></span>
        </div>
        {rows.map((r) => {
          let name = '?';
          try { name = JSON.parse(r.strategy_def_json).name; } catch (_) {}
          return (
            <div key={r.iteration_id} className={'sc-history-row mono' + (r.overfit_warning ? ' overfit' : '')}>
              <span>{r.attempt_no}</span>
              <span className="sc-history-name">{name}</span>
              <span className={r.is_total_return >= 0 ? 'up' : 'down'}>{r.is_total_return.toFixed(2)}%</span>
              <span className={r.oos_total_return == null ? 'muted' : (r.oos_total_return >= 0 ? 'up' : 'down')}>
                {r.oos_total_return == null ? '—' : r.oos_total_return.toFixed(2) + '%'}
              </span>
              <span>{r.is_sharpe.toFixed(2)}</span>
              <span className="down">{r.is_mdd.toFixed(2)}%</span>
              <span>{r.is_oos_gap_pct == null ? '—' : r.is_oos_gap_pct.toFixed(1) + '%'}</span>
              <span>{r.optimization_goal}</span>
              <span className="muted">{fmt.date(r.timestamp)}</span>
              <button className="sc-history-load" onClick={() => onLoad(r)}>복원</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
