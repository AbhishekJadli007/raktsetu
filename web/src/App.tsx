import { AnimatePresence, motion } from 'framer-motion'
import { Activity, FlaskConical, GitBranch, LayoutDashboard, Microscope } from 'lucide-react'
import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { api, type Meta } from './api'
import { ErrorNote, Spinner } from './components/ui'
import ControlRoom from './views/ControlRoom'
import Evidence from './views/Evidence'
import Overview from './views/Overview'
import SimLab from './views/SimLab'

const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'control', label: 'Control Room', icon: LayoutDashboard },
  { id: 'lab', label: 'Simulation Lab', icon: FlaskConical },
  { id: 'evidence', label: 'Evidence & Method', icon: Microscope },
] as const
type TabId = (typeof TABS)[number]['id']

const REPO_URL = 'https://github.com/AbhishekJadli007/raktsetu'

function useHashTab(): [TabId, (t: TabId) => void] {
  const read = () => (TABS.find((t) => `#${t.id}` === window.location.hash)?.id ?? 'overview') as TabId
  const [tab, setTab] = useState<TabId>(read)
  useEffect(() => {
    const on = () => setTab(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [tab, (t) => { window.location.hash = t; window.scrollTo({ top: 0, behavior: 'smooth' }) }]
}

export default function App() {
  const [tab, go] = useHashTab()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api.meta().then(setMeta).catch((e) => setErr(String(e.message ?? e))) }, [])

  return (
    <div className="min-h-full page-glow">
      <header className="sticky top-0 z-[1000] border-b border-line/80 bg-bg/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center gap-4">
          <button onClick={() => go('overview')} className="flex items-center gap-2.5 shrink-0">
            <Logo />
            <div className="text-left leading-tight">
              <div className="font-display font-bold text-lg tracking-tight">RaktSetu</div>
              <div className="text-[10px] text-muted -mt-0.5">रक्त सेतु · a bridge for blood</div>
            </div>
          </button>
          <nav className="flex-1 flex justify-center overflow-x-auto">
            <div className="flex gap-1 rounded-2xl bg-surface/80 border border-line p-1">
              {TABS.map((t) => (
                <button key={t.id} onClick={() => go(t.id)}
                  className={clsx('relative flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
                    tab === t.id ? 'text-ink' : 'text-muted hover:text-ink')}>
                  {tab === t.id && <motion.div layoutId="tab-pill" className="absolute inset-0 rounded-xl bg-surface-3 border border-line" transition={{ type: 'spring', stiffness: 400, damping: 32 }} />}
                  <t.icon size={15} className="relative" />
                  <span className="relative hidden sm:inline">{t.label}</span>
                </button>
              ))}
            </div>
          </nav>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="hidden md:flex items-center gap-1.5 text-xs text-muted hover:text-ink shrink-0">
            <GitBranch size={16} /> Open source · MIT
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6 sm:py-8">
        {err && <ErrorNote error={`Cannot reach the RaktSetu API: ${err}. Start it with: uvicorn api.main:app --port 8000`} />}
        {!meta && !err && <Spinner label="Loading the Jaipur network…" />}
        {meta && (
          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.25 }}>
              {tab === 'overview' && <Overview meta={meta} go={go} />}
              {tab === 'control' && <ControlRoom meta={meta} />}
              {tab === 'lab' && <SimLab meta={meta} />}
              {tab === 'evidence' && <Evidence meta={meta} />}
            </motion.div>
          </AnimatePresence>
        )}
      </main>

      <footer className="border-t border-line/70 mt-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-6 text-xs text-faint flex flex-wrap gap-x-6 gap-y-2 justify-between">
          <span>Simulated on real structure: OpenStreetMap blood-bank locations, OSRM road times, Open-Meteo weather, NCVBDC dengue counts. Demand and donations are generated (seeded). Not a medical device.</span>
          <span>Built for COMMIT FOR GOOD · AI × Open Source × Public Good</span>
        </div>
      </footer>
    </div>
  )
}

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden>
      <defs>
        <linearGradient id="lg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#fb7185" /><stop offset="1" stopColor="#be123c" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="#11141b" stroke="#262c3b" />
      <path d="M32 10c0 0-14 17-14 27a14 14 0 0 0 28 0c0-10-14-27-14-27z" fill="url(#lg)" />
      <path d="M21 41c4-5 18-5 22 0" stroke="#22d3ee" strokeWidth="3.5" fill="none" strokeLinecap="round" />
    </svg>
  )
}

export type Go = (t: TabId) => void
