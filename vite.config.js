import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// Prevent an automated deployment from replacing the site with an empty catalog.
if (process.env.VERCEL && !/^https:\/\//.test(process.env.VITE_NATIVE_CATALOG_BASE || '')) {
  throw new Error('Set VITE_NATIVE_CATALOG_BASE to the verified hosted overlay release before deploying.');
}

// Local-only adapter for the same versioned objects later served by a storage CDN.
// Bulk rasters stay outside public/ so builds never duplicate gigabytes of arrays.
function nativeScaleupFiles() {
  const root = fileURLToPath(new URL('../high_density_pixel_scaleup_20261112/', import.meta.url));
  const middleware = async (req,res,next) => {
    const url = (req.url || '').split('?')[0];
    if(!url.startsWith('/native-scaleup/'))return next();
    if(!['GET','HEAD'].includes(req.method)){res.statusCode=405;res.end();return;}
    const path=url.slice('/native-scaleup/'.length);
    let file;
    if(['index.json','run.json'].includes(path))file=`${root}release/${path}`;
    else if(/^assets\/[A-Za-z0-9_-]+\.(jpg|f32|npz|json)$/.test(path))file=`${root}${path}`;
    else if(/^details\/[A-Za-z0-9_-]+\.json$/.test(path))file=`${root}release/${path}`;
    else{res.statusCode=404;res.end();return;}
    try{
      const info=await stat(file);
      res.setHeader('Content-Length',info.size);
      res.setHeader('Content-Type',file.endsWith('.json')?'application/json':file.endsWith('.jpg')?'image/jpeg':'application/octet-stream');
      res.setHeader('Cache-Control',path.includes('/')?'public, max-age=31536000, immutable':'no-cache');
      if(req.method==='HEAD')res.end();else createReadStream(file).on('error',()=>res.destroy()).pipe(res);
    }catch{res.statusCode=404;res.end();}
  };
  return {name:'local-native-overlay-files',configureServer(server){server.middlewares.use(middleware);},configurePreviewServer(server){server.middlewares.use(middleware);}};
}
export default defineConfig({
  plugins: [react(),nativeScaleupFiles()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
});
