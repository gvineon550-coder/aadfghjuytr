import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const url = new URL(request.url);
  const pathname = url.pathname;

  // ⚡ Lazy Resolver для VK Live
  // Плеер запрашивает /vk-stream/{username}, мы на лету получаем свежий поток
  if (pathname.startsWith("/vk-stream/")) {
    const username = pathname.replace("/vk-stream/", "").replace(/\/$/, "");
    if (!username) {
      return new Response("No channel name", { status: 400 });
    }

    const apiUrl =
      `https://api.live.vkvideo.ru/v1/blog/${username}/public_video_stream`;

    try {
      const res = await fetch(apiUrl, {
        headers: {
          "Origin": "https://live.vkvideo.ru",
          "Referer": `https://live.vkvideo.ru/${username}`,
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
                        "AppleWebKit/537.36 (KHTML, like Gecko) " +
                        "Chrome/120.0.0.0 Safari/537.36",
          "Accept": "application/json, text/plain, */*",
        },
      });

      if (!res.ok) {
        return new Response(`VK API error: ${res.status}`, {
          status: 502,
          headers: { "Cache-Control": "no-store" },
        });
      }

      const data = await res.json();

      if (!data.isOnline) {
        return new Response(`Channel ${username} is offline`, {
          status: 404,
          headers: { "Cache-Control": "no-store" },
        });
      }

      const streams = data.data?.[0]?.playerUrls || [];

      // 🎯 Ищем мастер-ссылку (live_hls — это и есть master playlist)
      const liveStream =
        streams.find((s: any) => s.type === "live_hls") ||
        streams.find((s: any) => s.type === "live_playback_hls");

      if (liveStream?.url) {
        // Cache-Control: no-store — чтобы плеер не запоминал редирект
        return new Response(null, {
          status: 302,
          headers: {
            "Location": liveStream.url,
            "Cache-Control": "no-store",
          },
        });
      }

      return new Response("No stream URL in response", {
        status: 404,
        headers: { "Cache-Control": "no-store" },
      });
    } catch (e: any) {
      return new Response(`Error: ${e.message}`, {
        status: 500,
        headers: { "Cache-Control": "no-store" },
      });
    }
  }

  // 🛡️ Старая логика для статических плейлистов (whitelist.m3u и т.д.)
  const requestedFile = pathname.replace(/^\//, "");
  const ua = (request.headers.get("user-agent") || "").toLowerCase();

  const browserSignatures = [
    "chrome", "safari", "firefox", "edg", "opr", "yabrowser"
  ];
  const isBrowser = browserSignatures.some(sig => ua.includes(sig));

  const playerSignatures = [
    "vlc", "tivimate", "ott", "kodi", "exoplayer",
    "lavf", "mxplayer", "wink", "ssiptv", "perfect"
  ];
  const isPlayer = playerSignatures.some(sig => ua.includes(sig));

  if (isBrowser && !isPlayer) {
    return new Response(
      "⛔ Доступ запрещен.\n\nЭта ссылка предназначена только для IPTV-плееров.",
      {
        status: 403,
        headers: { "content-type": "text/plain; charset=utf-8" },
      }
    );
  }

  const GITHUB_BASE =
    "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/";
  return Response.redirect(GITHUB_BASE + requestedFile, 302);
};

export const config: Config = { path: "/*" };
