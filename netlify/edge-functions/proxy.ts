import type { Config, Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  const url = new URL(request.url);
  
  // Извлекаем имя файла из ссылки (например, /kakoytahren2026.m3u -> kakoytahren2026.m3u)
  const requestedFile = url.pathname.replace(/^\//, "");
  
  // Базовая ссылка на твой репозиторий (она не меняется)
  const GITHUB_BASE = "https://raw.githubusercontent.com/gvineon550-coder/aadfghjuytr/refs/heads/main/";

  // Склеиваем ссылку на GitHub
  const targetUrl = GITHUB_BASE + requestedFile;

  // Делаем редирект
  return Response.redirect(targetUrl, 302);
};

export const config: Config = { path: "/*" };
