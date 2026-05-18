const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

async function getComments(env, slug) {
  const raw = await env.COMMENTS.get(slug);
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

async function putComments(env, slug, data) {
  await env.COMMENTS.put(slug, JSON.stringify(data));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // Auth for write operations
    if (request.method === "POST" || request.method === "PUT" || request.method === "DELETE") {
      const auth = request.headers.get("Authorization") || "";
      const token = auth.replace("Bearer ", "");
      if (!env.API_SECRET || token !== env.API_SECRET) {
        return json({ error: "unauthorized" }, 401);
      }
    }

    // Routes: /api/comments/<slug> and /api/comments/<slug>/@<id>
    // Slug can contain slashes (e.g. "organizaciones/agora-partnerships")
    // Using /@ separator for comment ID to avoid ambiguity
    const commentMatch = path.match(/^\/api\/comments\/(.+?)\/@([^/]+)$/);
    const slugMatch = !commentMatch && path.match(/^\/api\/comments\/(.+?)\/??$/);

    // GET /api/comments/<slug>
    if (slugMatch && request.method === "GET") {
      const slug = decodeURIComponent(slugMatch[1]);
      return json(await getComments(env, slug));
    }

    // POST /api/comments/<slug>
    if (slugMatch && request.method === "POST") {
      const slug = decodeURIComponent(slugMatch[1]);
      const body = await request.json();
      const comments = await getComments(env, slug);
      comments.push(body);
      await putComments(env, slug, comments);
      return json(body, 201);
    }

    // PUT /api/comments/<slug>/@<id>
    if (commentMatch && request.method === "PUT") {
      const slug = decodeURIComponent(commentMatch[1]);
      const cid = decodeURIComponent(commentMatch[2]);
      const body = await request.json();
      const comments = await getComments(env, slug);
      const idx = comments.findIndex(c => c.id === cid);
      if (idx === -1) return json({ error: "not found" }, 404);
      comments[idx] = body;
      await putComments(env, slug, comments);
      return json(body);
    }

    // DELETE /api/comments/<slug>/@<id>
    if (commentMatch && request.method === "DELETE") {
      const slug = decodeURIComponent(commentMatch[1]);
      const cid = decodeURIComponent(commentMatch[2]);
      const comments = await getComments(env, slug);
      const filtered = comments.filter(c => c.id !== cid);
      await putComments(env, slug, filtered);
      return json({ deleted: cid });
    }

    // GET /api/sync — returns all slugs and their comments
    if (path === "/api/sync" && request.method === "GET") {
      const auth = request.headers.get("Authorization") || "";
      const token = auth.replace("Bearer ", "");
      if (!env.API_SECRET || token !== env.API_SECRET) {
        return json({ error: "unauthorized" }, 401);
      }
      const list = await env.COMMENTS.list();
      const all = {};
      for (const key of list.keys) {
        all[key.name] = await getComments(env, key.name);
      }
      return json(all);
    }

    // PUT /api/sync — bulk upload from local
    if (path === "/api/sync" && request.method === "PUT") {
      const auth = request.headers.get("Authorization") || "";
      const token = auth.replace("Bearer ", "");
      if (!env.API_SECRET || token !== env.API_SECRET) {
        return json({ error: "unauthorized" }, 401);
      }
      const body = await request.json();
      for (const [slug, comments] of Object.entries(body)) {
        await putComments(env, slug, comments);
      }
      return json({ synced: Object.keys(body).length });
    }

    return json({ error: "not found" }, 404);
  },
};
