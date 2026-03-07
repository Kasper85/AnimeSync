import logging
import re
from tenacity import retry, stop_after_attempt, wait_fixed

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def obtener_link_mp4_mediafire(url_intermedia, session):
    """Extrae el .mp4 asíncronamente vía Aiohttp y Regex sin usar recursos de navegador gráfico."""
    try:
        if not url_intermedia or "mediafire.com" not in url_intermedia:
            return None
            
        async with session.get(url_intermedia, allow_redirects=True, timeout=15) as respuesta:
            if respuesta.status != 200:
                return None
                
            html = await respuesta.text()
            
            # Buscar el enlace directo en el HTML estático de la página
            # Mediafire lo expone normalmente como: href="https://download[número].mediafire.com/..."
            match = re.search(r'href="(https?://download[^"]+)"', html)
            if match:
                return match.group(1)
            
            # Segunda opción menos probable: botón envuelto o string en JS
            match_js = re.search(r'window\.location\.href\s*=\s*[\'"](https?://download[^\'"]+)[\'"]', html)
            if match_js:
                return match_js.group(1)
            
            logging.warning(f"No se encontró enlace directo de Mediafire en el HTML: {url_intermedia}")
            return None

    except Exception as e:
        logging.error(f"[Mediafire Fast Extractor Error] {str(e)}")
        return None