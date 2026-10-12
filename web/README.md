# RaktSetu web app

React 19 + Vite + Tailwind 4 + framer-motion + react-leaflet + Recharts.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
npm run build    # outputs dist/, which FastAPI serves at http://localhost:8000
```

Views: `src/views/Overview.tsx`, `ControlRoom.tsx` (today's plan, editable stock), `SimLab.tsx` (scenarios + replay), `Evidence.tsx` (evaluation).
API client and types: `src/api.ts`. Map: `src/components/NetworkMap.tsx`.
