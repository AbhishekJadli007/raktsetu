import { motion } from 'framer-motion'
import { Pause, Play, Plus, Trash2, Wand2, Zap } from 'lucide-react'
import clsx from 'clsx'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtInt, fmtPct, POLICY_META, type Meta, type PolicyKey, type ScenarioIn, type SimResult } from '../api'
import { NetworkMap, type MapArc, type MapBank } from '../components/NetworkMap'
import { AnimatedNumber, Badge, Button, Card, coverColor, Delta, ErrorNote, Field, inputCls, SectionTitle, Spinner } from '../components/ui'

type Form = {
  start: string; end: string; dengue_scale: number; donation_change: number; vans: number; seed: number
  separator: { on: boolean; bank: string; start: string; end: string }
  halt: { on: boolean; bank: string; start: string; end: string }
  surge: { on: boolean; bank: string; date: string; units: number }
}

const BASE: Form = {
  start: '2024-08-15', end: '2024-11-30', dengue_scale: 1, donation_change: 0, vans: 2, seed: 42,
  separator: { on: false, bank: 'BMCHRC', start: '2024-09-01', end: '2024-10-15' },
  halt: { on: false, bank: 'SKBB', start: '2024-09-10', end: '2024-09-30' },
  surge: { on: false, bank: 'SMS', date: '2024-09-20', units: 120 },
}

const PRESETS: { name: string; desc: string; f: (b: Form) => Form }[] = [
  { name: '2024 dengue season', desc: 'The real 2024 season (12,514 cases in Rajasthan).', f: (b) => b },
  { name: 'Severe season, 2021-like', desc: 'Dengue 1.7× worse, like 2021 (20,749 cases).', f: (b) => ({ ...b, dengue_scale: 1.7 }) },
  { name: 'Platelet machine breaks', desc: 'Cancer hospital’s separator fails for 6 weeks at the peak.', f: (b) => ({ ...b, separator: { ...b.separator, on: true } }) },
  { name: 'Mass-casualty event', desc: 'Bus accident: 120 extra red-cell units at SMS in one day.', f: (b) => ({ ...b, surge: { ...b.surge, on: true } }) },
  { name: 'Summer donor drought', desc: 'Apr–Jul 2025, walk-in donations fall 35%.', f: (b) => ({ ...b, start: '2025-04-01', end: '2025-07-31', donation_change: -0.35 }) },
  { name: 'Everything at once', desc: 'Severe dengue + machine failure + accident + one van.', f: (b) => ({ ...b, dengue_scale: 1.7, vans: 1, separator: { ...b.separator, on: true }, surge: { ...b.surge, on: true } }) },
]

function toScenario(f: Form): ScenarioIn {
  return {
    seed: f.seed, dengue_scale: f.dengue_scale, donation_change: f.donation_change, vans: f.vans,
    separator_failure: f.separator.on ? [{ bank: f.separator.bank, start: f.separator.start, end: f.separator.end }] : [],
    collection_halt: f.halt.on ? [{ bank: f.halt.bank, start: f.halt.start, end: f.halt.end }] : [],
    surge: f.surge.on ? [{ bank: f.surge.bank, date: f.surge.date, units: f.surge.units }] : [],
  }
}

export default function SimLab({ meta }: { meta: Meta }) {
  const [form, setForm] = useState<Form>(BASE)
  const [preset, setPreset] = useState(0)
  const [sim, setSim] = useState<SimResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)

  const run = (f: Form = form) => {
    setLoading(true); setErr(null)
    const t0 = Date.now()
    const timer = setInterval(() => setElapsed((Date.now() - t0) / 1000), 200)
    api.simulate({ start: f.start, end: f.end, scenario: toScenario(f) })
      .then(setSim).catch((e) => setErr(String(e.message ?? e)))
      .finally(() => { clearInterval(timer); setLoading(false) })
  }
  useEffect(() => { run(BASE) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }))
  const banks = meta.banks.map((b) => b.short)
  const days = Math.round((+new Date(form.end) - +new Date(form.start)) / 864e5) + 1

  return (
    <div className="space-y-6">
      <SectionTitle eyebrow="Simulation lab" title="Break the network. See who copes."
        sub="Pick a crisis or build your own. The same requests and donations are replayed under three policies, so the only difference is how banks coordinate." />

      <div className="grid xl:grid-cols-[360px_1fr] gap-5 items-start">
        {/* builder */}
        <Card className="p-4 space-y-4 xl:sticky xl:top-20">
          <div>
            <div className="text-xs font-medium text-muted mb-2 flex items-center gap-1.5"><Wand2 size={13} /> Presets</div>
            <div className="grid grid-cols-2 gap-1.5">
              {PRESETS.map((p, i) => (
                <button key={p.name} title={p.desc} onClick={() => { const f = p.f(BASE); setPreset(i); setForm(f); run(f) }}
                  className={clsx('rounded-lg border px-2 py-1.5 text-left text-[11px] leading-tight transition',
                    preset === i ? 'border-ours/60 bg-ours/10 text-ink' : 'border-line bg-surface-2 text-muted hover:text-ink')}>{p.name}</button>
              ))}
            </div>
            <p className="text-[11px] text-faint mt-2">{PRESETS[preset].desc}</p>
          </div>
          <div className="h-px bg-line" />
          <div className="grid grid-cols-2 gap-2">
            <Field label="From"><input type="date" className={inputCls} value={form.start} min={meta.dates.first} max={meta.dates.last} onChange={(e) => set({ start: e.target.value })} /></Field>
            <Field label="To"><input type="date" className={inputCls} value={form.end} min={meta.dates.first} max={meta.dates.last} onChange={(e) => set({ end: e.target.value })} /></Field>
          </div>
          <div className={clsx('text-[11px]', days > 200 || days < 7 ? 'text-red-300' : 'text-faint')}>{days} days (7–200 allowed)</div>
          <Field label="Dengue severity" hint={`${form.dengue_scale.toFixed(1)}× the real year`}>
            <input type="range" min={0} max={3} step={0.1} value={form.dengue_scale} onChange={(e) => set({ dengue_scale: +e.target.value })} className="w-full" /></Field>
          <Field label="Walk-in donations" hint={`${form.donation_change >= 0 ? '+' : ''}${Math.round(form.donation_change * 100)}%`}>
            <input type="range" min={-0.6} max={0.3} step={0.05} value={form.donation_change} onChange={(e) => set({ donation_change: +e.target.value })} className="w-full" /></Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Vans" hint={form.vans}><input type="range" min={0} max={6} value={form.vans} onChange={(e) => set({ vans: +e.target.value })} className="w-full" /></Field>
            <Field label="Random seed"><input type="number" className={inputCls} value={form.seed} onChange={(e) => set({ seed: Math.max(0, Math.round(+e.target.value)) })} /></Field>
          </div>

          <Event title="Platelet separator failure" on={form.separator.on} toggle={() => set({ separator: { ...form.separator, on: !form.separator.on } })}>
            <BankSelect banks={banks} value={form.separator.bank} onChange={(bank) => set({ separator: { ...form.separator, bank } })} />
            <div className="grid grid-cols-2 gap-2">
              <input type="date" className={inputCls} value={form.separator.start} onChange={(e) => set({ separator: { ...form.separator, start: e.target.value } })} />
              <input type="date" className={inputCls} value={form.separator.end} onChange={(e) => set({ separator: { ...form.separator, end: e.target.value } })} />
            </div>
          </Event>
          <Event title="Bank stops collecting" on={form.halt.on} toggle={() => set({ halt: { ...form.halt, on: !form.halt.on } })}>
            <BankSelect banks={banks} value={form.halt.bank} onChange={(bank) => set({ halt: { ...form.halt, bank } })} />
            <div className="grid grid-cols-2 gap-2">
              <input type="date" className={inputCls} value={form.halt.start} onChange={(e) => set({ halt: { ...form.halt, start: e.target.value } })} />
              <input type="date" className={inputCls} value={form.halt.end} onChange={(e) => set({ halt: { ...form.halt, end: e.target.value } })} />
            </div>
          </Event>
          <Event title="Mass-casualty event" on={form.surge.on} toggle={() => set({ surge: { ...form.surge, on: !form.surge.on } })}>
            <BankSelect banks={banks} value={form.surge.bank} onChange={(bank) => set({ surge: { ...form.surge, bank } })} />
            <div className="grid grid-cols-2 gap-2">
              <input type="date" className={inputCls} value={form.surge.date} onChange={(e) => set({ surge: { ...form.surge, date: e.target.value } })} />
              <input type="number" className={inputCls} value={form.surge.units} min={1} max={500} onChange={(e) => set({ surge: { ...form.surge, units: Math.max(1, +e.target.value) } })} />
            </div>
          </Event>

          <Button variant="blood" className="w-full" onClick={() => run()} disabled={loading || days > 200 || days < 7}>
            <Zap size={15} /> {loading ? `Simulating… ${elapsed.toFixed(0)}s` : 'Run simulation'}
          </Button>
        </Card>

        {/* results */}
        <div className="space-y-5 min-w-0">
          {err && <ErrorNote error={err} />}
          {loading && !sim && <Card className="p-8"><Spinner label={`Solving ${days} daily plans for 18 banks… ${elapsed.toFixed(0)}s`} /></Card>}
          {sim && (
            <div className={clsx('space-y-5 transition-opacity', loading && 'opacity-50')}>
              <KpiCompare sim={sim} />
              <Playback sim={sim} meta={meta} />
              <Timeline sim={sim} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Event({ title, on, toggle, children }: { title: string; on: boolean; toggle: () => void; children: React.ReactNode }) {
  return (
    <div className={clsx('rounded-xl border p-2.5 transition', on ? 'border-blood/40 bg-blood/[0.05]' : 'border-line')}>
      <button onClick={toggle} className="w-full flex items-center justify-between text-xs font-medium">
        <span className={on ? 'text-ink' : 'text-muted'}>{title}</span>
        {on ? <Trash2 size={13} className="text-blood-soft" /> : <Plus size={13} className="text-muted" />}
      </button>
      {on && <div className="mt-2 space-y-2">{children}</div>}
    </div>
  )
}

function BankSelect({ banks, value, onChange }: { banks: string[]; value: string; onChange: (b: string) => void }) {
  return <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value)}>{banks.map((b) => <option key={b}>{b}</option>)}</select>
}

const ORDER: PolicyKey[] = ['isolated', 'reactive', 'raktsetu']

function KpiCompare({ sim }: { sim: SimResult }) {
  const base = sim.policies.reactive.kpis
  const rows: { k: keyof SimResult['policies']['raktsetu']['kpis']; label: string; pct?: boolean; better: 'lower' | 'higher' }[] = [
    { k: 'total_unmet', label: 'Unmet requests', better: 'lower' },
    { k: 'total_expired', label: 'Expired units', better: 'lower' },
    { k: 'plt_fill_rate', label: 'Platelet fill rate', pct: true, better: 'higher' },
    { k: 'rbc_fill_rate', label: 'Red-cell fill rate', pct: true, better: 'higher' },
    { k: 'total_trips', label: 'Van trips', better: 'lower' },
    { k: 'total_km', label: 'Van-km', better: 'lower' },
  ]
  return (
    <div className="grid md:grid-cols-3 gap-3">
      {ORDER.map((p, i) => {
        const k = sim.policies[p].kpis
        return (
          <motion.div key={p} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
            <Card className={clsx('p-4 h-full', p === 'raktsetu' && 'ring-1 ring-ours/40 shadow-[0_0_40px_rgba(34,211,238,0.08)]')}>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: POLICY_META[p].color }} />
                <div className="font-display font-semibold">{POLICY_META[p].label}</div>
              </div>
              <p className="text-[11px] text-faint mt-0.5 mb-3">{POLICY_META[p].blurb}</p>
              <div className="space-y-2">
                {rows.map((r) => (
                  <div key={r.k} className="flex items-center justify-between gap-2 text-sm">
                    <span className="text-muted">{r.label}</span>
                    <span className="flex items-center gap-2">
                      {p !== 'reactive' && <Delta base={base[r.k] as number} value={k[r.k] as number} better={r.better} />}
                      <AnimatedNumber value={k[r.k] as number} format={r.pct ? (v) => fmtPct(v) : fmtInt} className="font-semibold text-ink w-16 text-right" />
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>
        )
      })}
    </div>
  )
}

function Playback({ sim, meta }: { sim: SimResult; meta: Meta }) {
  const n = sim.dates.length
  const [day, setDay] = useState(0)
  const [playing, setPlaying] = useState(false)
  const timer = useRef<number | null>(null)
  useEffect(() => { setDay(0); setPlaying(false) }, [sim])
  useEffect(() => {
    if (!playing) return
    timer.current = window.setInterval(() => setDay((d) => (d + 1 >= n ? (setPlaying(false), d) : d + 1)), 220)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [playing, n])

  const pos = useMemo(() => Object.fromEntries(meta.banks.map((b) => [b.short, b])), [meta.banks])
  const view = (p: PolicyKey) => {
    const run = sim.policies[p]
    const bd = run.bank_days[day]
    const banks: MapBank[] = sim.banks.map((s, b) => {
      const [rbc, plt, unmet] = bd[b]
      const [mr, mp] = sim.bank_mean_demand[b]
      const cover = Math.min(rbc / Math.max(mr, 0.1), plt / Math.max(mp, 0.1))
      return {
        short: s, name: pos[s].name, lat: pos[s].lat, lon: pos[s].lon, color: unmet > 0 ? '#ef4444' : coverColor(cover),
        size: 10 + Math.sqrt(rbc + 4 * plt) / 2.4, pulse: unmet > 0,
        tooltip: `<b>${pos[s].name}</b><br/>Red cells ${rbc} · Platelets ${plt}${unmet ? `<br/><span style="color:#ef4444">${unmet} requests unmet today</span>` : ''}`,
      }
    })
    const arcs: MapArc[] = run.transfers[day].map(([s, d, u, kind], i) => ({
      key: `${p}-${day}-${i}`, from: [pos[sim.banks[s]].lat, pos[sim.banks[s]].lon], to: [pos[sim.banks[d]].lat, pos[sim.banks[d]].lon],
      units: u, color: kind === 'planned' ? '#22d3ee' : '#f59e0b', slow: kind === 'emergency',
    }))
    const cum = (k: 'unmet_rbc' | 'unmet_plt' | 'expired_rbc' | 'expired_plt') => run.daily[k].slice(0, day + 1).reduce((a, b) => a + b, 0)
    return { banks, arcs, unmet: cum('unmet_rbc') + cum('unmet_plt'), expired: cum('expired_rbc') + cum('expired_plt') }
  }
  const today = view('reactive')
  const ours = view('raktsetu')

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <div className="font-display font-semibold">Day-by-day replay</div>
        <Badge>{sim.dates[day]}</Badge>
        <div className="ml-auto flex items-center gap-3 text-[11px] text-muted">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-ours" /> planned transfer</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-today" /> emergency call</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-short" /> turned patients away</span>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {([['reactive', today], ['raktsetu', ours]] as const).map(([p, v]) => (
          <div key={p} className="relative">
            <NetworkMap banks={v.banks} arcs={v.arcs} height={360} showLabels={false} />
            <div className="absolute top-2 left-2 z-[500] rounded-xl bg-bg/85 backdrop-blur border border-line px-3 py-2">
              <div className="text-xs font-semibold" style={{ color: POLICY_META[p].color }}>{POLICY_META[p].label}</div>
              <div className="text-[11px] text-muted num">unmet so far <b className="text-red-300">{fmtInt(v.unmet)}</b> · expired <b className="text-violet-300">{fmtInt(v.expired)}</b></div>
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3 mt-3">
        <Button variant="ghost" className="!px-3" onClick={() => { if (day >= n - 1) setDay(0); setPlaying(!playing) }}>{playing ? <Pause size={15} /> : <Play size={15} />}</Button>
        <input type="range" min={0} max={n - 1} value={day} onChange={(e) => { setPlaying(false); setDay(+e.target.value) }} className="flex-1" />
        <span className="text-xs text-muted num w-20 text-right">day {day + 1}/{n}</span>
      </div>
    </Card>
  )
}

function Timeline({ sim }: { sim: SimResult }) {
  const data = sim.dates.map((d, i) => {
    const row: Record<string, number | string> = { d: d.slice(5) }
    for (const p of ORDER) {
      const r = sim.policies[p].daily
      row[`u_${p}`] = r.unmet_rbc[i] + r.unmet_plt[i]
      row[`e_${p}`] = r.expired_rbc[i] + r.expired_plt[i]
    }
    row.demand = sim.policies.reactive.daily.demand_plt[i]
    return row
  })
  const tip = { background: '#171b24', border: '1px solid #262c3b', borderRadius: 10, fontSize: 12 }
  return (
    <div className="grid lg:grid-cols-2 gap-4">
      {([['u', 'Requests turned away per day'], ['e', 'Units expiring per day']] as const).map(([k, title]) => (
        <Card key={k} className="p-4">
          <div className="text-sm text-muted mb-2">{title}</div>
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={data} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#262c3b" />
                <XAxis dataKey="d" tick={{ fill: '#5b6378', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={24} />
                <YAxis tick={{ fill: '#5b6378', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tip} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {ORDER.map((p) => <Line key={p} type="monotone" dataKey={`${k}_${p}`} name={POLICY_META[p].short} stroke={POLICY_META[p].color} strokeWidth={p === 'raktsetu' ? 2.4 : 1.6} dot={false} animationDuration={1200} />)}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      ))}
      <Card className="p-4 lg:col-span-2">
        <div className="text-sm text-muted mb-2">City-wide platelet requests in this scenario</div>
        <div className="h-40">
          <ResponsiveContainer>
            <AreaChart data={data} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
              <defs><linearGradient id="pd" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#fb7185" stopOpacity={0.5} /><stop offset="1" stopColor="#fb7185" stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid vertical={false} stroke="#262c3b" />
              <XAxis dataKey="d" tick={{ fill: '#5b6378', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={24} />
              <YAxis tick={{ fill: '#5b6378', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} />
              <Area type="monotone" dataKey="demand" name="platelet requests" stroke="#fb7185" fill="url(#pd)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  )
}
