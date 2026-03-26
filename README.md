<div align="center">

```
 █████╗ ███╗   ██╗██╗███╗   ███╗███████╗███████╗██╗   ██╗███╗   ██╗ ██████╗ 
██╔══██╗████╗  ██║██║████╗ ████║██╔════╝██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝ 
███████║██╔██╗ ██║██║██╔████╔██║█████╗  ███████╗ ╚████╔╝ ██╔██╗ ██║██║      
██╔══██║██║╚██╗██║██║██║╚██╔╝██║██╔══╝  ╚════██║  ╚██╔╝  ██║╚██╗██║██║      
██║  ██║██║ ╚████║██║██║ ╚═╝ ██║███████╗███████║   ██║   ██║ ╚████║╚██████╗ 
╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝ 
```

**AnimeSync** — an advanced, concurrent, and highly resilient anime scraper with integrated Telegram uploads.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square&logo=python)](https://www.python.org)
[![Playwright](https://img.shields.io/badge/playwright-async-green?style=flat-square&logo=playwright)]()
[![aiohttp](https://img.shields.io/badge/aiohttp-concurrent-red?style=flat-square)]()
[![Telethon](https://img.shields.io/badge/telethon-telegram-blue?style=flat-square&logo=telegram)]()

</div>

---

AnimeSync is a robust CLI tool designed for massive, concurrent episode downloads. Powered by **Architecture Modular v2.1**, it extracts video links safely, bypassing modern anti-bot challenges like Cloudflare (via DoH, custom SNI sockets, and Playwright), and manages downloads entirely asynchronously through an advanced queue system. Now with integrated **Telegram Updater** to upload downloaded episodes directly to Telegram channels.

```bash
╭──────────── Menú Principal ────────────╮
│ 🚀 MULTI-SCRAPER ASÍNCRONO DE ANIME 🚀 │
│         [ AnimeSync v2.1 ]             │
╰────────────────────────────────────────╯

[1] Descargar Serie (AnimeSync)
[2] Subir carpetas a Telegram (Telegram Updater)
[3] Descargar y Subir a Telegram (Juntos)
[4] Salir
```

## ✨ Core Features

- **Interactive Rich Menu** — Beautiful terminal UI powered by [Rich](https://github.com/Textualize/rich) with color-coded output, panels, and structured prompts. No more messy async console interleaving.
- **Massive & Concurrent Downloads** — Uses `aiohttp` and `asyncio.Queue` (Producer-Consumer concurrency model) to fetch and download multiple episodes simultaneously.
- **Advanced Cloudflare & DNS Bypass**:
  - Supports Google **DNS-over-HTTPS (DoH)** to bypass ISP blocks.
  - Custom TLS wrappers to send manual **Server Name Indication (SNI)** headers against raw IPs, avoiding standard HTTP bot protections.
  - Integrates `playwright-stealth` for full headless browser execution when JavaScript challenges are unavoidable.
- **Provider System (Modular)** — Easily extendable architecture to support new sites.
  - Supported: `jkanime.net`, `katanime.com`, `latanime.org`, `monoschino.com`, `animedbs.com`.
- **Direct Link Resolvers** — Connects directly to file hosters, skipping ad-fly links and UI traps automatically.
  - Resolvers include: `mediafire_resolver.py`, `mega_downloader.py`, `upnshare_resolver.py`, `yourupload_resolver.py`, `pixeldrain_resolver.py`.
- **Intelligent Error Engineering** — Features a sophisticated **3-Strike Rule** per series, probe tasks for dynamic episode fetching when counts are unknown, queue-draining cancellation mechanisms, and concurrency limits to avoid bans.
- **Telegram Updater Integration** — Upload downloaded episodes directly to a Telegram channel using multi-worker parallel uploads via Telethon with up to **12 concurrent connections**.

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

### Telegram Updater Setup (Optional)

To use the Telegram upload feature, create a `.env` file inside the `telegram_updater/` folder:

```env
API_ID=12345678
API_HASH=your_api_hash_here
PHONE=+511234567890
CHANNEL=your_channel_username
```

> **Note**: Get your `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org/apps). Your account must be an admin of the target channel.

## 🚀 Usage

```bash
python main.py
```

### Interactive Menu

The application presents a rich interactive menu with **3 modes of operation**:

| Option | Mode | Description |
|--------|------|-------------|
| `[1]` | **Download Only** | Download anime episodes to local folders (classic AnimeSync behavior). |
| `[2]` | **Upload Only** | Select local folders and upload them to a Telegram channel via Telegram Updater. |
| `[3]` | **Download + Upload** | Download episodes first, then automatically upload the results to Telegram — fully automated pipeline. |
| `[4]` | **Exit** | Close the application. |

Follow the prompts to define your target URL and download intentions (complete series vs parts). The engine auto-detects the provider and begins allocating the fetch queue.

---

## 🏗️ Architecture

```text
AnimeSync/
├── main.py                     CLI entry point with rich interactive menu & orchestrator.
├── config.py                   Global settings, provider mappings, and thread counts.
├── core/
│   ├── engine.py               Central node coordinating HTML fetching to video resolvers.
│   ├── downloader.py           Aiohttp streaming downloader w/ chunk retries.
│   ├── browser_manager.py      Playwright context, stealth injection & host bindings.
│   ├── mediafire_resolver.py   Extracts direct video `.mp4` from Mediafire pages.
│   ├── mega_downloader.py      Parses Mega.nz structures via specialized handlers.
│   ├── pixeldrain_resolver.py  PixelDrain direct download resolver.
│   ├── upnshare_resolver.py    UpnShare direct video extractor.
│   └── yourupload_resolver.py  YourUpload iframe & token resolver.
├── providers/
│   ├── base.py                 Abstract BaseAnimeProvider enforcing standard methods.
│   ├── animedbs.py             Site handler for AnimeDbs.
│   ├── jkanime.py              Site handler for JKAnime (uses SNI via raw sockets).
│   ├── katanime.py             Site handler for Katanime.
│   ├── latanime.py             Site handler for LatAnime.
│   └── monoschino.py           Site handler for MonosChino.
├── telegram_updater/
│   ├── main.py                 Telegram uploader orchestrator (standalone or integrated).
│   ├── config.py               Loads Telegram credentials from .env.
│   ├── auth.py                 Interactive login, 2FA, and session management.
│   ├── fast_uploader.py        Multi-worker parallel upload engine (12 concurrent connections).
│   ├── uploader.py             Upload logic with video metadata extraction and retry handling.
│   └── files.py                File discovery, natural sorting, and filtering utilities.
└── utils/
    └── network.py              DoH IP Resolvers, fake headers, global HTTP helpers.
```

## 📌 Requirements

- Python `3.9` or higher.
- A stable internet connection. High concurrency relies heavily on your raw I/O throughput.
- **Optional**: A Telegram account with API credentials for the upload feature.
