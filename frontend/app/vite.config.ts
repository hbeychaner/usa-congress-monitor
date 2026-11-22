import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('zrender')) return 'zrender';
          if (id.includes('echarts')) return 'echarts';
          if (id.includes('sigma') || id.includes('graphology')) return 'graph';
          if (id.includes('react-simple-maps') || id.includes('d3-') || id.includes('topojson')) {
            return 'maps';
          }
          return 'vendor';
        },
      },
    },
  },
});
