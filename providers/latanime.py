import logging
from typing import List, Optional
from urllib.parse import urljoin
from .base import BaseAnimeProvider

class LatAnimeProvider(BaseAnimeProvider):
    name = "LatAnime"
    domain = "latanime.org"
    base_url = "https://latanime.org"
    priority_servers = ["Mediafire"]
    supports_dub = True

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        # Formato: https://latanime.org/ver/baki-dou-el-samurai-invencible-episodio-1
        series_url = series_url.rstrip('/')
        nombre_serie = series_url.split('/')[-1]
        
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(f"{self.base_url}/ver/{nombre_serie}-episodio-{ep}")
        return urls

    async def extract_mediafire_link(self, page, episode_url: str) -> Optional[str]:
        await page.goto(episode_url)
        try:
            selector_mediafire = 'a.direct-link[href*="mediafire.com"]'
            await page.wait_for_selector(selector_mediafire, timeout=10000)
            enlace = await page.locator(selector_mediafire).get_attribute('href')
            return enlace.strip() if enlace else None
        except Exception as e:
            logging.warning(f"No se encontró Mediafire en LatAnime para {episode_url}.")
            return None
