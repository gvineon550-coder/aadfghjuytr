import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const url = new URL(request.url);
  const requestedFile = url.pathname.replace(/^\//, "");
  
  // Получаем User-Agent (приводим к нижнему регистру для удобства)
  const ua = (request.headers.get("user-agent") || "").toLowerCase();

  // 1. Проверяем, не является ли это известным браузером
  const browserSignatures = ["chrome", "safari", "firefox", "edg", "opr", "yabrowser"];
  const isBrowser = browserSignatures.some(sig => ua.includes(sig));

  // 2. Проверяем, не является ли это известным плеером 
  // (нужно, так как некоторые плееры на Android используют встроенный Chrome)
  const playerSignatures = ["vlc", "tivimate", "ott", "kodi", "exoplayer", "lavf", "mxplayer", "wink", "ssiptv", "perfect"];
  const isPlayer = playerSignatures.some(sig => ua.includes(sig));

  // Если это браузер, но НЕ плеер — блокируем
  if (isBrowser && !isPlayer) {
    return new Response(
      "⛔ Доступ запрещен.\n\nЭта ссылка предназначена только для IPTV-плееров (Televizo, OTT Navigator, VLC и др.). Пожалуйста, откройте её в вашем приложении для просмотра ТВ.", 
      {
        status: 403,
        headers: { "content-type": "text/plain; charset=utf-8" },
      }
    );
  }

  // Если это плеер (или неизвестный клиент) — делаем редирект на GitHub
  const GITHUB_BASE = "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/";
  return Response.redirect(GITHUB_BASE + requestedFile, 302);
};

export const config: Config = { path: "/*" };
