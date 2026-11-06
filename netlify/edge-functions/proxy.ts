import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  // 1. Проверка токена
  const EXPECTED_TOKEN = Deno.env.get("MY_SECRET_TOKEN");
  if (!EXPECTED_TOKEN) {
    return new Response("Server configuration error", { status: 500 });
  }

  const url = new URL(request.url);
  const providedToken = url.searchParams.get("token");

  if (providedToken !== EXPECTED_TOKEN) {
    return new Response("Access denied: invalid or missing token.", {
      status: 403,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  // 2. Ваша ссылка на GitHub
  const GITHUB_RAW_URL = "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/whitelist.m3u";

  try {
    const upstream = await fetch(GITHUB_RAW_URL, { cache: "no-store" });
    if (!upstream.ok) {
      return new Response(`Upstream error: ${upstream.status}`, { status: 502 });
    }

    const body = await upstream.text();

    // 3. Отдаем плейлист и кэшируем на CDN Netlify на 5 минут
    return new Response(body, {
      status: 200,
      headers: {
        "content-type": "audio/x-mpegurl; charset=utf-8",
        "Netlify-CDN-Cache-Control": "public, max-age=300",
        "Cache-Control": "public, max-age=300",
      },
    });
  } catch (err) {
    return new Response(`Proxy error: ${err}`, { status: 500 });
  }
};

export const config: Config = {
  path: "/playlist.m3u",
};
