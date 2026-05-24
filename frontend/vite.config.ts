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

const proxied: Record<string, string | ProxyOptions> = {
  '/api': DEV_BACKEND,
  '/admin': DEV_BACKEND,
  '/accounts': DEV_BACKEND,
  '/static': DEV_BACKEND,
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
