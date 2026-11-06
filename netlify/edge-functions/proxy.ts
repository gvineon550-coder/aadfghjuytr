import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*",
  };

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  const url = new URL(request.url);
  const pathname = url.pathname; 

  // Извлекаем токен из пути (убираем первый слэш и расширение .m3u)
  // Если ссылка /kakoytahren2026.m3u, то токен будет "kakoytahren2026"
  const providedToken = pathname.replace(/^\//, "").replace(/\.m3u$/, "");

  const EXPECTED_TOKEN = Deno.env.get("MY_SECRET_TOKEN");
  if (!EXPECTED_TOKEN) {
    return new Response("Server configuration error", { status: 500, headers: corsHeaders });
  }

  if (providedToken !== EXPECTED_TOKEN) {
    return new Response("Access denied: invalid or missing token.", {
      status: 403,
      headers: { ...corsHeaders, "content-type": "text/plain; charset=utf-8" },
    });
  }

  const GITHUB_RAW_URL = "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/whitelist.m3u";

  try {
    const upstream = await fetch(GITHUB_RAW_URL, { cache: "no-store" });
    if (!upstream.ok) {
      return new Response(`Upstream error: ${upstream.status}`, { status: 502, headers: corsHeaders });
    }

    const body = await upstream.text();

    return new Response(body, {
      status: 200,
      headers: {
        ...corsHeaders,
        "content-type": "application/vnd.apple.mpegurl; charset=utf-8",
        "Cache-Control": "no-store", // Временно отключаем кэш для чистоты теста
      },
    });
  } catch (err) {
    return new Response(`Proxy error: ${err}`, { status: 500, headers: corsHeaders });
  }
};

export const config: Config = {
  path: "/*", // Теперь функция ловит все запросы, а мы сами разбираем путь
};
