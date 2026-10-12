import { animate, motion, useInView, useMotionValue, useTransform } from 'framer-motion'
import clsx from 'clsx'
import { useEffect, useRef, type ReactNode } from 'react'

export function Card({ children, className, ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('card', className)} {...rest}>{children}</div>
}

export function SectionTitle({ eyebrow, title, sub, right }: { eyebrow?: string; title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div>
        {eyebrow && <div className="text-[11px] uppercase tracking-[0.18em] text-blood-soft font-semibold mb-1">{eyebrow}</div>}
        <h2 className="font-display text-xl sm:text-2xl font-semibold text-ink">{title}</h2>
        {sub && <p className="text-sm text-muted mt-1 max-w-3xl">{sub}</p>}
      </div>
      {right}
    </div>
  )
}

/** Number that counts up when it scrolls into view and re-animates on change. */
export function AnimatedNumber({ value, format = (v) => Math.round(v).toLocaleString('en-IN'), duration = 1.1, className }:
  { value: number; format?: (v: number) => string; duration?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const mv = useMotionValue(0)
  const text = useTransform(mv, (v) => format(v))
  useEffect(() => {
    if (!inView) return
    const c = animate(mv, value, { duration, ease: [0.16, 1, 0.3, 1] })
    return () => c.stop()
  }, [value, inView, duration, mv])
  return <motion.span ref={ref} className={clsx('num', className)}>{text}</motion.span>
}

export function Badge({ children, tone = 'neutral', className }: { children: ReactNode; tone?: 'neutral' | 'good' | 'bad' | 'warn' | 'ours' | 'waste'; className?: string }) {
  const tones = {
    neutral: 'bg-surface-3 text-muted border-line',
    good: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
    bad: 'bg-red-500/10 text-red-300 border-red-500/30',
    warn: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    ours: 'bg-cyan-400/10 text-cyan-300 border-cyan-400/30',
    waste: 'bg-violet-400/10 text-violet-300 border-violet-400/30',
  }
  return <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium', tones[tone], className)}>{children}</span>
}

export function Button({ children, onClick, variant = 'primary', disabled, className, type = 'button' }:
  { children: ReactNode; onClick?: () => void; variant?: 'primary' | 'ghost' | 'blood'; disabled?: boolean; className?: string; type?: 'button' | 'submit' }) {
  const v = {
    primary: 'bg-ours text-bg hover:brightness-110 shadow-[0_0_24px_rgba(34,211,238,0.25)]',
    blood: 'bg-blood text-white hover:brightness-110 shadow-[0_0_24px_rgba(225,29,72,0.3)]',
    ghost: 'bg-surface-2 text-ink border border-line hover:bg-surface-3',
  }
  return (
    <motion.button whileTap={{ scale: 0.97 }} type={type} disabled={disabled} onClick={onClick}
      className={clsx('inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed', v[variant], className)}>
      {children}
    </motion.button>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <div className="flex items-baseline justify-between gap-2 mb-1.5">
        <span className="text-xs font-medium text-muted">{label}</span>
        {hint && <span className="text-xs text-ink num">{hint}</span>}
      </div>
      {children}
    </label>
  )
}

export const inputCls = 'w-full rounded-lg bg-surface-2 border border-line px-3 py-2 text-sm text-ink outline-none focus:border-ours/60 focus:ring-2 focus:ring-ours/20'

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-muted">
      <div className="relative h-12 w-12">
        <motion.div className="absolute inset-0 rounded-full border-2 border-blood/30 border-t-blood" animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 0.9, ease: 'linear' }} />
        <motion.div className="absolute inset-2 rounded-full border-2 border-ours/30 border-b-ours" animate={{ rotate: -360 }} transition={{ repeat: Infinity, duration: 1.4, ease: 'linear' }} />
      </div>
      {label && <div className="text-sm">{label}</div>}
    </div>
  )
}

export function ErrorNote({ error }: { error: string }) {
  return <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
}

export function Delta({ base, value, better = 'lower', format = (x: number) => `${x > 0 ? '+' : ''}${x.toFixed(0)}%` }:
  { base: number; value: number; better?: 'lower' | 'higher'; format?: (x: number) => string }) {
  if (!base) return null
  const pct = (100 * (value - base)) / base
  const good = better === 'lower' ? pct < 0 : pct > 0
  if (Math.abs(pct) < 0.5) return <Badge>±0%</Badge>
  return <Badge tone={good ? 'good' : 'bad'}>{format(pct)}</Badge>
}

export function Source({ href, children }: { href: string; children: ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer" className="text-[11px] text-faint hover:text-muted underline decoration-dotted underline-offset-2">{children}</a>
}

export function coverColor(days: number): string {
  if (days < 1) return '#ef4444'
  if (days < 2) return '#f97316'
  if (days < 3) return '#f59e0b'
  return '#34d399'
}
