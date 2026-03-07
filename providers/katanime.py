import logging
from typing import List, Optional
from urllib.parse import urljoin
from .base import BaseAnimeProvider

class KatanimeProvider(BaseAnimeProvider):
    name = "Katanime"
    domain = "katanime.net"
    base_url = "https://katanime.net"
    priority_servers = ["Mediafire"]
    supports_dub = True

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        # Formato: https://katanime.net/capitulo/ad-police-tv-1/
        series_url = series_url.rstrip('/')
        nombre_serie = series_url.split('/')[-1]
        
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(f"{self.base_url}/capitulo/{nombre_serie}-{ep}/")
        return urls

    async def extract_mediafire_link(self, page, episode_url: str) -> Optional[str]:
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
            
            for _ in range(3):
                await boton_descarga.click(force=True)
                try:
                    await page.wait_for_selector(selector_mediafire, timeout=3000)
                    break
                except Exception:
                    pass
            
            await page.wait_for_selector(selector_mediafire, timeout=5000)
            enlace_espera = await page.locator(selector_mediafire).first.get_attribute('href')
            
            if not enlace_espera:
                return None
                
            logging.info(f"[{self.name} Trace] Navegando a página de espera...")
            await page.goto(enlace_espera)
            
            selector_linkbutton = '#linkButton'
            try:
                # Tolerancia radical a la carga de Cloudflare del modal 
                await page.wait_for_selector(selector_linkbutton, state="attached", timeout=45000)
                await page.wait_for_function('document.querySelector("#linkButton") && document.querySelector("#linkButton").href.includes("mediafire.com")', timeout=45000)
            except Exception as wait_e:
                logging.warning(f"Timeout esperando #linkButton para Mediafire en Katanime.")
                return None
            
            enlace_mediafire = await page.locator(selector_linkbutton).get_attribute('href')
            return enlace_mediafire.strip() if enlace_mediafire else None
            
        except Exception as e:
            logging.warning(f"Error procesando katanime.net para {episode_url}: {e}")
            return None
