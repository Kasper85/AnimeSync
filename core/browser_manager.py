import platform
import os
import logging
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from utils.network import resolver_ip_dominio

# Instancia global de Stealth (se reutiliza para todos los contextos)
_stealth = Stealth()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
]

HEADERS = {
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Upgrade-Insecure-Requests": "1",
}

def obtener_ruta_navegador() -> str:
    sistema = platform.system()
    if sistema == 'Windows':
        ruta_brave = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        if os.path.exists(ruta_brave): return ruta_brave
        ruta_chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(ruta_chrome): return ruta_chrome
    elif sistema == 'Linux':
        return "/usr/bin/brave-browser" 
    elif sistema == 'Darwin':
        return "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" 
    return None

async def crear_navegador(playwright_context, dominio_ip: str):
    """
    Inicializa el navegador aplicando las reglas de resolución DNS 
    (Google DoH) para saltar bloqueos de operadoras en el dominio base dado.
    """
    ruta_navegador = obtener_ruta_navegador()
    argumentos_lanzamiento = {"headless": True, "args": []}
    
    if ruta_navegador:
        argumentos_lanzamiento["executable_path"] = ruta_navegador
        
    ip_resuelta = resolver_ip_dominio(dominio_ip)
    if ip_resuelta:
        logging.info(f"DNS Bypass activado para: {dominio_ip} -> {ip_resuelta}")
        argumentos_lanzamiento["args"].append(f"--host-resolver-rules=MAP {dominio_ip} {ip_resuelta}")

    browser = await playwright_context.chromium.launch(**argumentos_lanzamiento)
    return browser

async def crear_pagina_stealth(browser) -> tuple:
    """
    Crea un nuevo contexto y página de Playwright con Stealth, User-Agent real y Headers aplicado.
    Devuelve (context, page) para que el caller pueda cerrarlos correctamente.
    """
    ua = random.choice(USER_AGENTS)
    context = await browser.new_context(user_agent=ua, extra_http_headers=HEADERS)
    page = await context.new_page()
    await _stealth.apply_stealth_async(page)
    return context, page
