import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, isAbsolute, join, normalize, relative, resolve, sep } from "node:path";
import { createServer, request as httpRequest } from "node:http";

const projectRoot = process.cwd();
const configuredStaticRoot = process.env.STATIC_ROOT || ".";
const root = resolve(projectRoot, configuredStaticRoot);
const port = Number(process.env.PORT || 4173);
const backendPort = Number(process.env.BACKEND_PORT || 8000);
const frontendApiBaseUrl = process.env.FRONTEND_API_BASE_URL || "/api";
const securityHeaders = {
  "Content-Security-Policy": "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
};
const reviewPathPrefix = "/data/reviews/tl004-junction-aware/";
const reviewSecurityHeaders = {
  ...securityHeaders,
  "Content-Security-Policy": "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'",
};

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
};

createServer((request, response) => {
  const url = new URL(request.url || "/", `http://localhost:${port}`);

  if (url.pathname === "/app/runtime-config.js") {
    response.writeHead(200, {
      ...securityHeaders,
      "Cache-Control": "no-store",
      "Content-Type": "text/javascript; charset=utf-8",
    });
    response.end(
      `window.__THREATLENS_CONFIG__ = ${JSON.stringify({ apiBaseUrl: frontendApiBaseUrl })};`,
    );
    return;
  }

  // Proxy /api/* → Python backend
  if (url.pathname.startsWith("/api/")) {
    const target = url.pathname.replace(/^\/api/, "") + (url.search || "");
    const proxyOptions = {
      hostname: "127.0.0.1",
      port: backendPort,
      path: target,
      method: request.method,
      headers: { ...request.headers, host: `127.0.0.1:${backendPort}` },
    };
    const proxyReq = httpRequest(proxyOptions, (proxyRes) => {
      response.writeHead(proxyRes.statusCode, { ...proxyRes.headers, ...securityHeaders });
      proxyRes.pipe(response);
    });
    proxyReq.on("error", (err) => {
      if (!response.headersSent) {
        response.writeHead(502, {
          ...securityHeaders,
          "Content-Type": "text/plain; charset=utf-8",
        });
        response.end(`Backend unavailable: ${err.message}`);
      }
    });
    request.pipe(proxyReq);
    return;
  }

  const requestPath = url.pathname === "/" ? "/app/index.html" : url.pathname;
  const filePath = normalize(join(root, requestPath));
  const relativePath = relative(root, filePath);
  const staticSecurityHeaders = url.pathname.startsWith(reviewPathPrefix)
    ? reviewSecurityHeaders
    : securityHeaders;

  if (request.method !== "GET" && request.method !== "HEAD") {
    response.writeHead(405, {
      ...securityHeaders,
      "Allow": "GET, HEAD",
      "Content-Type": "text/plain; charset=utf-8",
    });
    response.end("Method not allowed");
    return;
  }

  if (
    relativePath === ".." ||
    relativePath.startsWith(`..${sep}`) ||
    isAbsolute(relativePath) ||
    !existsSync(filePath) ||
    statSync(filePath).isDirectory()
  ) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }

  response.writeHead(200, {
    ...staticSecurityHeaders,
    "Content-Type":
      mimeTypes[extname(filePath).toLowerCase()] || "application/octet-stream",
  });
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  createReadStream(filePath).pipe(response);
}).listen(port, () => {
  console.log(`ThreatLens AI running at http://localhost:${port}`);
});
