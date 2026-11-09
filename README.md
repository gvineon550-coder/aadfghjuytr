# 📺 VK Live IPTV

[![VK Live Auto-Update](https://github.com/gvineon550-coder/aadfghjuytr/actions/workflows/vk_update.yml/badge.svg)](https://github.com/gvineon550-coder/aadfghjuytr/actions/workflows/vk_update.yml)

Автоматический плейлист VK Live с ленивым резолвингом через Netlify Edge.

## Как это работает

- **GitHub Actions** — раз в 6 часов собирает список каналов из VK-категории.
- **Netlify Edge** — на лету получает свежую мастер-ссылку из VK API.
- **IPTV-плеер** — получает вечную ссылку и играет без протухания токенов.

## Файлы

- `vk_config.json` — категории и ручные каналы
- `vk_updater.py` — сборщик плейлиста
- `vk_live.m3u` — сгенерированный плейлист
- `netlify/edge-functions/proxy.ts` — Edge-функция резолвера

## Плейлист

https://incomparable-hamster-974986.netlify.app/vk_live.m3u
