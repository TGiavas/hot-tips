import { defineConfig, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

// In production the bundle is collected into Django's staticfiles and served
// at /static/, so we set the base to '/static/'. In dev we serve directly
// from Vite at '/'.
//
// The proxy lets the browser talk to a single origin (the Vite dev server) so
// session cookies + CSRF work without CORS gymnastics. We forward /api, /admin,
// /accounts, and /static to the Django backend container. The DEV_BACKEND env
// var lets you point the proxy at a non-default backend host.
const DEV_BACKEND = process.env.DEV_BACKEND ?? 'http://backend:8000'

// CAREFUL: do not use the string shorthand here. Vite's shorthand wraps each
// entry as `{ target, changeOrigin: true }`, which rewrites the outgoing
// Host header to "backend:8000". That breaks allauth's OAuth flow because
// `request.build_absolute_uri()` then constructs a redirect_uri of
// http://backend:8000/... and Discord/Google reject it as malformed. We pass
// `changeOrigin: false` explicitly so the browser's Host (localhost:5173)
// is preserved.
const toBackend = (target: string): ProxyOptions => ({
  target,
  changeOrigin: false,
})

const proxied: Record<string, ProxyOptions> = {
  '/api': toBackend(DEV_BACKEND),
  '/admin': toBackend(DEV_BACKEND),
  '/accounts': toBackend(DEV_BACKEND),
  '/static': toBackend(DEV_BACKEND),
}

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/static/' : '/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: proxied,
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    emptyOutDir: true,
  },
}))
