import platform
import os
import logging
import random
from playwright_stealth import Stealth
from utils.network import resolver_ip_dominio, obtener_todas_ips, obtener_ip_fallback

# Instancia global de Stealth (se reutiliza para todos los contextos)
_stealth = Stealth()

# Almacena IPs ya utilizadas para evitar repetirlas
_ips_utilizadas = {}
_ips_bloqueadas = set()

# Límites para evitar memory leaks y acumulación infinita de IPs
_MAX_IPS_POR_DOMINIO = 10
_MAX_IPS_BLOQUEADAS = 20

# Límite seguro para episodios en modo dinámico cuando falla el scraping
_DINAMICO_EPISODIOS_LIMITE = 20

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
        if os.path.exists(ruta_brave):
            return ruta_brave
        ruta_chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(ruta_chrome):
            return ruta_chrome
    elif sistema == 'Linux':
        return "/usr/bin/brave-browser" 
    elif sistema == 'Darwin':
        return "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" 
    return None

async def crear_navegador(playwright_context, dominio_ip: str, ip_excluir: str = None):
    """
    Inicializa el navegador aplicando las reglas de resolución DNS 
    (Google DoH) para saltar bloqueos de operadoras en el dominio base dado.
    
    Args:
        playwright_context: Contexto de Playwright
        dominio_ip: Dominio a resolver
        ip_excluir: IP a excluir (para reintentos con otra IP)
    """
    ruta_navegador = obtener_ruta_navegador()
    argumentos_lanzamiento = {"headless": True, "args": []}
    
    if ruta_navegador:
        argumentos_lanzamiento["executable_path"] = ruta_navegador
    
    # Obtener IP, intentando excluir las que ya fallaron
    ip_resuelta = obtener_ip_para_dominio(dominio_ip, ip_excluir)
    
    if ip_resuelta:
        logging.debug(f"DNS Bypass: {dominio_ip} -> {ip_resuelta}")
        argumentos_lanzamiento["args"].append(f"--host-resolver-rules=MAP {dominio_ip} {ip_resuelta}")
    else:
        logging.warning(f"No se pudo resolver IP para {dominio_ip}")

    browser = await playwright_context.chromium.launch(**argumentos_lanzamiento)
    return browser

def obtener_ip_para_dominio(dominio: str, ip_excluir: str = None) -> str:
    """
    Obtiene una IP válida para el dominio, evitando las bloqueadas y las ya utilizadas.
    """
    # Inicializar lista de IPs utilizadas para este dominio
    if dominio not in _ips_utilizadas:
        _ips_utilizadas[dominio] = []
    
    # Limpiar IPs antiguas si excede el límite (mantener las más recientes)
    if len(_ips_utilizadas[dominio]) > _MAX_IPS_POR_DOMINIO:
        _ips_utilizadas[dominio] = _ips_utilizadas[dominio][-_MAX_IPS_POR_DOMINIO:]
    
    # Intentar obtener IPs del DNS
    ips_dns = obtener_todas_ips(dominio)
    
    # Filtrar IPs ya utilizadas y bloqueadas
    ips_validas = [ip for ip in ips_dns if ip not in _ips_utilizadas[dominio] and ip not in _ips_bloqueadas]
    
    if ips_validas:
        ip_elegida = random.choice(ips_validas)
        _ips_utilizadas[dominio].append(ip_elegida)
        return ip_elegida
    
    # Si no hay IPs del DNS disponibles, intentar con el pool de fallback
    ip_fallback = obtener_ip_fallback(dominio)
    if ip_fallback and ip_fallback != ip_excluir and ip_fallback not in _ips_bloqueadas and ip_fallback not in _ips_utilizadas[dominio]:
        _ips_utilizadas[dominio].append(ip_fallback)
        logging.info(f"Usando IP de fallback para {dominio}: {ip_fallback}")
        return ip_fallback
    
    # Si tenemos IPs utilizadas, devolver una al azar que no sea la excluida
    if _ips_utilizadas[dominio]:
        otras_ips = [ip for ip in _ips_utilizadas[dominio] if ip != ip_excluir]
        if otras_ips:
            return random.choice(otras_ips)
    
    # Último recurso: cualquier IP del DNS
    if ips_dns:
        return ips_dns[0]
    
    # Si todo falla, devolver una IP predeterminada o lanzar excepción
    # En lugar de retornar None que podría causar problemas, usamos una IP de loopback como último recurso
    logging.error(f"No se pudo obtener IP para {dominio}, usando 127.0.0.1 como último recurso")
    return "127.0.0.1"

def marcar_ip_bloqueada(ip: str, dominio: str):
    """Marca una IP como bloqueada para no volver a usarla."""
    global _ips_bloqueadas
    
    # Limpiar IPs antiguas si excede el límite (mantener las más recientes)
    if len(_ips_bloqueadas) > _MAX_IPS_BLOQUEADAS:
        # Eliminar las IPs más antiguas, mantener solo las más recientes
        ips_list = list(_ips_bloqueadas)
        ips_list = ips_list[-_MAX_IPS_BLOQUEADAS:]
        _ips_bloqueadas = set(ips_list)
    
    _ips_bloqueadas.add(ip)
    logging.warning(f"IP {ip} marcada como bloqueada para {dominio}")

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
