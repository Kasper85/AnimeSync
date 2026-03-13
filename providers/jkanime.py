from typing import List, Optional
import re
from urllib.parse import urljoin
from .base import BaseAnimeProvider

class JKAnimeProvider(BaseAnimeProvider):
    name = "JKAnime"
    domain = "jkanime.net"
    base_url = "https://jkanime.net"
    priority_servers = ["Mediafire", "UpnShare", "YourUpload", "Mega", "Streamwish", "VOE", "Mp4upload", "Vidhide"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de JKAnime: https://jkanime.net/naruto/1/"""
        # Ignorar si es la URL principal de la serie sin número al final
        match = re.search(r'jkanime\.net/([\w-]+)/(\d+)/?$', url)
        if match:
             return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        if not series_url.endswith('/'):
            series_url += '/'
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(urljoin(series_url, f"{ep}/"))
        return urls

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        import logging
        await page.goto(episode_url)
        
        try:
            boton_descarga = page.locator('#dwld')
            await boton_descarga.wait_for(state="visible", timeout=15000)
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

        except Exception as e:
            logging.error(f"[{self.name}] Falló al buscar opciones de descarga: {e} - posible login requerido o cambio estructural")
            return None

        # Prioridad de servidores
        for servidor_ideal in self.priority_servers:
            if servidor_ideal in opciones_descarga:
                return {"url": opciones_descarga[servidor_ideal], "server": servidor_ideal.lower()}

        servidor_fallback = list(opciones_descarga.keys())[0]
        return {"url": opciones_descarga[servidor_fallback], "server": servidor_fallback.lower()}
