import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

// createRoot is the React 18 API. ReactDOM.render is the legacy entry point:
// it logs a warning, opts out of concurrent rendering, and ignores features
// that depend on it (Suspense, transitions).
const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element #root not found in index.html');
}

createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
