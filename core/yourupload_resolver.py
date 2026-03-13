import logging
import re
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urljoin

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def obtener_link_mp4_yourupload(url_intermedia: str, session) -> str:
    """Extrae el enlace directo .mp4 de YourUpload usando Aiohttp."""
    try:
        if not url_intermedia:
            return None
            
        logging.info(f"[YourUpload] Navegando a {url_intermedia}")
        
        # 1. Obtener la página inicial (/watch/... o /download...)
        # Si ya es de tipo download?file=... con token, la devolvemos tal cual? (Probablemente no).
        async with session.get(url_intermedia, allow_redirects=True, timeout=15) as res1:
            if res1.status != 200:
                logging.warning(f"[YourUpload] Falló página watch: HTTP {res1.status}")
                return None
            html1 = await res1.text()
            
        download_page_url = None
        
        # Caso 1: Estábamos en /watch/... Buscamos el botón de ir a la página de descarga
        if "/watch/" in url_intermedia:
            match_download_btn = re.search(r'href=["\'](/download\?file=\d+)["\']', html1)
            if match_download_btn:
                download_page_url = urljoin("https://www.yourupload.com", match_download_btn.group(1))
            else:
                # Intento alternativo por si está en un og:video y sirve
                match_og = re.search(r'property="og:video" content="(https?://[^"]+)"', html1)
                if match_og:
                    return match_og.group(1)
        # Caso 2: Ya estábamos en la página /download?...
        elif "/download?" in url_intermedia:
            download_page_url = url_intermedia
            
        if not download_page_url:
            logging.warning("[YourUpload] No se encontró el enlace a la página de descarga.")
            return None
            
        logging.info(f"[YourUpload] Navegando a la página de descarga: {download_page_url}")
        
        # 2. Obtener la página de descarga para extraer el data-url
        fetch_url = download_page_url if download_page_url != url_intermedia else None
        
        if fetch_url:
            async with session.get(fetch_url, allow_redirects=True, timeout=15) as res2:
                if res2.status != 200:
                    logging.warning(f"[YourUpload] Falló página download: HTTP {res2.status}")
                    return None
                html2 = await res2.text()
        else:
            html2 = html1 # Ya estábamos en la página de descarga

        # Extraemos data-url del botón final: <a href="#" data-url="/download?file=...&sendFile=true&token=..."
        match_data_url = re.search(r'data-url=["\']([^"\']+)["\']', html2)
        if match_data_url:
            data_url = match_data_url.group(1).replace('&amp;', '&').replace('\r', '').replace('\n', '').strip()
            final_mp4_url = urljoin("https://www.yourupload.com", data_url)
            
            # Verificamos rápidamente si el server nos dará un 500 para evitar crasheos en downloader
            # y forzar un fallback al siguiente servidor en engine.py
            try:
                async with session.head(final_mp4_url, headers={"Referer": "https://www.yourupload.com/"}, allow_redirects=True, timeout=10) as h_res:
                    if h_res.status in [200, 206]:
                        logging.info(f"[YourUpload] Éxito! Enlace final extraído: {final_mp4_url}")
                        return final_mp4_url
                    else:
                        logging.warning(f"[YourUpload] Falló enlace final generado (Http {h_res.status}). Abortando para fallback.")
                        return None
            except Exception as e_head:
                logging.warning(f"[YourUpload] Falló pre-verificación de enlace (posible caída): {e_head}")
                return None
            
            
        # Fallback si por alguna razón no está en `data-url` sino en `href` de un .mp4
        match_mp4 = re.search(r'href=["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html2)
        if match_mp4:
            return match_mp4.group(1)
            
        logging.warning("[YourUpload] No se pudo encontrar el data-url ni enlace .mp4")
        return None

    except Exception as e:
        logging.error(f"[YourUpload Resolver Error] {str(e)}")
        return None
