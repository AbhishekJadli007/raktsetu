import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, ChevronDown, Clock, PencilLine, RefreshCw, Siren, Truck, X } from 'lucide-react'
import clsx from 'clsx'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtInt, type BankStatus, type Meta, type Plan, type Radar, type Trip } from '../api'
import { NetworkMap, type MapArc, type MapBank } from '../components/NetworkMap'
import { AnimatedNumber, Badge, Button, Card, coverColor, ErrorNote, Field, inputCls, Spinner } from '../components/ui'

type Overrides = Record<string, Record<string, number>>
const tipStyle = { background: '#171b24', border: '1px solid #262c3b', borderRadius: 10, fontSize: 12 }

export default function ControlRoom({ meta }: { meta: Meta }) {
  const [date, setDate] = useState(meta.dates.today)
  const [history, setHistory] = useState<'isolated' | 'reactive'>('isolated')
  const [vans, setVans] = useState(meta.defaults.vans)
  const [overrides, setOverrides] = useState<Overrides>({})
  const [plan, setPlan] = useState<Plan | null>(null)
  const [radar, setRadar] = useState<Radar | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [panel, setPanel] = useState<'trips' | 'escalate'>('trips')

  const run = useCallback((ov: Overrides = overrides) => {
    setLoading(true); setErr(null)
    Promise.all([
      api.plan({ date, history, scenario: { vans }, overrides: Object.keys(ov).length ? ov : null }),
      api.radar(date),
    ]).then(([p, r]) => { setPlan(p); setRadar(r) })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [date, history, vans, overrides])

  useEffect(() => { run() }, [date, history, vans]) // eslint-disable-line react-hooks/exhaustive-deps

  const pos = useMemo(() => Object.fromEntries(meta.banks.map((b) => [b.short, [b.lat, b.lon] as [number, number]])), [meta.banks])
  const mapBanks: MapBank[] = useMemo(() => (plan?.banks ?? []).map((b) => ({
    short: b.bank, name: b.name, lat: b.lat, lon: b.lon, color: coverColor(b.min_cover_days),
    size: 12 + Math.sqrt(b.rbc_stock + 4 * b.plt_stock) / 2, pulse: b.min_cover_days < 1 || b.short_skus.includes('PLT'),
    tooltip: `<div style="min-width:180px"><b>${b.name}</b><div style="color:#8a93a8;margin:2px 0 6px">${b.role} · ${b.operator}</div>` +
      `Red cells <b>${b.rbc_stock}</b> (${b.rbc_days_cover} days)<br/>Platelets <b>${b.plt_stock}</b> (${b.plt_days_cover} days)` +
      (b.at_risk_units ? `<br/><span style="color:#a78bfa">${b.at_risk_units} units at risk of expiry</span>` : '') + `</div>`,
  })), [plan])
  const arcs: MapArc[] = useMemo(() => (plan?.trips ?? []).map((t, i) => ({
    key: `${t.from}-${t.to}-${i}`, from: pos[t.from], to: pos[t.to], units: t.units,
    color: t.items.some((x) => x.sku === 'PLT') ? '#fb7185' : '#22d3ee',
  })), [plan, pos])

  const sel = plan?.banks.find((b) => b.bank === selected) ?? null
  const nOverrides = Object.values(overrides).reduce((a, o) => a + Object.keys(o).length, 0)

  return (
    <div className="space-y-5">
      {/* controls */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="mr-auto">
            <div className="text-[11px] uppercase tracking-[0.16em] text-blood-soft font-semibold">District control room · Jaipur</div>
            <h1 className="font-display text-2xl font-semibold">Morning transfer plan</h1>
          </div>
          <div className="w-40"><Field label="Date"><input type="date" className={inputCls} value={date} min={meta.dates.first} max={meta.dates.last} onChange={(e) => { const v = e.target.value; if (v && v >= meta.dates.first && v <= meta.dates.last) setDate(v) }} /></Field></div>
          <div className="w-52"><Field label="Until yesterday, banks…">
            <select className={inputCls} value={history} onChange={(e) => setHistory(e.target.value as 'isolated' | 'reactive')}>
              <option value="isolated">worked alone</option>
              <option value="reactive">phoned around when short</option>
            </select></Field></div>
          <div className="w-40"><Field label="Vans today" hint={`${vans} (${vans * meta.defaults.trips_per_van} trips)`}>
            <input type="range" min={0} max={6} value={vans} onChange={(e) => setVans(+e.target.value)} className="w-full" /></Field></div>
          <Button variant="ghost" onClick={() => run()} disabled={loading}><RefreshCw size={15} className={clsx(loading && 'animate-spin')} /> Re-plan</Button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-faint">Jump to:</span>
          {[[meta.dates.today, 'Today'], ['2024-08-20', '20 Aug 2024 · before the surge'], ['2024-09-20', '20 Sep 2024 · dengue peak']].map(([d, l]) => (
            <button key={d} onClick={() => setDate(d)}
              className={clsx('rounded-full border px-2.5 py-1 transition', date === d ? 'border-ours/60 bg-ours/10 text-ink' : 'border-line text-muted hover:text-ink')}>{l}</button>
          ))}
        </div>
        {nOverrides > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="warn"><PencilLine size={12} /> {nOverrides} stock value{nOverrides > 1 ? 's' : ''} typed in by you</Badge>
            {Object.entries(overrides).flatMap(([b, o]) => Object.entries(o).map(([s, n]) => <Badge key={b + s}>{b} {s} = {n}</Badge>))}
            <button className="text-muted hover:text-ink underline" onClick={() => { setOverrides({}); run({}) }}>clear</button>
          </div>
        )}
      </Card>

      {err && <ErrorNote error={err} />}

      {/* KPI strip */}
      {plan && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Kpi label="Van trips" value={plan.totals.trips} sub={`of ${plan.max_trips} available`} color="text-ours" />
          <Kpi label="Units moved" value={plan.totals.units} sub={`${plan.totals.km} km in total`} />
          <Kpi label="Saved from expiry" value={plan.totals.units_rescued_from_expiry} sub="units that would be discarded" color="text-waste" />
          <Kpi label="At risk city-wide" value={plan.totals.at_risk_units} sub="units expiring unused soon" />
          <Kpi label="Needs donors, not vans" value={plan.totals.unresolved_units} sub="shortfall no bank can spare" color="text-short" />
        </div>
      )}

      <div className="grid lg:grid-cols-[1.55fr_1fr] gap-5">
        {/* map */}
        <div className="relative">
          {plan ? <NetworkMap banks={mapBanks} arcs={arcs} selected={selected} onSelect={setSelected} height={600} /> : <Card className="h-[600px] grid place-items-center"><Spinner label="Simulating stock and solving today’s plan…" /></Card>}
          {loading && plan && <div className="absolute inset-0 z-[600] grid place-items-center rounded-2xl bg-bg/40 backdrop-blur-[2px]"><Spinner label="Re-planning…" /></div>}
          <div className="absolute top-3 right-3 z-[500] rounded-xl bg-bg/85 backdrop-blur border border-line px-3 py-2 text-[11px] space-y-1">
            <div className="text-faint mb-1">Days of cover (worst product)</div>
            {[['< 1 day', '#ef4444'], ['1–2', '#f97316'], ['2–3', '#f59e0b'], ['3+', '#34d399']].map(([l, c]) => (
              <div key={l} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{l}</div>
            ))}
            <div className="pt-1 border-t border-line flex items-center gap-2"><span className="h-0.5 w-4 bg-[#fb7185]" />carries platelets</div>
            <div className="flex items-center gap-2"><span className="h-0.5 w-4 bg-ours" />red cells only</div>
          </div>
          <AnimatePresence>
            {sel && <BankDrawer key={sel.bank} bank={sel} overrides={overrides[sel.bank] ?? {}} onClose={() => setSelected(null)}
              onApply={(o) => { const next = { ...overrides, [sel.bank]: o }; if (!Object.keys(o).length) delete next[sel.bank]; setOverrides(next); run(next) }} />}
          </AnimatePresence>
        </div>

        {/* side panel */}
        <Card className="p-0 overflow-hidden flex flex-col max-h-[600px]">
          <div className="flex border-b border-line">
            {([['trips', `Transfers (${plan?.trips.length ?? 0})`, Truck], ['escalate', `Escalations (${plan?.unresolved.length ?? 0})`, Siren]] as const).map(([id, l, Icon]) => (
              <button key={id} onClick={() => setPanel(id)} className={clsx('flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium border-b-2 transition',
                panel === id ? 'border-ours text-ink' : 'border-transparent text-muted hover:text-ink')}><Icon size={15} />{l}</button>
            ))}
          </div>
          <div className="p-3 overflow-y-auto space-y-2.5 flex-1">
            {plan && <p className="text-xs text-muted px-1 pb-1">{plan.summary}</p>}
            {panel === 'trips' && plan?.trips.map((t, i) => <TripCard key={i} t={t} i={i} onFocus={(b) => setSelected(b)} />)}
            {panel === 'trips' && plan && !plan.trips.length && <div className="text-sm text-muted p-4 text-center">No transfers needed this morning.</div>}
            {panel === 'escalate' && plan?.unresolved.map((u, i) => (
              <motion.div key={i} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                className="rounded-xl border border-red-500/25 bg-red-500/[0.06] p-3 text-sm">
                <div className="flex items-center gap-2 font-medium text-red-200"><AlertTriangle size={14} /> {u.bank} · {u.units} × {u.sku}</div>
                <p className="text-xs text-muted mt-1">{u.action}</p>
              </motion.div>
            ))}
            {panel === 'escalate' && plan && !plan.unresolved.length && <div className="text-sm text-muted p-4 text-center">Every shortfall can be covered by moving stock.</div>}
          </div>
        </Card>
      </div>

      {radar && <RadarCard radar={radar} />}
    </div>
  )
}

function Kpi({ label, value, sub, color }: { label: string; value: number; sub: string; color?: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className={clsx('font-display text-2xl font-bold mt-0.5', color)}><AnimatedNumber value={value} duration={0.8} /></div>
      <div className="text-[11px] text-faint mt-0.5">{sub}</div>
    </Card>
  )
}

function TripCard({ t, i, onFocus }: { t: Trip; i: number; onFocus: (b: string) => void }) {
  const [open, setOpen] = useState(i === 0)
  const hasPlt = t.items.some((x) => x.sku === 'PLT')
  return (
    <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
      className={clsx('rounded-xl border p-3', hasPlt ? 'border-rose-400/25 bg-rose-400/[0.04]' : 'border-line bg-surface-2/60')}>
      <button className="w-full text-left" onClick={() => setOpen(!open)}>
        <div className="flex items-center gap-2 text-sm font-semibold">
          <span className="text-faint num w-5">{i + 1}.</span>
          <span className="hover:underline" onClick={(e) => { e.stopPropagation(); onFocus(t.from) }}>{t.from}</span>
          <ArrowRight size={14} className={hasPlt ? 'text-blood-soft' : 'text-ours'} />
          <span className="hover:underline" onClick={(e) => { e.stopPropagation(); onFocus(t.to) }}>{t.to}</span>
          <span className="ml-auto flex items-center gap-1 text-xs font-normal text-muted"><Clock size={12} />{Math.round(t.drive_min)} min · {t.drive_km} km</span>
          <ChevronDown size={15} className={clsx('text-faint transition', open && 'rotate-180')} />
        </div>
        <div className="flex flex-wrap gap-1.5 mt-2 pl-7">
          {t.items.map((x) => (
            <span key={x.sku} className={clsx('rounded-md px-1.5 py-0.5 text-[11px] font-semibold num',
              x.sku === 'PLT' ? 'bg-rose-500/15 text-rose-300' : 'bg-cyan-400/10 text-cyan-200')}>{x.units} × {x.sku}</span>
          ))}
        </div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden pl-7 mt-2 space-y-1">
            {t.reasons.slice(0, 6).map((r, k) => <li key={k} className="text-xs text-muted leading-relaxed">• {r}</li>)}
          </motion.ul>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function BankDrawer({ bank, overrides, onClose, onApply }: { bank: BankStatus; overrides: Record<string, number>; onClose: () => void; onApply: (o: Record<string, number>) => void }) {
  const [edit, setEdit] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(overrides).map(([k, v]) => [k, String(v)])))
  const data = Object.entries(bank.stock_by_sku).map(([sku, n]) => ({ sku, n }))
  const apply = () => {
    const o: Record<string, number> = {}
    for (const [k, v] of Object.entries(edit)) if (v !== '' && !Number.isNaN(+v)) o[k] = Math.max(0, Math.round(+v))
    onApply(o)
  }
  return (
    <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
      className="absolute left-3 top-3 bottom-3 z-[700] w-[min(340px,calc(100%-24px))] rounded-2xl border border-line bg-bg/95 backdrop-blur-xl p-4 overflow-y-auto shadow-2xl">
      <div className="flex items-start gap-2">
        <div className="flex-1">
          <div className="font-display font-semibold leading-tight">{bank.name}</div>
          <div className="text-xs text-muted mt-0.5">{bank.role} · {bank.operator}</div>
        </div>
        <button onClick={onClose} className="text-muted hover:text-ink"><X size={18} /></button>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-3 text-center">
        <Mini label="Red-cell cover" value={`${bank.rbc_days_cover}d`} color={coverColor(bank.rbc_days_cover)} />
        <Mini label="Platelet cover" value={`${bank.plt_days_cover}d`} color={coverColor(bank.plt_days_cover)} />
        <Mini label="At risk" value={String(bank.at_risk_units)} color="#a78bfa" />
      </div>
      <div className="h-40 mt-3">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#262c3b" />
            <XAxis dataKey="sku" tick={{ fill: '#8a93a8', fontSize: 10 }} axisLine={false} tickLine={false} interval={0} />
            <YAxis tick={{ fill: '#5b6378', fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Bar dataKey="n" name="units in stock" fill="#22d3ee" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 rounded-xl border border-line bg-surface p-3">
        <div className="flex items-center gap-2 text-sm font-medium"><PencilLine size={14} className="text-today" /> Type in this bank’s real stock</div>
        <p className="text-[11px] text-muted mt-1">Leave blank to keep the simulated value. RaktSetu re-plans the whole city around your numbers.</p>
        <div className="grid grid-cols-3 gap-2 mt-2">
          {Object.keys(bank.stock_by_sku).map((sku) => (
            <label key={sku} className="text-[11px] text-muted">
              {sku}
              <input inputMode="numeric" className={clsx(inputCls, 'mt-0.5 px-2 py-1 text-xs')} placeholder={String(bank.stock_by_sku[sku])}
                value={edit[sku] ?? ''} onChange={(e) => setEdit({ ...edit, [sku]: e.target.value.replace(/[^0-9]/g, '') })} />
            </label>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <Button onClick={apply} className="flex-1 !py-1.5">Re-plan with these</Button>
          <Button variant="ghost" className="!py-1.5" onClick={() => { setEdit({}); onApply({}) }}>Reset</Button>
        </div>
      </div>
    </motion.div>
  )
}

function Mini({ label, value, color }: { label: string; value: string; color: string }) {
  return <div className="rounded-lg bg-surface border border-line py-2"><div className="font-display font-bold" style={{ color }}>{value}</div><div className="text-[10px] text-faint">{label}</div></div>
}

function RadarCard({ radar }: { radar: Radar }) {
  const tone = radar.level === 'alert' ? 'bad' : radar.level === 'watch' ? 'warn' : 'good'
  const data = [
    { name: 'Last 7 days', v: radar.current_demand_per_day, err: [0, 0] as [number, number], now: true },
    ...radar.weeks.map((w) => ({ name: `Wk of ${w.starts.slice(5)}`, v: w.expected_per_day, err: [w.expected_per_day - w.low, w.high - w.expected_per_day] as [number, number], now: false })),
  ]
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1 min-w-[260px]">
          <div className="flex items-center gap-2">
            <div className="text-[11px] uppercase tracking-[0.16em] text-blood-soft font-semibold">Platelet surge radar · city-wide</div>
            <Badge tone={tone}>{radar.level.toUpperCase()}</Badge>
          </div>
          <h3 className="font-display text-lg font-semibold mt-1">Will Jaipur have enough platelets in the next 4 weeks?</h3>
          <p className="text-sm text-ink/85 mt-2">{radar.action}</p>
          <p className="text-xs text-muted mt-2">Why: {radar.driver} Rainfall leads dengue by ~8 weeks (pan-India study), which gives time to organise donors.</p>
        </div>
        <div className="w-full md:w-[460px] h-56">
          <ResponsiveContainer>
            <ComposedChart data={data} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#262c3b" />
              <XAxis dataKey="name" tick={{ fill: '#8a93a8', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5b6378', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tipStyle} formatter={(v) => `${Number(v).toFixed(0)} / day`} />
              <ReferenceLine y={radar.current_production_per_day} stroke="#34d399" strokeDasharray="5 5" label={{ value: `production ~${fmtInt(radar.current_production_per_day)}/day`, fill: '#34d399', fontSize: 10, position: 'insideTopLeft' }} />
              <Bar dataKey="v" name="platelet requests" fill="#fb7185" radius={[6, 6, 0, 0]} animationDuration={900}>
                <ErrorBar dataKey="err" stroke="#e9ecf3" strokeOpacity={0.5} width={6} />
                {data.map((d, i) => <Cell key={i} fill={d.now ? '#5b6378' : d.v > radar.current_production_per_day ? '#ef4444' : '#fb7185'} />)}
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  )
}
