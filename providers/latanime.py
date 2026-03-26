import asyncio
import logging
import re
from typing import List, Optional
from .base import BaseAnimeProvider
from core.browser_manager import _DINAMICO_EPISODIOS_LIMITE

class LatAnimeProvider(BaseAnimeProvider):
    name = "LatAnime"
    domain = "latanime.org"
    base_url = "https://latanime.org"
    priority_servers = ["Mediafire", "UpnShare", "YourUpload", "PixelDrain", "Mega"]
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
                
                # Crear un browser propio para scraping (bypass de Cloudflare)
                try:
                    from playwright.async_api import async_playwright
                    from core.browser_manager import crear_pagina_stealth, crear_navegador
                    
                    async with async_playwright() as p:
                        scrape_browser = await crear_navegador(p, self.domain)
                        context, page = await crear_pagina_stealth(scrape_browser)
                        
                        # Navigate and wait for load
                        await page.goto(series_url, timeout=30000)
                        
                        # Wait for Cloudflare
                        await page.wait_for_timeout(5000)
                        
                        html = await page.content()
                        
                        await context.close()
                        await scrape_browser.close()
                        
                        logging.info(f"[{self.name}] Scraping completado exitosamente.")
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
                    
                    # Generar URLs directamente sin verificar (ya scrapeamos la página)
                    urls = []
                    for ep in range(start_ep, end_ep + 1):
                        url = f"{self.base_url}/ver/{nombre_serie}-episodio-{ep}"
                        urls.append(url)
                    return urls
                else:
                    logging.warning(f"[{self.name}] No se encontraron episodios. Usando modo dinámico.")
            except Exception as e:
                logging.warning(f"[{self.name}] Falló scraping de la serie: {e}")
                # Intentar modo de sondeo adaptativo
                if browser:
                    try:
                        urls_sondeo = await self._probar_episodios_dinamico(browser, nombre_serie, start_ep)
                        if urls_sondeo:
                            logging.info(f"[{self.name}] Sondeo adaptativo encontró {len(urls_sondeo)} episodios.")
                            return urls_sondeo
                    except Exception as probe_error:
                        logging.warning(f"[{self.name}] Falló sondeo adaptativo: {probe_error}")
                
                # Fallback final
                end_ep = _DINAMICO_EPISODIOS_LIMITE
        
        # Validar cada URL antes de agregarla (para evitar 404)
        urls = []
        for ep in range(start_ep, end_ep + 1):
            url = f"{self.base_url}/ver/{nombre_serie}-episodio-{ep}"
            # Probar si la URL existe antes de agregarla
            if await self._verificar_episodio_existe(url, browser):
                urls.append(url)
            else:
                logging.debug(f"[{self.name}] Episodio {ep} no existe (404), deteniendo búsqueda.")
                break  # Detener si encontramos un episodio que no existe
        
        return urls

    async def _verificar_episodio_existe(self, url: str, browser) -> bool:
        """Verifica si un episodio existe (no devuelve 404 y tiene contenido de reproductor)"""
        import urllib.request
        from bs4 import BeautifulSoup
        
        try:
            html = None
            if browser:
                try:
                    page = await browser.new_page()
                    await page.goto(url, timeout=10000)
                    html = await page.content()
                    await page.close()
                except Exception as e:
                    logging.debug(f"[{self.name}] Error al verificar {url}: {e}")
                    if page and not page.is_closed():
                        await page.close()
            
            if not html:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                try:
                    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                except:
                    return False
            
            soup = BeautifulSoup(html, 'html.parser')
            texto_pagina = soup.get_text().lower()
            
            # Detectar si la página indica que el episodio no existe
            no_existe = any(palabra in texto_pagina for palabra in [
                'no encontrada', 'no encontrado', '404', 'error 404',
                'no se encontró', 'no existe', 'capitulo no disponible',
                'episode not found', 'page not found'
            ])
            
            if no_existe:
                return False
            
            # Verificar que tenga contenido de reproductor
            tiene_player = any(palabra in texto_pagina for palabra in [
                'reproducir', 'player', 'ver', 'descargar', 'servidor'
            ])
            
            return tiene_player
            
        except Exception as e:
            logging.debug(f"[{self.name}] Excepción al verificar {url}: {e}")
            return False

    async def _probar_episodios_dinamico(self, browser, nombre_serie: str, start_ep: int = 1) -> List[str]:
        """
        Método de sondeo adaptativo: prueba episodios secuencialmente hasta encontrar
        3 episodios consecutivos que no existen.
        """
        import re
        from bs4 import BeautifulSoup
        import urllib.request
        
        urls_encontradas = []
        max_sondeo = 100  # Máximo episodios a probar
        fallos_consecutivos = 0
        
        logging.info(f"[{self.name}] Iniciando sondeo adaptativo desde episodio {start_ep}...")
        
        for ep in range(start_ep, start_ep + max_sondeo):
            url = f"{self.base_url}/ver/{nombre_serie}-episodio-{ep}"
            
            try:
                html = None
                if browser:
                    try:
                        page = await browser.new_page()
                        await page.goto(url, timeout=10000)
                        html = await page.content()
                        await page.close()
                    except Exception as e:
                        logging.debug(f"[{self.name}] Error en episodio {ep}: {e}")
                        if page and not page.is_closed():
                            await page.close()
                
                if not html:
                    # Fallback a urllib
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    try:
                        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                    except:
                        pass
                
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    texto_pagina = soup.get_text().lower()
                    
                    # Detectar si la página indica que el episodio no existe
                    no_existe = any(palabra in texto_pagina for palabra in [
                        'no encontrada', 'no encontrado', '404', 'error 404',
                        'no se encontró', 'no existe', 'capitulo no disponible',
                        'episode not found', 'page not found'
                    ])
                    
                    if not no_existe:
                        # Verificar que tenga contenido de reproductor
                        tiene_player = any(palabra in texto_pagina for palabra in [
                            'reproducir', 'player', 'ver', 'descargar', 'servidor'
                        ])
                        
                        if tiene_player:
                            urls_encontradas.append(url)
                            logging.debug(f"[{self.name}] Episodio {ep} encontrado: {url}")
                            fallos_consecutivos = 0
                        else:
                            # Página existe pero no tiene reproductor - posible fin
                            fallos_consecutivos += 1
                    else:
                        fallos_consecutivos += 1
                else:
                    fallos_consecutivos += 1
                
                # Si 3 episodios consecutivos no existen, detener
                if fallos_consecutivos >= 3:
                    logging.info(f"[{self.name}] Detectados 3 episodios consecutivos sin contenido. Serie finalizada en episodio {ep - 2}")
                    break
                
            except Exception as e:
                logging.debug(f"[{self.name}] Excepción probando episodio {ep}: {e}")
                fallos_consecutivos += 1
                if fallos_consecutivos >= 3:
                    break
        
        return urls_encontradas

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[list]:
        """Obtiene la lista de enlaces de video usando priority_servers para ordenar."""
        await page.goto(episode_url)
        
        # Mapeo de servidores a selectores
        server_selectors = {
            "Mediafire": 'a.direct-link[href*="mediafire.com"]',
            "Mega": 'a.direct-link[href*="mega.nz"]',
            "PixelDrain": 'a.direct-link[href*="pixeldrain.com"]',
            "YourUpload": 'a.direct-link[href*="yourupload.com"]',
            "UpnShare": 'a.direct-link[href*="upnstream.com"]',
        }
        
        # Recopilar todos los servidores disponibles
        opciones_descarga = {}
        for server_name, selector in server_selectors.items():
            try:
                await page.wait_for_selector(selector, timeout=3000)
                enlace = await page.locator(selector).get_attribute('href')
                if enlace:
                    opciones_descarga[server_name] = enlace.strip()
                    logging.debug(f"[{self.name}] Encontrado {server_name}: {enlace[:50]}...")
            except Exception:
                pass  # Servidor no disponible, continuar
        
        if not opciones_descarga:
            logging.warning(f"[{self.name}] No se encontraron servidores disponibles en {episode_url}")
            return None
        
        resultados = []
        
        # Priorizar según priority_servers del provider
        for servidor_ideal in self.priority_servers:
            if servidor_ideal in opciones_descarga:
                resultados.append({"url": opciones_descarga[servidor_ideal], "server": servidor_ideal.lower()})
                del opciones_descarga[servidor_ideal]
        
        # Agregar los restantes que no estaban en priority_servers (si los hay)
        for nombre_servidor, enlace in opciones_descarga.items():
            resultados.append({"url": enlace, "server": nombre_servidor.lower()})
            
        return resultados
