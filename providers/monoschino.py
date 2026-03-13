import logging
import re
import urllib.request
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urlparse, parse_qs
from .base import BaseAnimeProvider

class MonoschinoProvider(BaseAnimeProvider):
    name = "Monoschino"
    domain = "monoschino2.com"
    base_url = "https://monoschino2.com"
    priority_servers = ["YourUpload", "Mediafire", "UpnShare", "Mega", "Fembed"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de Monoschino: https://monoschino2.com/ver/uchuu-senkan-yamato-2199-1"""
        match = re.search(r'/ver/([\w-]+)-(\d+)$', url)
        if match:
            return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        
        series_url = series_url.rstrip('/')
        nombre_serie = series_url.split('/')[-1]
        
        try:
            req = urllib.request.Request(series_url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8') # nosec B310
            soup = BeautifulSoup(html, 'html.parser')
            
            cifra_max = 0
            patron = re.compile(rf'/ver/{nombre_serie}-([0-9]+)$')
            for a in soup.find_all('a', href=True):
                m = patron.search(a['href'])
                if m:
                    num = int(m.group(1))
                    if num > cifra_max:
                        cifra_max = num
                        
            if cifra_max > 0:
                end_ep = min(end_ep, cifra_max)
        except Exception as e:
            logging.error(f"[{self.name}] Falló al obtener la lista exacta de episodios, usando rango por defecto: {e}")
            
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(f"{self.base_url}/ver/{nombre_serie}-{ep}")
        return urls

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        await page.goto(episode_url)
        
        try:
            # Esperamos a que los enlaces de descarga estén visibles
            # Basado en el HTML dado: <a class="button is-rounded is-yellow" href="...">
            selector = 'a.button.is-yellow[href*="smart.php?url="]'
            
            # Buscaremos primero si la tabla o los botones están ahí
            # Le damos 10 segundos
            await page.wait_for_selector(selector, timeout=10000)
            
            enlaces = await page.locator(selector).all()
            opciones_descarga = {}
            
            for enlace in enlaces:
                texto = await enlace.inner_text()
                href = await enlace.get_attribute('href')
                
                if href and "url=" in href:
                    # El href es como https://re.animepelix.net/smart.php?url=https://mega.nz/...
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    real_url = qs.get("url", [None])[0]
                    
                    if real_url:
                        servidor = texto.strip().split(' ')[0].lower() # e.g. "Mega.nz" -> "mega.nz", "Fembed" -> "fembed"
                        if "mega" in servidor:
                            # Monoschino sirve URLs como https://mega.nz/!ID!KEY (sin #)
                            # mega.py necesita https://mega.nz/#!ID!KEY (formato V1)
                            # o https://mega.nz/file/ID#KEY (formato V2)
                            if '/file/' not in real_url and '#' not in real_url:
                                # Insertar # antes del primer ! para formato V1
                                real_url = real_url.replace('mega.nz/!', 'mega.nz/#!', 1)
                            opciones_descarga["mega"] = real_url
                        elif "mediafire" in servidor:
                            opciones_descarga["mediafire"] = real_url
                        elif "yourupload" in servidor:
                            opciones_descarga["yourupload"] = real_url
                        elif "fembed" in servidor:
                            opciones_descarga["fembed"] = real_url
                        else:
                            # Por si hay otros servidores
                            opciones_descarga[servidor] = real_url
                            
            if not opciones_descarga:
                return None
                
            # Prioridad de servidores
            opciones_ordenadas = []
            for servidor_ideal in [s.lower() for s in self.priority_servers]:
                if servidor_ideal in opciones_descarga:
                    opciones_ordenadas.append({"url": opciones_descarga[servidor_ideal], "server": servidor_ideal})
                    
            if not opciones_ordenadas:
                servidor_fallback = list(opciones_descarga.keys())[0]
                opciones_ordenadas.append({"url": opciones_descarga[servidor_fallback], "server": servidor_fallback})
                
            return opciones_ordenadas

        except Exception as e:
            logging.error(f"[{self.name}] Falló al buscar opciones de descarga en {episode_url}: {e}")
            return None
