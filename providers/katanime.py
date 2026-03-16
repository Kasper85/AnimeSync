import logging
import re
from typing import List, Optional
from .base import BaseAnimeProvider
from core.browser_manager import _DINAMICO_EPISODIOS_LIMITE

class KatanimeProvider(BaseAnimeProvider):
    name = "Katanime"
    domain = "katanime.net"
    base_url = "https://katanime.net"
    priority_servers = ["Mediafire", "UpnShare", "YourUpload", "Mega"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de Katanime: https://katanime.net/capitulo/ad-police-tv-1/"""
        match = re.search(r'/capitulo/([\w-]+)-(\d+)/?$', url)
        if match:
            return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999, browser=None) -> List[str]:
        import re
        from bs4 import BeautifulSoup
        
        # Formato: https://katanime.net/capitulo/ad-police-tv-1/
        series_url = series_url.rstrip('/')
        nombre_serie = series_url.split('/')[-1]
        
        # Intentar scrapear la página de la serie para obtener el total real
        if end_ep == 9999:
            try:
                html = None
                
                # Usar Playwright si está disponible (bypass DNS)
                if browser:
                    try:
                        page = await browser.new_page()
                        await page.goto(series_url, timeout=15000)
                        html = await page.content()
                        await page.close()
                    except Exception as e:
                        logging.warning(f"[{self.name}] Falló scraping con Playwright: {e}")
                
                # Fallback a urllib si Playwright no está disponible o falló
                if not html:
                    import urllib.request
                    req = urllib.request.Request(series_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')  # nosec B310
                
                soup = BeautifulSoup(html, 'html.parser')
                
                cifra_max = 0
                patron = re.compile(rf'/capitulo/{re.escape(nombre_serie)}-(\d+)/?')
                for a in soup.find_all('a', href=True):
                    m = patron.search(a['href'])
                    if m:
                        num = int(m.group(1))
                        if num > cifra_max:
                            cifra_max = num
                
                if cifra_max > 0:
                    end_ep = min(end_ep, cifra_max)
                    logging.info(f"[{self.name}] Detectados {cifra_max} episodios scrapeando la página.")
                else:
                    logging.warning(f"[{self.name}] No se encontraron episodios. Usando modo dinámico.")
            except Exception as e:
                logging.warning(f"[{self.name}] Falló scraping de la serie: {e}")
                # Limitar a un número razonable de episodios para modo dinámico
                end_ep = _DINAMICO_EPISODIOS_LIMITE  # Límite seguro para evitar miles de URLs inválidas
        
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(f"{self.base_url}/capitulo/{nombre_serie}-{ep}/")
        return urls

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        try:
            logging.info(f"[{self.name} Trace] Empezando con {episode_url}")
            
            # Katanime explota si bloqueamos sus recursos media, por lo que bloqueamos todo menos en ese sitio
            # Sin embargo, como estamos en el método de extracción, configuramos la página (idealmente se hace en el manager,
            # pero aquí garantizamos que se aplique la exclusividad del provider)
            await page.route("**/*", lambda route: route.continue_())
            
            await page.goto(episode_url)
            
            # Chequeo veloz: si aparece el div "not found" o la página 404, retornamos explícitamente None
            # Esto evita que el engine reintente ciegamente esperando un botón que jamás saldrá
            if await page.locator("text='Página no encontrada'").count() > 0 or await page.locator(".error-404").count() > 0:
                logging.info(f"[{self.name} Trace] Episodio no existe (404/Not Found).")
                return None
            
            boton_descarga = page.locator('button.btn-descargar.btn')
            
            try:
                 await boton_descarga.wait_for(state="visible", timeout=6000)
            except Exception:
                 logging.info(f"[{self.name} Trace] Botón de descarga no apareció (posible fin de serie).")
                 return None
            
            # Selector hiper-estricto para evadir botones fantasma o de otros servidores como Mega
            selector_mediafire = 'a.downbtn:has-text("Mediafire")'
            
            # Intentar encontrar Mediafire primero
            intentar_mediafire = True
            for _ in range(3):
                await boton_descarga.click(force=True)
                try:
                    await page.wait_for_selector(selector_mediafire, timeout=3000)
                    break
                except Exception as e:
                    logging.debug(f"Intento {_+1} fallido por: {e}")
            
            enlace_espera = None
            try:
                await page.wait_for_selector(selector_mediafire, timeout=5000)
                enlace_espera = await page.locator(selector_mediafire).first.get_attribute('href')
            except Exception:
                intentar_mediafire = False
                logging.info(f"[{self.name} Trace] No se encontró Mediafire, buscando Mega...")
                
            if intentar_mediafire and enlace_espera:
                logging.info(f"[{self.name} Trace] Navegando a página de espera (Mediafire)...")
                await page.goto(enlace_espera)
                
                selector_linkbutton = '#linkButton'
                try:
                    # Tolerancia radical a la carga de Cloudflare del modal 
                    await page.wait_for_selector(selector_linkbutton, state="attached", timeout=45000)
                    await page.wait_for_function('document.querySelector("#linkButton") && document.querySelector("#linkButton").href.includes("mediafire.com")', timeout=45000)
                except Exception:
                    logging.warning("Timeout esperando #linkButton para Mediafire en Katanime.")
                    return None
                
                enlace_mediafire = await page.locator(selector_linkbutton).get_attribute('href')
                if enlace_mediafire:
                    return {"url": enlace_mediafire.strip(), "server": "mediafire"}
            
            # --- Plan B: MEGA ---
            selector_mega = 'a.downbtn:has-text("Mega")'
            try:
                await page.wait_for_selector(selector_mega, timeout=5000)
                enlace_mega_espera = await page.locator(selector_mega).first.get_attribute('href')
                
                if enlace_mega_espera:
                    logging.info(f"[{self.name} Trace] Navegando a página de espera (Mega)...")
                    await page.goto(enlace_mega_espera)
                    
                    selector_linkbutton_mega = '#linkButton'
                    await page.wait_for_selector(selector_linkbutton_mega, state="attached", timeout=45000)
                    await page.wait_for_function('document.querySelector("#linkButton") && document.querySelector("#linkButton").href.includes("mega.nz")', timeout=45000)
                    
                    enlace_final_mega = await page.locator(selector_linkbutton_mega).get_attribute('href')
                    if enlace_final_mega:
                         return {"url": enlace_final_mega.strip(), "server": "mega"}
            except Exception:
                logging.warning("Timeout o error esperando botón de Mega en Katanime.")
                
            return None

        except Exception as e:
            logging.warning(f"Error procesando katanime.net para {episode_url}: {e}")
            return None
