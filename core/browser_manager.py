import platform
import os
import logging
from playwright.async_api import async_playwright
from utils.network import resolver_ip_dominio

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
