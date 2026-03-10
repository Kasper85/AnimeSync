import logging
import re
from typing import List, Optional
from .base import BaseAnimeProvider

class LatAnimeProvider(BaseAnimeProvider):
    name = "LatAnime"
    domain = "latanime.org"
    base_url = "https://latanime.org"
    priority_servers = ["Mediafire", "Mega"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de LatAnime: https://latanime.org/ver/baki-dou-el-samurai-invencible-episodio-1"""
        match = re.search(r'/ver/([\w-]+)-episodio-(\d+)', url)
        if match:
            return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        # Formato: https://latanime.org/ver/baki-dou-el-samurai-invencible-episodio-1
        series_url = series_url.rstrip('/')
        nombre_serie = series_url.split('/')[-1]
        
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
            logging.info(f"No se encontró Mediafire en LatAnime para {episode_url}. Intentando Mega...")
            
        try:
            # Fallback a Mega
            selector_mega = 'a.direct-link[href*="mega.nz"]'
            await page.wait_for_selector(selector_mega, timeout=5000)
            enlace_mega = await page.locator(selector_mega).get_attribute('href')
            if enlace_mega:
                return {"url": enlace_mega.strip(), "server": "mega"}
        except Exception:
            logging.warning(f"Tampoco se encontró Mega en LatAnime para {episode_url}.")
            
        return None
