import logging
import asyncio
from typing import Optional

async def obtener_link_mp4_upnshare(page, url_intermedia: str) -> Optional[str]:
    """
    Interactúa con UpnShare usando el navegador Playwright ya abierto
    para resolver y extraer el enlace final .mp4.
    """
    try:
        logging.info(f"[UpnShare Resolver] Navegando a {url_intermedia}")
        await page.goto(url_intermedia)
        
        # 1. Esperar al botón inicial "Get Video" y darle clic
        btn_get_video = page.locator('button.downloader-button:has-text("Get Video")')
        try:
            await btn_get_video.wait_for(state="attached", timeout=15000)
            
            # Limpiar overlays (anti-adblock / popunders)
            await page.evaluate('''() => {
                document.querySelectorAll('div[style*="z-index:2147483647"]').forEach(e => e.remove());
                document.querySelectorAll('div[style*="z-index: 2147483647"]').forEach(e => e.remove());
            }''')
            
            await btn_get_video.scroll_into_view_if_needed()
            await btn_get_video.click(force=True)
            logging.info("[UpnShare Resolver] Clic en 'Get Video'. Esperando generación de enlace...")
        except Exception as e:
            logging.warning(f"[UpnShare Resolver] No se encontró o falló clic en 'Get Video': {e}")
            return None

        # 2. Esperar a que aparezca el contenedor de botones finales
        container_botones = page.locator('#downloader-button-container')
        try:
            await page.wait_for_function('''() => {
                const btn = document.querySelector('a.downloader-button[download]');
                const hd = document.querySelector('button.downloader-button');
                return btn !== null || (hd && hd.innerText.includes('Headless Detected'));
            }''', timeout=25000)
            
            await container_botones.wait_for(state="attached", timeout=25000)
            await asyncio.sleep(1)
        except Exception as e:
            logging.warning(f"[UpnShare Resolver] No apareció el contenedor final: {e}")
            return None

        # 3. Extraer el enlace del botón "Download"
        btn_download = container_botones.locator('a.downloader-button:has-text("Download")')
        try:
            await btn_download.wait_for(state="attached", timeout=5000)
            enlace_mp4 = await btn_download.get_attribute('href')
            
            if enlace_mp4:
                logging.info(f"[UpnShare Resolver] Éxito! Enlace MP4 extraído: {enlace_mp4}")
                return enlace_mp4.strip()
            else:
                logging.warning("[UpnShare Resolver] El botón 'Download' no tenía atributo href.")
                return None
        except Exception as e:
            logging.warning(f"[UpnShare Resolver] No se pudo extraer el enlace del botón 'Download': {e}")
            return None

    except Exception as e:
        logging.error(f"[UpnShare Resolver] Error crítico procesando URL {url_intermedia}: {e}")
        return None
