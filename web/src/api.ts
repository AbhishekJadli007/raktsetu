// Typed client for the RaktSetu FastAPI backend.

export type Bank = { short: string; name: string; lat: number; lon: number; operator: string; role: string; runs_camps: boolean }
export type Meta = {
  banks: Bank[]
  dates: { first: string; last: string; today: string }
  skus: string[]
  defaults: { vans: number; kappa: number; quantile: number; trips_per_van: number; box_capacity: number }
  dengue_cases_rajasthan: Record<string, number>
}

export type Trip = {
  from: string; from_name: string; to: string; to_name: string
  drive_min: number; drive_km: number; units: number
  items: { sku: string; units: number }[]
  reasons: string[]
}
export type BankStatus = {
  bank: string; name: string; lat: number; lon: number; operator: string; role: string
  rbc_stock: number; rbc_days_cover: number; plt_stock: number; plt_days_cover: number
  at_risk_units: number; short_skus: string[]; need_units: number; spare_units: number
  stock_by_sku: Record<string, number>; min_cover_days: number
}
export type Plan = {
  date: string; summary: string; trips: Trip[]; banks: BankStatus[]
  unresolved: { bank: string; sku: string; units: number; action: string }[]
  totals: { trips: number; units: number; units_rescued_from_expiry: number; km: number; at_risk_units: number; short_positions: number; unresolved_units: number }
  solver_status: string; vans: number; max_trips: number
}
export type Radar = {
  date: string; current_demand_per_day: number; current_production_per_day: number
  weeks: { week: number; starts: string; expected_per_day: number; low: number; high: number }[]
  level: 'normal' | 'watch' | 'alert'; action: string; driver: string
}

export type PolicyKey = 'isolated' | 'reactive' | 'raktsetu'
export type Kpis = {
  rbc_fill_rate: number; plt_fill_rate: number; rbc_wastage_rate: number; plt_wastage_rate: number
  rbc_unmet: number; plt_unmet: number; rbc_expired: number; plt_expired: number
  total_unmet: number; total_expired: number; planned_trips: number; emergency_trips: number
  total_trips: number; total_km: number; planned_units_moved: number; emergency_units_moved: number
  rbc_requests: number; plt_requests: number
}
export type PolicyRun = {
  kpis: Kpis
  daily: Record<'unmet_rbc' | 'unmet_plt' | 'expired_rbc' | 'expired_plt' | 'demand_plt' | 'demand_rbc', number[]>
  bank_days: number[][][] // [day][bank][rbcStock, pltStock, unmet]
  transfers: [number, number, number, 'planned' | 'emergency'][][]
}
export type SimResult = {
  start: string; end: string; dates: string[]; banks: string[]; policies: Record<PolicyKey, PolicyRun>
  bank_mean_demand: [number, number][] // per bank: mean daily [red cells, platelets]
}

export type BankWindow = { bank: string; start: string; end: string }
export type ScenarioIn = {
  seed?: number; dengue_scale?: number; kappa?: number; donation_change?: number
  change_start?: string | null; change_end?: string | null
  separator_failure?: BankWindow[]; collection_halt?: BankWindow[]
  surge?: { bank: string; date: string; units: number }[]
  vans?: number
}

export type Drivers = {
  dates: string[]; rain_mm: number[]; temp_c: number[]; dengue_signal: number[]
  plt_requests: number[]; plt_produced: number[]; rbc_requests: number[]
}
export type ForecastSeries = { bank: string; product: string; dates: string[]; actual: number[]; ml: number[]; ma7: number[]; true_mean: number[] }

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* keep status text */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

export const api = {
  meta: () => req<Meta>('/api/meta'),
  plan: (body: { date: string; history?: string; scenario?: ScenarioIn; overrides?: Record<string, Record<string, number>> | null }) =>
    req<Plan>('/api/plan', { method: 'POST', body: JSON.stringify(body) }),
  radar: (date: string) => req<Radar>(`/api/radar?date=${date}`),
  simulate: (body: { start: string; end: string; scenario?: ScenarioIn; forecaster?: string }) =>
    req<SimResult>('/api/simulate', { method: 'POST', body: JSON.stringify(body) }),
  drivers: (start: string, end: string) => req<Drivers>(`/api/drivers?start=${start}&end=${end}`),
  forecast: (bank: string, product: string, start: string, end: string) =>
    req<ForecastSeries>(`/api/forecast?bank=${bank}&product=${product}&start=${start}&end=${end}`),
  evaluation: () => req<any>('/api/evaluation'),
}

export const POLICY_META: Record<PolicyKey, { label: string; short: string; color: string; blurb: string }> = {
  isolated: { label: 'Isolated banks', short: 'Isolated', color: '#64748b', blurb: 'Every bank on its own. No sharing.' },
  reactive: { label: 'Phone-around (today)', short: 'Today', color: '#f59e0b', blurb: 'A bank that runs out calls its nearest neighbours.' },
  raktsetu: { label: 'RaktSetu', short: 'RaktSetu', color: '#22d3ee', blurb: 'Forecast, then move stock every morning before anyone runs out.' },
}

export const fmtPct = (x: number, d = 1) => `${(100 * x).toFixed(d)}%`
export const fmtInt = (x: number) => Math.round(x).toLocaleString('en-IN')
