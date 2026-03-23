import urllib.request
import json
import logging
import random

# Pool de IPs conocidas por funcionar para cada dominio
# Se usarán como fallback cuando la resolución DNS falle o dé problemas
# Nota: Estas IPs fueron verificadas en marzo 2026. Revisar periódicamente.
IP_POOL = {
    "jkanime.net": [
        "104.26.10.188", "104.26.11.188", "104.26.12.188",
        "172.64.146.117", "172.64.155.117", "172.64.156.117",
        "172.67.70.150", "172.67.71.150", "172.67.72.150"
    ],
    "animeflv.net": ["104.21.47.100", "172.64.144.100"],
    "latanime.org": ["104.21.74.227", "172.67.164.15"],
}

def obtener_todas_ips(dominio: str) -> list:
    """Obtiene todas las IPs disponibles para un dominio usando Google DoH."""
    try:
        req = urllib.request.Request(f'https://dns.google/resolve?name={dominio}&type=A')
        with urllib.request.urlopen(req, timeout=5) as response:  # nosec
            data = json.loads(response.read().decode())
            ips = [ans['data'] for ans in data.get('Answer', []) if ans['type'] == 1]
            return ips
    except Exception as e:
        logging.warning(f"Buscador DNS falló para {dominio}: {e}")
    return []

def obtener_ip_fallback(dominio: str) -> str:
    """Obtiene una IP del pool predefinido como fallback."""
    if dominio in IP_POOL:
        return random.choice(IP_POOL[dominio])
    return None

def resolver_ip_dominio(dominio: str) -> str:
    """Resuelve la IP de cualquier dominio usando Google DoH para saltar bloqueos de operadoras.
    Intenta primero con DNS dinámico, luego con pool de IPs conocidas."""
    # Intentar resolución DNS normal primero
    ips = obtener_todas_ips(dominio)
    if ips:
        return ips[0]
    
    # Fallback al pool de IPs conocidas
    logging.warning(f"DNS falló para {dominio}, usando pool de IPs conocidas")
    ip_fallback = obtener_ip_fallback(dominio)
    if ip_fallback:
        logging.info(f"Usando IP de fallback para {dominio}: {ip_fallback}")
        return ip_fallback
    
    return None
