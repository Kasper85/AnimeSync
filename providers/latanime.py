import logging
import re
from typing import List, Optional
from .base import BaseAnimeProvider
from core.browser_manager import _DINAMICO_EPISODIOS_LIMITE

class LatAnimeProvider(BaseAnimeProvider):
    name = "LatAnime"
    domain = "latanime.org"
    base_url = "https://latanime.org"
    priority_servers = ["Mediafire", "UpnShare", "YourUpload", "Mega"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de LatAnime: https://latanime.org/ver/baki-dou-el-samurai-invencible-episodio-1"""
        match = re.search(r'/ver/([\w-]+)-episodio-(\d+)', url)
        if match:
            return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999, browser=None) -> List[str]:
        import re
        from bs4 import BeautifulSoup
        
        # Formato: https://latanime.org/ver/baki-dou-el-samurai-invencible-episodio-1
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
                patron = re.compile(rf'{re.escape(nombre_serie)}-episodio-(\d+)')
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
                # En caso de fallo, limitar a un número razonable de episodios para modo dinámico
                end_ep = _DINAMICO_EPISODIOS_LIMITE  # Límite seguro para evitar miles de URLs inválidas
        
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(f"{self.base_url}/ver/{nombre_serie}-episodio-{ep}")
        return urls

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        await page.goto(episode_url)
        try:
            # Intentar con Mediafire
            selector_mediafire = 'a.direct-link[href*="mediafire.com"]'
            await page.wait_for_selector(selector_mediafire, timeout=5000)
            enlace = await page.locator(selector_mediafire).get_attribute('href')
            if enlace:
                return {"url": enlace.strip(), "server": "mediafire"}
        except Exception:
            logging.debug(f"No se encontró Mediafire en LatAnime para {episode_url}. Intentando Mega...")
            
        try:
            # Fallback a Mega
            selector_mega = 'a.direct-link[href*="mega.nz"]'
            await page.wait_for_selector(selector_mega, timeout=5000)
            enlace_mega = await page.locator(selector_mega).get_attribute('href')
            if enlace_mega:
                return {"url": enlace_mega.strip(), "server": "mega"}
        except Exception:
            logging.debug(f"Tampoco se encontró Mega en LatAnime para {episode_url}.")
            
        return None
