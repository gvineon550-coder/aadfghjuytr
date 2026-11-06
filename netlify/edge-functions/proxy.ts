import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  // 1. Добавляем заголовки CORS для совместимости с плеерами
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*",
  };

  // 2. Обрабатываем предварительный запрос OPTIONS (очень важно для плееров)
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  // 3. Проверка токена
  const EXPECTED_TOKEN = Deno.env.get("MY_SECRET_TOKEN");
  if (!EXPECTED_TOKEN) {
    return new Response("Server configuration error", { status: 500, headers: corsHeaders });
  }

  const url = new URL(request.url);
  const providedToken = url.searchParams.get("token");

  if (providedToken !== EXPECTED_TOKEN) {
    return new Response("Access denied: invalid or missing token.", {
      status: 403,
      headers: { ...corsHeaders, "content-type": "text/plain; charset=utf-8" },
    });
  }

  // 4. Ваша ссылка на GitHub
  const GITHUB_RAW_URL = "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/whitelist.m3u";

  try {
    const upstream = await fetch(GITHUB_RAW_URL, { cache: "no-store" });
    if (!upstream.ok) {
      return new Response(`Upstream error: ${upstream.status}`, { status: 502, headers: corsHeaders });
    }

    const body = await upstream.text();

    // 5. Отдаем плейлист с правильными заголовками
    return new Response(body, {
      status: 200,
      headers: {
        ...corsHeaders,
        // Более универсальный Content-Type для M3U
        "content-type": "application/vnd.apple.mpegurl; charset=utf-8",
        "Netlify-CDN-Cache-Control": "public, max-age=300",
        "Cache-Control": "public, max-age=300",
      },
    });
  } catch (err) {
    return new Response(`Proxy error: ${err}`, { status: 500, headers: corsHeaders });
  }
};

export const config: Config = {
  path: "/playlist.m3u",
};
