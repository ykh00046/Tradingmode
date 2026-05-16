// =============================================================================
// build.mjs — frontend build pipeline (PDCA cycle build-pipeline, v0.11.0).
//
// Replaces in-browser @babel/standalone transpilation with esbuild
// pre-compilation. Approach A-minimal: each JSX file is transformed
// individually (no --bundle), preserving the global-scope + load-order
// architecture so the 6 .jsx + 4 plain .js source files stay unchanged.
//
//   node build.mjs          production build  → build/
//   node build.mjs --dev    dev: no minify, watch + serve on :5173
// =============================================================================

import * as esbuild from 'esbuild';
import { cpSync, mkdirSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const DEV      = process.argv.includes('--dev');
const ROOT     = import.meta.dirname;                  // Tradingmode/
const OUT      = join(ROOT, 'build');
const BUILD_ID = DEV ? 'dev' : Date.now().toString(36);
const VARIANT  = DEV ? 'development' : 'production.min';

// Source entry points — order is irrelevant here (each file is transformed
// independently); index.html keeps the actual load order.
const ENTRIES = [
  'api.js', 'data.js', 'loader.js', 'lib/storage.js',
  'tweaks-panel.jsx', 'charts.jsx', 'signals-page.jsx',
  'portfolio-page.jsx', 'strategy-coach-page.jsx', 'app.jsx',
];

const buildOpts = {
  entryPoints: ENTRIES.map((f) => join(ROOT, f)),
  outdir: OUT,
  outbase: ROOT,                       // lib/storage.js -> build/lib/storage.js
  loader: { '.jsx': 'jsx' },
  jsx: 'transform',                    // classic -> React.createElement (global)
  minifyWhitespace: !DEV,
  minifySyntax:     !DEV,
  minifyIdentifiers: false,            // keep — components cross-reference each
                                       // other by bare global name (no imports)
  logLevel: 'info',
};

// Copy static assets that esbuild does not process: styles.css and the
// React / ReactDOM UMD builds (vendored from node_modules — same-origin,
// no SRI needed, no network at build time).
function copyStatic() {
  cpSync(join(ROOT, 'styles.css'), join(OUT, 'styles.css'));
  mkdirSync(join(OUT, 'vendor'), { recursive: true });
  for (const pkg of ['react', 'react-dom']) {
    cpSync(
      join(ROOT, 'node_modules', pkg, 'umd', `${pkg}.${VARIANT}.js`),
      join(OUT, 'vendor', `${pkg}.${VARIANT}.js`),
    );
  }
}

// Derive build/index.html from the source index.html (template, unchanged):
// drop @babel/standalone, point React at the vendored build, turn the
// text/babel JSX scripts into plain pre-compiled scripts, refresh cache query.
function genIndexHtml() {
  let html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  html = html
    .replace(/^.*@babel\/standalone.*\r?\n/m, '')
    .replace(
      /<script src="https:\/\/unpkg\.com\/react@[^"]*"[^>]*><\/script>/,
      `<script src="vendor/react.${VARIANT}.js"></script>`,
    )
    .replace(
      /<script src="https:\/\/unpkg\.com\/react-dom@[^"]*"[^>]*><\/script>/,
      `<script src="vendor/react-dom.${VARIANT}.js"></script>`,
    )
    .replace(
      /<script type="text\/babel" src="([^"]+)\.jsx\?v=\d+">/g,
      `<script src="$1.js?v=${BUILD_ID}">`,
    )
    .replace(/\?v=\d+/g, `?v=${BUILD_ID}`);
  writeFileSync(join(OUT, 'index.html'), html);
}

rmSync(OUT, { recursive: true, force: true });

if (DEV) {
  const ctx = await esbuild.context(buildOpts);
  await ctx.watch();                   // initial build + watch (.js/.jsx only;
                                       // edits to index.html/styles.css need a
                                       // manual rebuild)
  copyStatic();
  genIndexHtml();
  await ctx.serve({ servedir: OUT, port: 5173 });
  console.log('dev server -> http://localhost:5173  (watching .js/.jsx)');
} else {
  await esbuild.build(buildOpts);
  copyStatic();
  genIndexHtml();
  console.log(`build complete -> build/  (v=${BUILD_ID})`);
}
