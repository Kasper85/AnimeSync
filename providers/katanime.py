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
                    # Generar URLs directamente sin verificación adicional
                    urls = []
                    for ep in range(start_ep, end_ep + 1):
                        urls.append(f"{self.base_url}/capitulo/{nombre_serie}-{ep}/")
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
                
                # Fallback final: usar límite reducido para evitar sobrecarga
                end_ep = min(_DINAMICO_EPISODIOS_LIMITE, 30)
        
        # Verificar cada URL antes de agregarla (para evitar 404)
        urls = []
        for ep in range(start_ep, end_ep + 1):
            url = f"{self.base_url}/capitulo/{nombre_serie}-{ep}/"
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
        
        page = None
        try:
            html = None
            if browser:
                try:
                    page = await browser.new_page()
                    await page.goto(url, timeout=10000)
                    html = await page.content()
                except Exception as e:
                    logging.debug(f"[{self.name}] Error al verificar {url}: {e}")
                finally:
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
                'reproducir', 'player', 'ver', 'descargar', 'servidor', 'descarga'
            ])
            
            return tiene_player
            
        except Exception as e:
            logging.debug(f"[{self.name}] Excepción al verificar {url}: {e}")
            return False
        finally:
            # Asegurar cierre de página
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass

    async def _probar_episodios_dinamico(self, browser, nombre_serie: str, start_ep: int = 1) -> List[str]:
        """
        Método de sondeo adaptativo: prueba episodios secuencialmente hasta encontrar
        3 episodios consecutivos que no existen.
        """
        from bs4 import BeautifulSoup
        import urllib.request
        
        urls_encontradas = []
        max_sondeo = 30  # Reducido de 50 a 30 para evitar sobrecarga
        fallos_consecutivos = 0
        
        logging.info(f"[{self.name}] Iniciando sondeo adaptativo desde episodio {start_ep}...")
        
        for ep in range(start_ep, start_ep + max_sondeo):
            url = f"{self.base_url}/capitulo/{nombre_serie}-{ep}"
            page = None
            
            try:
                html = None
                if browser:
                    try:
                        page = await browser.new_page()
                        await page.goto(url, timeout=10000)
                        html = await page.content()
                    except Exception as e:
                        logging.debug(f"[{self.name}] Error en episodio {ep}: {e}")
                    finally:
                        if page and not page.is_closed():
                            try:
                                await page.close()
                            except Exception:
                                pass
                
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
                            'reproducir', 'player', 'ver', 'descargar', 'servidor', 'descarga'
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

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        """Obtiene el enlace de video usando priority_servers para priorizar."""
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
            
            # Mapeo de servidores a selectores
            server_selectors = {
                "Mediafire": 'a.downbtn:has-text("Mediafire")',
                "Mega": 'a.downbtn:has-text("Mega")',
            }
            
            # Recopilar todos los servidores disponibles
            opciones_disponibles = []
            for server_name in self.priority_servers:
                if server_name in server_selectors:
                    selector = server_selectors[server_name]
                    # Intentar hacer clic y buscar el servidor
                    for _ in range(3):
                        try:
                            await boton_descarga.click(force=True)
                            await page.wait_for_selector(selector, timeout=3000)
                            # Verificar que el elemento es visible
                            if await page.locator(selector).first.is_visible():
                                opciones_disponibles.append(server_name)
                                logging.debug(f"[{self.name}] Encontrado servidor: {server_name}")
                                break
                        except Exception:
                            pass
            
            if not opciones_disponibles:
                logging.warning(f"[{self.name}] No se encontraron servidores disponibles en {episode_url}")
                return None
            
            # Priorizar según priority_servers del provider
            for servidor_ideal in self.priority_servers:
                if servidor_ideal in opciones_disponibles:
                    return await self._get_link_for_server(page, servidor_ideal, boton_descarga)
            
            # Fallback: usar el primer servidor disponible
            return await self._get_link_for_server(page, opciones_disponibles[0], boton_descarga)
            
        except Exception as e:
            logging.warning(f"Error procesando katanime.net para {episode_url}: {e}")
            return None
    
    async def _get_link_for_server(self, page, server_name: str, boton_descarga):
        """Obtiene el enlace final para un servidor específico."""
        selector = 'a.downbtn:has-text("' + server_name + '")'
        
        try:
            # Click para revelar el botón del servidor
            for _ in range(3):
                try:
                    await boton_descarga.click(force=True)
                    await page.wait_for_selector(selector, timeout=3000)
                    if await page.locator(selector).first.is_visible():
                        break
                except Exception:
                    pass
            
            enlace_espera = await page.locator(selector).first.get_attribute('href')
            if not enlace_espera:
                logging.warning(f"[{self.name}] No se pudo obtener enlace para {server_name}")
                return None
            
            logging.info(f"[{self.name} Trace] Navegando a página de espera ({server_name})...")
            await page.goto(enlace_espera)
            
            # Obtener enlace final (página intermedia tiene #linkButton)
            selector_linkbutton = '#linkButton'
            await page.wait_for_selector(selector_linkbutton, state="attached", timeout=45000)
            
            # Verificar que el enlace corresponde al servidor esperado
            if server_name == "Mediafire":
                await page.wait_for_function(
                    'document.querySelector("#linkButton") && document.querySelector("#linkButton").href.includes("mediafire.com")', 
                    timeout=45000
                )
            elif server_name == "Mega":
                await page.wait_for_function(
                    'document.querySelector("#linkButton") && document.querySelector("#linkButton").href.includes("mega.nz")', 
                    timeout=45000
                )
            
            enlace_final = await page.locator(selector_linkbutton).get_attribute('href')
            if enlace_final:
                logging.info(f"[{self.name}] Seleccionado {server_name} (prioridad configurada)")
                return {"url": enlace_final.strip(), "server": server_name.lower()}
            
        except Exception as e:
            logging.warning(f"Timeout o error esperando botón de {server_name} en Katanime: {e}")
        
        return None
