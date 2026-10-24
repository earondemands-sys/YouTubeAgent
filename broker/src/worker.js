// worker.js - the "Connect Instagram" login server for YouTubeAgent (a Cloudflare Worker).
//
// It exists for one reason: Instagram's login needs the Meta app's secret, and the secret cannot
// ship inside a public repo. So the secret lives here, and every creator who runs the skill just
// clicks Allow. The flow, with no address pasting:
//
//   1. instagram_auth.py makes a random `state` and a random `claim`, and opens
//      /login?state=<state>&ch=<sha256(claim)> in the browser.
//   2. /login remembers (state -> ch) for 10 minutes and sends the browser to Instagram's Allow page.
//   3. Instagram sends the browser to /callback?code=...&state=... . The worker trades the code for a
//      60-day token (the step that needs the secret) and keeps it under that state for 5 minutes.
//   4. instagram_auth.py polls POST /claim {state, claim}. Only the holder of `claim` - the terminal
//      that started the login - gets the token, exactly once; then it is deleted from here.
//
// Renewing a token needs no secret, so after step 4 the creator's computer never talks to this
// worker again. Nothing is stored past those few minutes; /privacy says so, and the deauthorize
// and data-deletion endpoints Meta requires have nothing to delete.
//
// Bindings (wrangler.toml): SESSIONS (KV), INSTAGRAM_APP_ID, API_VERSION, CONTACT_EMAIL, APP_NAME;
// secret: INSTAGRAM_APP_SECRET (`npx wrangler secret put INSTAGRAM_APP_SECRET`).

const SCOPES = [
  "instagram_business_basic",
  "instagram_business_content_publish",
  "instagram_business_manage_comments",
  "instagram_business_manage_messages",
];
const LOGIN_TTL = 600;  // seconds from /login to Allow
const CLAIM_TTL = 300;  // seconds the token waits for the terminal to collect it
const STATE_RE = /^[A-Za-z0-9_-]{32,128}$/;
const HEX64 = /^[0-9a-f]{64}$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      const route = ROUTES[`${request.method} ${url.pathname}`];
      if (!route) return page(env, 404, "Not found", "<p>Nothing here.</p>");
      return await route(request, env, url);
    } catch (e) {
      return page(env, 500, "Something went wrong", `<p>${esc(e.message || String(e))}</p><p>Run the connect command again.</p>`);
    }
  },
};

const ROUTES = {
  "GET /": (req, env) => page(env, 200, `${appName(env)}`,
    `<p>This service connects an Instagram professional account to ${esc(appName(env))}, a tool creators run on
     their own computer to post Reels and answer comments and DMs.</p>
     <p>Start it from the tool: <code>python3 scripts/instagram_auth.py</code></p>
     <p><a href="/privacy">Privacy policy</a></p>`),
  "GET /login": login,
  "GET /callback": callback,
  "POST /claim": claim,
  "POST /deauthorize": deauthorize,
  "POST /data-deletion": dataDeletion,
  "GET /deletion": (req, env, url) => page(env, 200, "Data deletion",
    `<p>Request <code>${esc(url.searchParams.get("id") || "")}</code> is complete.</p>
     <p>This service keeps no data about you: a sign-in is held for at most five minutes until your own
     computer collects it, then deleted. Anything the tool saved lives only on that computer.</p>`),
  "GET /privacy": privacy,
};

async function login(req, env, url) {
  const state = url.searchParams.get("state") || "";
  const ch = (url.searchParams.get("ch") || "").toLowerCase();
  if (!STATE_RE.test(state) || !HEX64.test(ch)) {
    return page(env, 400, "Bad link", "<p>Start the connection from the tool: <code>python3 scripts/instagram_auth.py</code></p>");
  }
  if (await env.SESSIONS.get(key(state))) {
    return page(env, 409, "Link already used", "<p>Run <code>python3 scripts/instagram_auth.py</code> again for a fresh link.</p>");
  }
  await env.SESSIONS.put(key(state), JSON.stringify({ ch, at: Date.now() }), { expirationTtl: LOGIN_TTL });
  const auth = new URL("https://www.instagram.com/oauth/authorize");
  auth.search = new URLSearchParams({
    client_id: env.INSTAGRAM_APP_ID,
    redirect_uri: `${url.origin}/callback`,
    response_type: "code",
    scope: SCOPES.join(","),
    state,
    enable_fb_login: "0",
    force_reauth: "true",
  }).toString();
  return Response.redirect(auth.toString(), 302);
}

async function callback(req, env, url) {
  const state = url.searchParams.get("state") || "";
  const saved = STATE_RE.test(state) && (await env.SESSIONS.get(key(state), "json"));
  if (!saved) {
    return page(env, 410, "This link has expired", "<p>Go back to your terminal and run <code>python3 scripts/instagram_auth.py</code> again.</p>");
  }
  if (saved.result || saved.error) {
    return page(env, 409, "Already done", "<p>This sign-in has already been used. Go back to your terminal.</p>");
  }
  const err = url.searchParams.get("error");
  if (err) {
    const why = url.searchParams.get("error_description") || url.searchParams.get("error_reason") || err;
    await env.SESSIONS.put(key(state), JSON.stringify({ ch: saved.ch, error: why }), { expirationTtl: CLAIM_TTL });
    return page(env, 200, "Not connected", `<p>Instagram said: ${esc(why)}</p><p>You can close this tab.</p>`);
  }
  const code = (url.searchParams.get("code") || "").split("#")[0];
  if (!code) return page(env, 400, "No code", "<p>Instagram did not send a code. Try again from the tool.</p>");

  let result;
  try {
    result = await exchange(env, code, `${url.origin}/callback`);
  } catch (e) {
    await env.SESSIONS.put(key(state), JSON.stringify({ ch: saved.ch, error: e.message }), { expirationTtl: CLAIM_TTL });
    return page(env, 502, "Not connected", `<p>${esc(e.message)}</p><p>Go back to your terminal and try again.</p>`);
  }
  await env.SESSIONS.put(key(state), JSON.stringify({ ch: saved.ch, result }), { expirationTtl: CLAIM_TTL });
  const pro = ["BUSINESS", "MEDIA_CREATOR", "CREATOR"].includes(result.account_type);
  return page(env, 200, `Connected @${esc(result.username || "")}`,
    `<p>Your Instagram account is connected. <b>Go back to your terminal</b> - it finishes there on its own.</p>
     ${pro ? "" : "<p><b>Note:</b> posting needs a Creator or Business account (Instagram -> Settings -> Account type and tools).</p>"}
     <p>You can close this tab.</p>`);
}

async function exchange(env, code, redirect) {
  const short = await json(await fetch("https://api.instagram.com/oauth/access_token", {
    method: "POST",
    body: new URLSearchParams({
      client_id: env.INSTAGRAM_APP_ID, client_secret: env.INSTAGRAM_APP_SECRET,
      grant_type: "authorization_code", redirect_uri: redirect, code,
    }),
  }), "code exchange");
  const s = short.data ? short.data[0] : short;
  const long = await json(await fetch("https://graph.instagram.com/access_token?" + new URLSearchParams({
    grant_type: "ig_exchange_token", client_secret: env.INSTAGRAM_APP_SECRET, access_token: s.access_token,
  })), "long-lived token");
  const me = await json(await fetch(`https://graph.instagram.com/${env.API_VERSION || "v23.0"}/me?` + new URLSearchParams({
    fields: "user_id,username,account_type", access_token: long.access_token,
  })), "account lookup");
  return {
    access_token: long.access_token, expires_in: long.expires_in || 5184000,
    user_id: String(me.user_id || s.user_id), username: me.username, account_type: me.account_type,
    permissions: s.permissions || null,
  };
}

async function claim(req, env) {
  let body;
  try {
    body = await req.json();
  } catch {
    return reply({ status: "bad-request" }, 400);
  }
  const { state = "", claim: secret = "" } = body || {};
  if (!STATE_RE.test(state) || typeof secret !== "string" || secret.length < 32) {
    return reply({ status: "bad-request" }, 400);
  }
  const saved = await env.SESSIONS.get(key(state), "json");
  if (!saved) return reply({ status: "unknown" }, 404);
  if ((await sha256hex(secret)) !== saved.ch) return reply({ status: "forbidden" }, 403);
  if (saved.error) {
    await env.SESSIONS.delete(key(state));
    return reply({ status: "error", error: saved.error });
  }
  if (!saved.result) return reply({ status: "pending" }, 202);
  await env.SESSIONS.delete(key(state));
  return reply({ status: "ok", token: saved.result });
}

// Meta calls these when someone removes the app or asks for their data to be deleted. The worker
// keeps nothing past a few minutes, so there is nothing to remove; it still checks the signature.
async function deauthorize(req, env) {
  const data = await signedRequest(req, env);
  if (!data) return reply({ error: "bad signature" }, 400);
  return reply({ ok: true });
}

async function dataDeletion(req, env) {
  const data = await signedRequest(req, env);
  if (!data) return reply({ error: "bad signature" }, 400);
  const code = crypto.randomUUID();
  return reply({ url: `${new URL(req.url).origin}/deletion?id=${code}`, confirmation_code: code });
}

async function signedRequest(req, env) {
  const form = await req.formData().catch(() => null);
  const raw = form && form.get("signed_request");
  if (!raw || !raw.includes(".")) return null;
  const [sig, payload] = raw.split(".", 2);
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(env.INSTAGRAM_APP_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const want = b64url(new Uint8Array(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(payload))));
  if (!timingSafeEqual(want, sig)) return null;
  try {
    return JSON.parse(new TextDecoder().decode(unb64url(payload)));
  } catch {
    return null;
  }
}

function privacy(req, env) {
  const contact = env.CONTACT_EMAIL ? `<a href="mailto:${esc(env.CONTACT_EMAIL)}">${esc(env.CONTACT_EMAIL)}</a>` : "the project's GitHub page";
  return page(env, 200, "Privacy policy", `
    <p><b>${esc(appName(env))}</b> is a tool a creator runs on their own computer. With the creator's
    permission it posts Reels to their Instagram professional account, reads and replies to comments
    on their posts, and reads and replies to direct messages sent to that account.</p>
    <h2>What this connection service does</h2>
    <p>When a creator connects Instagram, this service receives the sign-in from Instagram, turns it
    into an access token, and hands it to the creator's own computer. The token is held for at most
    five minutes until that computer collects it, then deleted. This service stores no tokens,
    posts, comments, messages or profile data, and shares nothing with anyone.</p>
    <h2>What the tool on the creator's computer keeps</h2>
    <p>The access token, and the posts, comments and messages it handles, are saved only on the
    creator's computer. Replies are drafted with an AI model the creator chooses and sent only to the
    person who commented or messaged. Nothing is sold or used for advertising.</p>
    <h2>Removing access and deleting data</h2>
    <p>Remove the app any time in Instagram: Settings -> Website permissions -> Apps and websites.
    Since this service keeps nothing, there is nothing left here to delete; deleting the tool's
    folder removes everything it saved.</p>
    <h2>Contact</h2>
    <p>${contact}</p>`);
}

// ------------------------------------------------------------------ helpers

const key = (state) => `s:${state}`;
const appName = (env) => env.APP_NAME || "YouTubeAgent";

async function json(res, what) {
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = {};
  }
  if (!res.ok || body.error || body.error_type) {
    const e = body.error || {};
    const msg = (typeof e === "object" ? e.error_user_msg || e.message : e) || body.error_message || text.slice(0, 200);
    throw new Error(`Instagram ${what} failed: ${msg}`);
  }
  return body;
}

function reply(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function page(env, status, title, body) {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)} - ${esc(appName(env))}</title>
<style>
:root{--bg:#fafafa;--fg:#1a1a1a;--muted:#666;--card:#fff;--line:#e5e5e5;--accent:#c13584}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--muted:#aaa;--card:#1b1b1b;--line:#333;--accent:#e1306c}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,sans-serif}
main{max-width:640px;margin:48px auto;padding:28px;background:var(--card);border:1px solid var(--line);border-radius:14px}
h1{font-size:22px;margin:0 0 12px}h2{font-size:17px;margin:22px 0 6px}a{color:var(--accent)}
code{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:14px}
footer{color:var(--muted);font-size:13px;margin-top:24px}
@media (max-width:700px){main{margin:16px;padding:20px}}
</style></head><body><main><h1>${esc(title)}</h1>${body}
<footer>${esc(appName(env))} · <a href="/privacy">Privacy</a></footer></main></body></html>`;
  return new Response(html, {
    status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
                       "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; frame-ancestors 'none'" },
  });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

async function sha256hex(s) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  return [...d].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function unb64url(s) {
  const b = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
