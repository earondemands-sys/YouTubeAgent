// devserver.mjs - runs the worker on localhost with an in-memory KV and a fake Instagram, so the
// Python client can be tested against the real server code.  Prints the port on the first line.
//   node broker/test/devserver.mjs
import http from "node:http";
import worker from "../src/worker.js";

const store = new Map();
const env = {
  INSTAGRAM_APP_ID: "999", INSTAGRAM_APP_SECRET: "test-secret", API_VERSION: "v23.0",
  SESSIONS: {
    async get(k, type) { const v = store.get(k); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; },
    async put(k, v) { store.set(k, v); },
    async delete(k) { store.delete(k); },
  },
};

globalThis.fetch = async (url) => {
  const u = new URL(url);
  if (u.host === "api.instagram.com") return Response.json({ access_token: "SHORT", user_id: 1784 });
  if (u.pathname === "/access_token") return Response.json({ access_token: "LONG-TOKEN", expires_in: 5184000 });
  if (u.pathname.endsWith("/me")) return Response.json({ user_id: "17841400000000000", username: "earondemands", account_type: "MEDIA_CREATOR" });
  throw new Error("unexpected fetch " + url);
};

const server = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = chunks.length ? Buffer.concat(chunks) : undefined;
  const r = await worker.fetch(new Request(`http://127.0.0.1:${server.address().port}${req.url}`,
    { method: req.method, headers: req.headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : body }), env);
  res.writeHead(r.status, Object.fromEntries(r.headers));
  res.end(Buffer.from(await r.arrayBuffer()));
});
server.listen(0, "127.0.0.1", () => console.log(server.address().port));
