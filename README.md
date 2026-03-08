<div align="center">

```
 █████╗ ███╗   ██╗██╗███╗   ███╗███████╗    ██████╗ ██╗     
██╔══██╗████╗  ██║██║████╗ ████║██╔════╝    ██╔══██╗██║     
███████║██╔██╗ ██║██║██╔████╔██║█████╗      ██║  ██║██║     
██╔══██║██║╚██╗██║██║██║╚██╔╝██║██╔══╝      ██║  ██║██║     
██║  ██║██║ ╚████║██║██║ ╚═╝ ██║███████╗    ██████╔╝███████╗
╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚═╝╚══════╝    ╚═════╝ ╚══════╝
```

**Anime Downloader** — a powerful, fast, and modular asynchronous anime scraper written in Python.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square&logo=python)](https://www.python.org)
[![Playwright](https://img.shields.io/badge/playwright-async-green?style=flat-square&logo=playwright)]()
[![aiohttp](https://img.shields.io/badge/aiohttp-concurrent-red?style=flat-square)]()

</div>

---

Anime Downloader is a robust CLI tool designed for massive, concurrent episode downloads. Powered by an **Architecture Modular v2.0**, it safely extracts video links bypassing modern anti-bot challenges and manages downloads entirely asynchronously.

```bash
[INFO] Resolviendo enlaces para: jkanime.net/naruto
[INFO] Bypassing Cloudflare... done.
▶ --- INICIANDO DESCARGA: CAPÍTULO 1 (naruto) ---
▶ --- INICIANDO DESCARGA: CAPÍTULO 2 (naruto) ---
🎉 --- PROCESO COMPLETADO --- 🎉
💾 Datos totales descargados : 450.20 MB
```

## Features

- **Massive & Concurrent Downloads** — Uses `aiohttp` and `asyncio` to fetch episodes simultaneously, maximizing your bandwidth.
- **Provider System** — Easily extendable architecture to support new websites. Out-of-the-box support for `jkanime`, `katanime`, and `latanime`.
- **Browser Automation & Bypass** — Integrates with `playwright` to intercept network requests, execute JavaScript, and bypass complex anti-bot walls (e.g. Cloudflare).
- **Direct Link Resolvers** — Specific support to traverse hosters like Mediafire and Mega (`mediafire_resolver.py`, `mega_downloader.py`), skipping ads automatically.
- **Advanced Error & Ban Management** — Concurrency limits, semaphores to avoid targeted IP blocking, and automatic retry mechanisms for failed chunks.

## Installation

```bash
git clone https://github.com/yourusername/anime-downloader.git
cd anime-downloader
pip install -r requirements.txt
playwright install chromium
```

Playwright browser binaries are strictly required, as the core relies on headless Chromium to bypass sophisticated protections.

## Usage

### Interactive CLI

```bash
python main.py
```

```
==============================================
   🚀 MULTI-SCRAPER ASÍNCRONO DE ANIME 🚀   
        [ Arquitectura Modular v2.0 ]         
==============================================

Ingresa la URL principal de la serie (Ej. jkanime.net/naruto):
```

Follow the prompts to define your target URL, starting episode, and ending episode. The scraper will configure the right provider and begin the job.

---

# Architecture

```text
anime downloader/
├── main.py                     CLI entry point and asynchronous worker orchestrator.
├── config.py                   Global variables and logging setup.
├── core/
│   ├── engine.py               Scraping orchestrator + download delegator.
│   ├── downloader.py           Asynchronous MP4 payload downloader.
│   ├── browser_manager.py      Playwright lifecycle and fingerprinting.
│   ├── mediafire_resolver.py   Mediafire bypass logic.
│   └── mega_downloader.py      Mega.nz direct link fallback integration.
├── providers/
│   ├── base.py                 Standard Provider interface.
│   ├── jkanime.py              Provider mapping for jkanime.net
│   ├── katanime.py             Provider mapping for katanime.net
│   └── latanime.py             Provider mapping for latanime.org
└── utils/
    └── network.py              Network helpers and HTTP headers.
```

## Requirements

- Python `3.9` or higher.
- A stable internet connection. High concurrency relies on fast I/O throughput. 
