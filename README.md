<div align="center">

```
 █████╗ ███╗   ██╗██╗███╗   ███╗███████╗███████╗██╗   ██╗███╗   ██╗ ██████╗ 
██╔══██╗████╗  ██║██║████╗ ████║██╔════╝██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝ 
███████║██╔██╗ ██║██║██╔████╔██║█████╗  ███████╗ ╚████╔╝ ██╔██╗ ██║██║      
██╔══██║██║╚██╗██║██║██║╚██╔╝██║██╔══╝  ╚════██║  ╚██╔╝  ██║╚██╗██║██║      
██║  ██║██║ ╚████║██║██║ ╚═╝ ██║███████╗███████║   ██║   ██║ ╚████║╚██████╗ 
╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝ 
```

**AnimeSync** — an advanced, concurrent, and highly resilient anime scraper written in Python.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square&logo=python)](https://www.python.org)
[![Playwright](https://img.shields.io/badge/playwright-async-green?style=flat-square&logo=playwright)]()
[![aiohttp](https://img.shields.io/badge/aiohttp-concurrent-red?style=flat-square)]()

</div>

---

AnimeSync is a robust CLI tool designed for massive, concurrent episode downloads. Powered by **Architecture Modular v2.1**, it extracts video links safely, bypassing modern anti-bot challenges like Cloudflare (via DoH, custom SNI sockets, and Playwright), and manages downloads entirely asynchronously through an advanced queue system.

```bash
[INFO] Resolviendo enlaces para: jkanime.net/bna/
[PREPARE] Detectados 12 episodios leyendo texto de la serie.
DNS Bypass activado para: jkanime.net -> 172.67.70.150
▶ --- INICIANDO DESCARGA: CAPÍTULO 1 (bna) ---
▶ --- INICIANDO DESCARGA: CAPÍTULO 2 (bna) ---
🎉 --- PROCESO COMPLETADO --- 🎉
💾 Datos totales descargados : 1988.26 MB
```

## ✨ Core Features

- **Massive & Concurrent Downloads** — Uses `aiohttp` and `asyncio.Queue` (Producer-Consumer concurrency model) to fetch and download multiple episodes simultaneously.
- **Advanced Cloudflare & DNS Bypass**:
  - Supports Google **DNS-over-HTTPS (DoH)** to bypass ISP blocks.
  - Custom TLS wrappers to send manual **Server Name Indication (SNI)** headers against raw IPs, avoiding standard HTTP bot protections.
  - Integrates `playwright-stealth` for full headless browser execution when JavaScript challenges are unavoidable.
- **Provider System (Modular)** — Easily extendable architecture to support new sites.
  - Supported: `jkanime.net`, `katanime.com`, `latanime.org`, `monoschino.com`, `animedbs.com`.
- **Direct Link Resolvers** — Connects directly to file hosters, skipping ad-fly links and UI traps automatically.
  - Resolvers include: `mediafire_resolver.py`, `mega_downloader.py`, `upnshare_resolver.py`, `yourupload_resolver.py`.
- **Intelligent Error Engineering** — Features a sophisticated **3-Strike Rule** per series, probe tasks for dynamic episode fetching when counts are unknown, queue-draining cancellation mechanisms, and concurrency limits to avoid bans.

## 📦 Installation

```bash
git clone https://github.com/Kasper85/AnimeSync.git
cd AnimeSync
# Crear y activar entorno virtual
python -m venv env
env\Scripts\activate
# Instalar dependencias
pip install -r requirements.txt
playwright install chromium
```

Playwright browser binaries are strictly required, as the core occasionally relies on headless Chromium to execute JS-based protections.

## 🚀 Usage

```bash
python main.py
```

### Interactive CLI

```
==============================================
   🚀 MULTI-SCRAPER ASÍNCRONO DE ANIME 🚀   
        [ Arquitectura Modular v2.1 ]         
==============================================

Ingresa la URL principal de la serie (Ej. jkanime.net/naruto):
```

Follow the prompts to define your target URL and download intentions (complete series vs parts). The engine auto-detects the provider and begins allocating the fetch queue.

---

## 🏗️ Architecture

```text
AnimeSync/
├── main.py                     CLI entry point, producer-consumer queue loop & orchestrator.
├── config.py                   Global settings, provider mappings, and thread counts.
├── core/
│   ├── engine.py               Central node coordinating HTML fetching to video resolvers.
│   ├── downloader.py           Aiohttp streaming downloader w/ chunk retries.
│   ├── browser_manager.py      Playwright context, stealth injection & host bindings.
│   ├── mediafire_resolver.py   Extracts direct video `.mp4` from Mediafire pages.
│   ├── mega_downloader.py      Parses Mega.nz structures via specialized handlers.
│   ├── upnshare_resolver.py    UpnShare direct video extractor.
│   └── yourupload_resolver.py  YourUpload iframe & token resolver.
├── providers/
│   ├── base.py                 Abstract BaseAnimeProvider enforcing standard methods.
│   ├── animedbs.py             Site handler for AnimeDbs.
│   ├── jkanime.py              Site handler for JKAnime (uses SNI via raw sockets).
│   ├── katanime.py             Site handler for Katanime.
│   ├── latanime.py             Site handler for LatAnime.
│   └── monoschino.py           Site handler for MonosChino.
└── utils/
    └── network.py              DoH IP Resolvers, fake headers, global HTTP helpers.
```

For more inside details about the code flow, check `technical_specifications.md`.

## 📌 Requirements

- Python `3.9` or higher.
- A stable internet connection. High concurrency relies heavily on your raw I/O throughput.
