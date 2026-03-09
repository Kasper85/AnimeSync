import logging
import re
import aiohttp
from typing import List, Optional
from bs4 import BeautifulSoup
from .base import BaseAnimeProvider

class AnimeDbsProvider(BaseAnimeProvider):
    name = "AnimeDbs"
    domain = "animedbs.online"
    base_url = "https://www.animedbs.online"
    priority_servers = ["UpnShare", "Mediafire", "Mega", "voe", "PixelDrain"]
    priority_servers = ["UpnShare", "Mediafire", "Mega", "voe", "PixelDrain"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de AnimeDbs: https://www.animedbs.online/boku-no-hero-...-episodio-10-latino/"""
        # Debe contener la palabra episodio y el dominio
        if "episodio-" in url:
            match = re.search(r'([\w-]+)-episodio-(\d+)', url)
            if match:
                 return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999, session=None) -> List[str]:
        urls = []
        try:
            # Reutilizar la sesión existente si se provee (evita crear dos sesiones HTTP)
            async def _do_fetch(s):
                async with s.get(series_url) as resp:
                    if resp.status != 200:
                        logging.error(f"Error {resp.status} al acceder a la serie AnimeDbs.")
                        return
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    episodios_encontrados = set()
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag['href']
                        if "episodio-" in href and "animedbs.online" in href:
                            episodios_encontrados.add(href)

                    def extract_ep_num(url):
                        match = re.search(r'episodio-(\d+)', url)
                        return int(match.group(1)) if match else 0

                    lista_ordenada = sorted(list(episodios_encontrados), key=extract_ep_num)
                    for url in lista_ordenada:
                        num_ep = extract_ep_num(url)
                        if start_ep <= num_ep <= end_ep:
                            if url not in urls:
                                urls.append(url)

                    if not urls:
                        logging.warning("No se encontraron enlaces scrapeando, usando guessing de URLs (puede fallar).")
                        slug_base = series_url.rstrip('/').split('/')[-1].replace('anime-', '')
                        for ep in range(start_ep, end_ep + 1):
                            urls.append(f"{self.base_url}/{slug_base}-episodio-{ep}-latino-hd/")

            if session is not None:
                await _do_fetch(session)
            else:
                async with aiohttp.ClientSession() as s:
                    await _do_fetch(s)

        except Exception as e:
            logging.error(f"Error parseando lista AnimeDbs: {e}")

        return urls

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        try:
            logging.info(f"[{self.name} Trace] Navegando a {episode_url}")
            
            # AnimeDbs puede tener protección básica, intentamos no bloquear demasiadas cosas
            # await page.route("**/*", lambda route: route.continue_())
            await page.goto(episode_url, timeout=30000)
            
            # Buscar el contenedor con los botones de servidor
            selector_servidores = 'div.soraurlx'
            try:
                 await page.wait_for_selector(selector_servidores, timeout=10000)
            except Exception as wait_e:
                 logging.info(f"[{self.name} Trace] No se encontró el recuadro de servidores: {wait_e}")
                 print(f"[{self.name} Trace] No se encontró el recuadro de servidores: {wait_e}")
                 return None
                 
            # Extraer todos los enlaces dentro del div
            enlaces_tag = await page.locator(f'{selector_servidores} a').all()
            opciones_descarga = {}
            
            for a_tag in enlaces_tag:
                 texto = await a_tag.inner_text()
                 href = await a_tag.get_attribute('href')
                 if texto and href:
                     opciones_descarga[texto.strip()] = href.strip()
                     
            if not opciones_descarga:
                 logging.info(f"[{self.name} Trace] Div soraurlx vacío de enlaces.")
                 print(f"[{self.name} Trace] Div soraurlx vacío de enlaces.")
                 return None
                 
            # Priorizar servidores según config
            for servidor_ideal in self.priority_servers:
                # Búsqueda case-insensitive
                for serv_disponible, url_serv in opciones_descarga.items():
                    if servidor_ideal.lower() in serv_disponible.lower():
                        logging.info(f"[{self.name} Trace] Seleccionado servidor: {serv_disponible}")
                        # Mapear a identificadores internos conocidos
                        if "upnshare" in serv_disponible.lower():
                            return {"url": url_serv, "server": "upnshare"}
                        elif "mediafire" in serv_disponible.lower():
                            return {"url": url_serv, "server": "mediafire"}
                        elif "mega" in serv_disponible.lower():
                            return {"url": url_serv, "server": "mega"}
                        else:
                            return {"url": url_serv, "server": serv_disponible.lower()}
            
            # Fallback al primero si no match
            primer_servidor = list(opciones_descarga.keys())[0]
            url_primer = opciones_descarga[primer_servidor]
            logging.info(f"[{self.name} Trace] Fallback servidor: {primer_servidor}")
            
            if "upnshare" in primer_servidor.lower(): 
                 return {"url": url_primer, "server": "upnshare"}
            elif "mediafire" in primer_servidor.lower():
                 return {"url": url_primer, "server": "mediafire"}
                 
            return {"url": url_primer, "server": primer_servidor.lower()}

        except Exception as e:
            logging.error(f"Error procesando {self.domain} para {episode_url}: {e}")
            return None
