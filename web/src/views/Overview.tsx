import { motion } from 'framer-motion'
import { ArrowRight, Brain, CloudRain, Map as MapIcon, MessageSquareText, Route, ShieldCheck, Truck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtInt, POLICY_META, type Meta, type Plan, type PolicyKey, type SimResult } from '../api'
import type { Go } from '../App'
import { NetworkMap, type MapArc, type MapBank } from '../components/NetworkMap'
import { AnimatedNumber, Badge, Button, Card, coverColor, SectionTitle, Source, Spinner } from '../components/ui'

const EVIDENCE = [
  { value: 28, suffix: ' lakh', label: 'units of blood and components discarded by Indian blood banks, 2012–2016', src: 'NACO data via RTI (Business Insider, 2017)', href: 'https://www.businessinsider.in/india-lost-6-lakh-litres-of-blood-in-five-years/articleshow/58338754.cms' },
  { value: 15, prefix: '5–', suffix: '%', label: 'of collected units are wasted: expiry, breakage, poor component management', src: 'ORF, Oct 2025', href: 'https://www.orfonline.org/expert-speak/securing-india-s-lifeblood-for-a-reliable-national-blood-supply' },
  { value: 146, suffix: ' lakh', label: 'units collected in 2024–25, roughly the national requirement. The gap is distribution, not supply.', src: 'ORF, Oct 2025', href: 'https://www.orfonline.org/expert-speak/securing-india-s-lifeblood-for-a-reliable-national-blood-supply' },
  { value: 60, prefix: '15/mo → ', suffix: '/day', label: 'platelet requests at one Jaipur blood bank during an October dengue surge', src: 'LivLong Health Story', href: 'https://healthstory.livlong.com/news/increase-in-dengue-cases-leads-to-rising-demand-for-platelets' },
  { value: 22, suffix: '%', label: 'of blood banks in 8 states incl. Rajasthan rarely or never update e-RaktKosh stock', src: 'BMJ Global Health, Oct 2024 (via ORF)', href: 'https://doaj.org/article/99ff305cac114d16a01b74de21e909c0' },
  { value: 5, suffix: ' days', label: 'shelf life of a platelet unit. Red cells last 35. A unit in the wrong bank is a unit lost.', src: 'Standard storage limits', href: 'https://www.orfonline.org/expert-speak/securing-india-s-lifeblood-for-a-reliable-national-blood-supply' },
]

const STEPS = [
  { icon: CloudRain, title: 'Sense', text: 'Real Jaipur rainfall and temperature, each bank’s stock by blood group and age, recent requests.' },
  { icon: Brain, title: 'Forecast', text: 'Gradient-boosted model per bank and product, 1–5 days ahead. A surge radar warns 2–4 weeks before the dengue peak.' },
  { icon: Route, title: 'Optimise', text: 'An OR-Tools integer programme picks the van trips that avert the most shortages and expiries within the vans you have.' },
  { icon: MessageSquareText, title: 'Explain', text: 'Every trip comes with its reasons. Shortfalls no van can fix are escalated: call donors, book apheresis.' },
]

export default function Overview({ meta, go }: { meta: Meta; go: Go }) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [sim, setSim] = useState<SimResult | null>(null)
  useEffect(() => {
    api.plan({ date: meta.dates.today }).then(setPlan).catch(() => {})
    api.simulate({ start: '2024-08-15', end: '2024-11-30' }).then(setSim).catch(() => {})
  }, [meta.dates.today])

  const mapBanks: MapBank[] = useMemo(() => (plan?.banks ?? []).map((b) => ({
    short: b.bank, name: b.name, lat: b.lat, lon: b.lon, color: coverColor(b.min_cover_days),
    size: 12 + Math.sqrt(b.rbc_stock + 4 * b.plt_stock) / 2.2, pulse: b.min_cover_days < 1,
    tooltip: `<b>${b.name}</b><br/>Red cells ${b.rbc_stock} · Platelets ${b.plt_stock}`,
  })), [plan])
  const arcs: MapArc[] = useMemo(() => {
    if (!plan) return []
    const pos = Object.fromEntries(plan.banks.map((b) => [b.bank, [b.lat, b.lon] as [number, number]]))
    return plan.trips.map((t, i) => ({ key: `${t.from}-${t.to}-${i}`, from: pos[t.from], to: pos[t.to], units: t.units, color: '#22d3ee' }))
  }, [plan])

  return (
    <div className="space-y-14">
      {/* HERO */}
      <section className="grid lg:grid-cols-[1.05fr_1fr] gap-8 items-center">
        <div>
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap gap-2 mb-5">
            <Badge tone="bad">Dengue season · Jaipur</Badge>
            <Badge tone="ours">18 real blood banks</Badge>
            <Badge>Open source · MIT</Badge>
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="font-display text-4xl sm:text-5xl font-bold leading-[1.05] tracking-tight">
            India collects enough blood.<br />
            <span className="bg-gradient-to-r from-blood-soft via-blood to-rose-500 bg-clip-text text-transparent">It just isn’t in the right bank on the right day.</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="mt-5 text-muted text-base sm:text-lg max-w-xl">
            RaktSetu forecasts requests at each of Jaipur’s blood banks and, every morning, tells the district coordinator which units to move where:
            <span className="text-ink"> before a patient is turned away, and before a unit expires on a shelf.</span>
          </motion.p>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="mt-7 flex flex-wrap gap-3">
            <Button onClick={() => go('control')}>Open today’s plan <ArrowRight size={16} /></Button>
            <Button variant="ghost" onClick={() => go('lab')}>Run a crisis scenario</Button>
          </motion.div>
          <div className="mt-8 rounded-2xl border border-line bg-surface/70 p-4 text-sm">
            <div className="text-[11px] uppercase tracking-[0.16em] text-faint mb-1.5">The problem, in one sentence</div>
            <p className="text-ink/90 leading-relaxed">
              <b>Blood-bank coordinators in Jaipur</b> cannot move stock to where it will be needed <b>before</b> it runs out or expires,
              <b> because</b> each bank plans alone and e-RaktKosh only shows today’s stock, <b>which causes</b> platelet shortages in dengue season
              while red cells and platelets are discarded unused a few kilometres away.
            </p>
          </div>
        </div>
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 }} className="relative">
          {plan ? (
            <>
              <NetworkMap banks={mapBanks} arcs={arcs} height={460} showLabels={false} />
              <div className="absolute left-3 bottom-3 right-3 sm:right-auto z-[500] rounded-xl bg-bg/85 backdrop-blur border border-line px-3 py-2 text-xs">
                <div className="text-faint">This morning ({plan.date})</div>
                <div className="text-ink font-medium"><span className="text-ours">{plan.totals.trips} van trips</span> · {fmtInt(plan.totals.units)} units · {plan.totals.km} km</div>
              </div>
            </>
          ) : <Card className="h-[460px] grid place-items-center"><Spinner label="Planning this morning’s transfers…" /></Card>}
        </motion.div>
      </section>

      {/* EVIDENCE */}
      <section>
        <SectionTitle eyebrow="Why it matters" title="The evidence" sub="Every number links to its source. We used these to size the problem, not as proof of our results." />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {EVIDENCE.map((e, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
              <Card className="p-5 h-full flex flex-col">
                <div className="font-display text-3xl font-bold text-blood-soft">
                  {e.prefix}<AnimatedNumber value={e.value} />{e.suffix}
                </div>
                <p className="text-sm text-ink/85 mt-2 flex-1">{e.label}</p>
                <div className="mt-3"><Source href={e.href}>{e.src}</Source></div>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section>
        <SectionTitle eyebrow="How it works" title="From rainfall to a van leaving the depot"
          sub="e-RaktKosh shows stock. RaktSetu says what to do about it, and why." />
        <div className="grid md:grid-cols-4 gap-4">
          {STEPS.map((s, i) => (
            <motion.div key={s.title} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}>
              <Card className="p-5 h-full relative overflow-hidden">
                <div className="absolute -right-3 -top-4 font-display text-7xl font-bold text-white/[0.03]">{i + 1}</div>
                <div className="h-10 w-10 rounded-xl bg-surface-3 border border-line grid place-items-center mb-3"><s.icon size={19} className="text-ours" /></div>
                <div className="font-display font-semibold">{s.title}</div>
                <p className="text-sm text-muted mt-1.5">{s.text}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* RESULT */}
      <section>
        <SectionTitle eyebrow="Result (simulation)" title="The 2024 dengue season, replayed three ways"
          sub="Same requests, same donations, same roads. Only the coordination changes. One seed shown here; the Evidence tab has the 5-seed mean, the sensitivity analysis and the limits." />
        {sim ? <ResultBars sim={sim} /> : <Card className="p-6"><Spinner label="Simulating 108 days for 18 banks under 3 policies…" /></Card>}
      </section>

      {/* HONESTY */}
      <section className="grid md:grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="flex items-center gap-2 font-display font-semibold mb-3"><MapIcon size={17} className="text-ok" /> Real inputs</div>
          <ul className="text-sm text-muted space-y-1.5 list-disc pl-5">
            <li>18 blood banks and their locations: OpenStreetMap</li>
            <li>Road travel times between every pair: OSRM on OSM roads</li>
            <li>Daily Jaipur rain, temperature, humidity 2016–2026: Open-Meteo (ERA5)</li>
            <li>Rajasthan dengue cases per year: NCVBDC / Parliament answers</li>
            <li>Blood-group mix: national multicentre study, 10,000 donors</li>
          </ul>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 font-display font-semibold mb-3"><ShieldCheck size={17} className="text-today" /> Generated (and said so)</div>
          <ul className="text-sm text-muted space-y-1.5 list-disc pl-5">
            <li>Daily requests and donations per bank. Real data is not public. Seeded, with every assumption listed</li>
            <li>Bank size and role profiles: our guesses from hospital type</li>
            <li>Results show the method works under stated assumptions. They are <b className="text-ink">not</b> a measured real-world outcome</li>
            <li>Next step: pilot with real stock from e-RaktKosh and one district coordinator</li>
          </ul>
        </Card>
      </section>
    </div>
  )
}

function ResultBars({ sim }: { sim: SimResult }) {
  const order: PolicyKey[] = ['isolated', 'reactive', 'raktsetu']
  const rows = order.map((p) => ({ p, name: POLICY_META[p].short, color: POLICY_META[p].color, ...sim.policies[p].kpis }))
  const base = sim.policies.reactive.kpis
  const ours = sim.policies.raktsetu.kpis
  const lessUnmet = 1 - ours.total_unmet / Math.max(1, base.total_unmet)
  const lessWaste = 1 - ours.total_expired / Math.max(1, base.total_expired)
  return (
    <div className="grid lg:grid-cols-[1fr_1fr_0.8fr] gap-4">
      {([['total_unmet', 'Requests that could not be met', '#ef4444'], ['total_expired', 'Units that expired unused', '#a78bfa']] as const).map(([k, title]) => (
        <Card key={k} className="p-5">
          <div className="text-sm text-muted mb-2">{title}</div>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={rows} margin={{ top: 22, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#262c3b" />
                <XAxis dataKey="name" tick={{ fill: '#8a93a8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#5b6378', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} contentStyle={{ background: '#171b24', border: '1px solid #262c3b', borderRadius: 10 }} formatter={(v) => fmtInt(Number(v))} />
                <Bar dataKey={k} radius={[8, 8, 0, 0]} animationDuration={1200}>
                  {rows.map((r) => <Cell key={r.p} fill={r.color} />)}
                  <LabelList dataKey={k} position="top" formatter={(v: unknown) => fmtInt(Number(v))} style={{ fill: '#e9ecf3', fontSize: 12, fontWeight: 600 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      ))}
      <Card className="p-5 flex flex-col justify-center gap-5">
        <div>
          <div className="font-display text-5xl font-bold text-ours"><AnimatedNumber value={100 * lessUnmet} format={(v) => `${v.toFixed(0)}%`} /></div>
          <div className="text-sm text-muted">fewer unmet requests than today’s phone-around</div>
        </div>
        <div>
          <div className="font-display text-5xl font-bold text-waste"><AnimatedNumber value={100 * lessWaste} format={(v) => `${v.toFixed(0)}%`} /></div>
          <div className="text-sm text-muted">fewer units expiring unused</div>
        </div>
        <div className="text-xs text-faint flex items-start gap-2"><Truck size={14} className="mt-0.5 shrink-0" />
          Cost: {fmtInt(ours.total_km - base.total_km)} more van-km over the season ({fmtInt(ours.total_trips)} vs {fmtInt(base.total_trips)} trips). We report it, not hide it.</div>
      </Card>
    </div>
  )
}
