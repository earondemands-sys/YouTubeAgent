// Offline tests for the login server: Instagram and KV are faked.  Run: node --test broker/test/
import { test } from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import worker from "../src/worker.js";

const ORIGIN = "https://connect.example.workers.dev";
const SECRET = "app-secret-123";

function kv() {
  const m = new Map();
  return {
    m,
    async get(k, type) { const v = m.get(k); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; },
    async put(k, v) { m.set(k, v); },
    async delete(k) { m.delete(k); },
  };
}

const env = () => ({ SESSIONS: kv(), INSTAGRAM_APP_ID: "999", INSTAGRAM_APP_SECRET: SECRET, API_VERSION: "v23.0", CONTACT_EMAIL: "hi@example.com" });
const sha = (s) => crypto.createHash("sha256").update(s).digest("hex");
const rand = () => crypto.randomBytes(32).toString("base64url");
const get = (e, path) => worker.fetch(new Request(ORIGIN + path, { redirect: "manual" }), e);
const post = (e, path, body) => worker.fetch(new Request(ORIGIN + path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }), e);

let calls = [];
function fakeInstagram({ fail } = {}) {
  calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const u = new URL(url);
    calls.push({ url: u, init });
    if (fail) return new Response(JSON.stringify({ error_type: "OAuthException", error_message: "Invalid code" }), { status: 400 });
    if (u.host === "api.instagram.com") return Response.json({ access_token: "SHORT", user_id: 1784, permissions: ["instagram_business_basic"] });
    if (u.pathname === "/access_token") return Response.json({ access_token: "LONG", token_type: "bearer", expires_in: 5183944 });
    if (u.pathname.endsWith("/me")) return Response.json({ user_id: "17841400000000000", username: "earondemands", account_type: "MEDIA_CREATOR" });
    throw new Error("unexpected " + url);
  };
}

async function startLogin(e) {
  const state = rand(), claim = rand();
  const r = await get(e, `/login?state=${state}&ch=${sha(claim)}`);
  return { state, claim, r };
}

test("login sends the browser to Instagram with our callback and scopes", async () => {
  const e = env();
  const { state, r } = await startLogin(e);
  assert.equal(r.status, 302);
  const to = new URL(r.headers.get("Location"));
  assert.equal(to.host, "www.instagram.com");
  assert.equal(to.searchParams.get("redirect_uri"), `${ORIGIN}/callback`);
  assert.equal(to.searchParams.get("state"), state);
  assert.match(to.searchParams.get("scope"), /instagram_business_manage_messages/);
  assert.equal(to.searchParams.get("client_id"), "999");
});

test("full flow: pending, then the token goes to the claim holder exactly once", async () => {
  const e = env();
  fakeInstagram();
  const { state, claim } = await startLogin(e);
  assert.equal((await post(e, "/claim", { state, claim })).status, 202);
  const cb = await get(e, `/callback?code=abc123%23_&state=${state}`);
  assert.equal(cb.status, 200);
  assert.match(await cb.text(), /Connected @earondemands/);
  assert.equal(calls[0].init.body.get("code"), "abc123");           // Instagram's trailing #_ removed
  assert.equal(calls[0].init.body.get("client_secret"), SECRET);
  const bad = await post(e, "/claim", { state, claim: rand() });
  assert.equal(bad.status, 403);                                     // someone with only the state gets nothing
  const ok = await (await post(e, "/claim", { state, claim })).json();
  assert.equal(ok.status, "ok");
  assert.equal(ok.token.access_token, "LONG");
  assert.equal(ok.token.user_id, "17841400000000000");
  assert.equal(e.SESSIONS.m.size, 0);                                // nothing kept
  assert.equal((await post(e, "/claim", { state, claim })).status, 404);
});

test("denied or failed logins reach the terminal as errors", async () => {
  const e = env();
  const { state, claim } = await startLogin(e);
  await get(e, `/callback?error=access_denied&error_description=User%20denied&state=${state}`);
  const r = await (await post(e, "/claim", { state, claim })).json();
  assert.deepEqual(r, { status: "error", error: "User denied" });

  fakeInstagram({ fail: true });
  const s2 = await startLogin(e);
  const cb = await get(e, `/callback?code=x&state=${s2.state}`);
  assert.equal(cb.status, 502);
  const r2 = await (await post(e, "/claim", { state: s2.state, claim: s2.claim })).json();
  assert.equal(r2.status, "error");
  assert.match(r2.error, /Invalid code/);
});

test("bad, reused and unknown links are refused", async () => {
  const e = env();
  assert.equal((await get(e, "/login?state=short&ch=abc")).status, 400);
  const { state, claim } = await startLogin(e);
  assert.equal((await get(e, `/login?state=${state}&ch=${sha(claim)}`)).status, 409);
  assert.equal((await get(e, `/callback?code=x&state=${rand()}`)).status, 410);
  assert.equal((await post(e, "/claim", { state: "nope", claim })).status, 400);
});

test("callback page escapes what Instagram sends back", async () => {
  const e = env();
  const { state } = await startLogin(e);
  const r = await get(e, `/callback?error=x&error_description=${encodeURIComponent("<script>alert(1)</script>")}&state=${state}`);
  const html = await r.text();
  assert.ok(!html.includes("<script>"));
  assert.ok(html.includes("&lt;script&gt;"));
});

function signed(payload, secret = SECRET) {
  const p = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = crypto.createHmac("sha256", secret).update(p).digest("base64url");
  return `${sig}.${p}`;
}

test("data deletion and deauthorize check Meta's signature", async () => {
  const e = env();
  const form = (sr) => new Request(ORIGIN + "/data-deletion", { method: "POST", body: new URLSearchParams({ signed_request: sr }) });
  const good = await (await worker.fetch(form(signed({ user_id: "1", algorithm: "HMAC-SHA256" })), e)).json();
  assert.match(good.url, /\/deletion\?id=/);
  assert.ok(good.confirmation_code);
  assert.equal((await worker.fetch(form(signed({ user_id: "1" }, "wrong")), e)).status, 400);
  const de = new Request(ORIGIN + "/deauthorize", { method: "POST", body: new URLSearchParams({ signed_request: signed({ user_id: "1" }) }) });
  assert.equal((await worker.fetch(de, e)).status, 200);
});

test("privacy page exists with the contact email", async () => {
  const r = await get(env(), "/privacy");
  assert.equal(r.status, 200);
  const html = await r.text();
  assert.match(html, /hi@example.com/);
  assert.match(html, /five minutes/);
});
