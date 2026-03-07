from typing import List, Optional
from urllib.parse import urljoin
from .base import BaseAnimeProvider

class JKAnimeProvider(BaseAnimeProvider):
    name = "JKAnime"
    domain = "jkanime.net"
    base_url = "https://jkanime.net"
    priority_servers = ["Mediafire", "Mega", "Streamwish", "VOE", "Mp4upload", "Vidhide"]
    supports_dub = True

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        if not series_url.endswith('/'):
            series_url += '/'
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(urljoin(series_url, f"{ep}/"))
        return urls

    async def extract_mediafire_link(self, page, episode_url: str) -> Optional[str]:
        await page.goto(episode_url)
        
        boton_descarga = page.locator('#dwld')
        await boton_descarga.wait_for(state="visible")
        await boton_descarga.click()
        
        try:
            await page.wait_for_selector('table tbody tr', timeout=4000)
        except Exception:
            await boton_descarga.click(force=True)
            await page.wait_for_selector('table tbody tr', timeout=10000)
        
        filas = await page.locator('table tbody tr:not(:first-child)').all()
        opciones_descarga = {}
        
        for fila in filas:
            celdas = await fila.locator('td').all()
            if len(celdas) >= 4:
                servidor = await celdas[0].inner_text()
                enlace = await celdas[3].locator('a').get_attribute('href')
                opciones_descarga[servidor.strip()] = enlace
                
        if not opciones_descarga:
            return None

        # Prioridad de servidores
        for servidor_ideal in self.priority_servers:
            if servidor_ideal in opciones_descarga:
                return opciones_descarga[servidor_ideal]

        servidor_fallback = list(opciones_descarga.keys())[0]
        return opciones_descarga[servidor_fallback]
