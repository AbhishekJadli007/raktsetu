import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, ZoomControl } from 'react-leaflet'

export type MapBank = {
  short: string
  name: string
  lat: number
  lon: number
  color: string
  size: number // px
  pulse?: boolean
  tooltip: string // small HTML snippet
}
export type MapArc = { from: [number, number]; to: [number, number]; units: number; color: string; slow?: boolean; key: string }

function curve(a: [number, number], b: [number, number], bend = 0.22, n = 28): [number, number][] {
  const [y1, x1] = a
  const [y2, x2] = b
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const dx = x2 - x1
  const dy = y2 - y1
  const cx = mx - dy * bend
  const cy = my + dx * bend
  const pts: [number, number][] = []
  for (let i = 0; i <= n; i++) {
    const t = i / n
    const x = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * cx + t * t * x2
    const y = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * cy + t * t * y2
    pts.push([y, x])
  }
  return pts
}

function FitBounds({ banks }: { banks: MapBank[] }) {
  const map = useMap()
  const key = banks.map((b) => b.short).join(',')
  useEffect(() => {
    if (!banks.length) return
    map.invalidateSize()
    map.fitBounds(L.latLngBounds(banks.map((b) => [b.lat, b.lon] as [number, number])).pad(0.12))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map])
  return null
}

export function NetworkMap({ banks, arcs, selected, onSelect, height = 520, showLabels = true }:
  { banks: MapBank[]; arcs: MapArc[]; selected?: string | null; onSelect?: (s: string) => void; height?: number | string; showLabels?: boolean }) {
  const icons = useMemo(() => {
    const m: Record<string, L.DivIcon> = {}
    for (const b of banks) {
      const s = Math.max(10, Math.min(34, b.size))
      const cls = ['bank-dot', b.pulse ? 'pulse' : '', selected === b.short ? 'selected' : ''].join(' ')
      m[b.short] = L.divIcon({
        className: '',
        iconSize: [s, s],
        iconAnchor: [s / 2, s / 2],
        html: `<div style="width:${s}px;height:${s}px;background:${b.color};color:${b.color}" class="${cls}"></div>` +
          (showLabels ? `<div class="bank-label" style="position:absolute;left:${s + 4}px;top:${s / 2 - 7}px">${b.short}</div>` : ''),
      })
    }
    return m
  }, [banks, selected, showLabels])

  return (
    <div style={{ height }} className="relative overflow-hidden rounded-2xl border border-line">
      <MapContainer center={[26.88, 75.8]} zoom={12} scrollWheelZoom={false} zoomControl={false} style={{ height: '100%', width: '100%' }} attributionControl>
        {/* Standard OSM tiles (no API key), darkened with a CSS filter (.dark-tiles in index.css) */}
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="dark-tiles"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <ZoomControl position="bottomright" />
        <FitBounds banks={banks} />
        {arcs.map((a) => (
          <Polyline key={a.key} positions={curve(a.from, a.to)}
            pathOptions={{ color: a.color, weight: Math.min(7, 1.6 + Math.sqrt(a.units) / 2), opacity: 0.95, className: a.slow ? 'arc slow' : 'arc', lineCap: 'round' }} />
        ))}
        {banks.map((b) => (
          <Marker key={b.short} position={[b.lat, b.lon]} icon={icons[b.short]} eventHandlers={{ click: () => onSelect?.(b.short) }}>
            <Tooltip direction="top" offset={[0, -10]} className="bank-tip">
              <div dangerouslySetInnerHTML={{ __html: b.tooltip }} />
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
