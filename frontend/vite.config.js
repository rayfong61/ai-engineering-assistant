import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Docker Desktop on Windows doesn't propagate native filesystem
    // change events into the container for bind-mounted files, so
    // chokidar's default watcher silently misses edits made on the host.
    // Polling works around that at the cost of a bit of CPU.
    watch: { usePolling: true, interval: 300 },
  },
})
