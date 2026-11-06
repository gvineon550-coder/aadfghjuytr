import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const url = new URL(request.url);
  const pathname = url.pathname; 
  
  // Извлекаем токен из пути (например, /kakoytahren2026.m3u -> kakoytahren2026)
  const providedToken = pathname.replace(/^\//, "").replace(/\.m3u$/, "");
  const EXPECTED_TOKEN = Deno.env.get("MY_SECRET_TOKEN");

  if (!EXPECTED_TOKEN) {
    return new Response("Server configuration error", { status: 500 });
  }

  // Если пароль неверный — блокируем
  if (providedToken !== EXPECTED_TOKEN) {
    return new Response("Access denied: invalid or missing token.", {
      status: 403,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  // Ваша прямая ссылка на GitHub
  const GITHUB_RAW_URL = "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/whitelist.m3u";

  // Если пароль верный — делаем редирект (302) прямо на GitHub
  return Response.redirect(GITHUB_RAW_URL, 302);
};

export const config: Config = {
  path: "/*",
};
