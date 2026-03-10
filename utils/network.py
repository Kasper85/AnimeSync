import urllib.request
import json
import logging

def resolver_ip_dominio(dominio: str) -> str:
    """Resuelve la IP de cualquier dominio usando Google DoH para saltar bloqueos de operadoras."""
    try:
        req = urllib.request.Request(f'https://dns.google/resolve?name={dominio}&type=A')
        with urllib.request.urlopen(req, timeout=5) as response:  # nosec
            data = json.loads(response.read().decode())
            ips = [ans['data'] for ans in data.get('Answer', []) if ans['type'] == 1]
            if ips:
                return ips[0]
    except Exception as e:
        logging.warning(f"Buscador DNS falló para {dominio}: {e}")
    return None
