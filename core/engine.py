import os
import asyncio
import time
import logging
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential
from .mediafire_resolver import obtener_link_mp4_mediafire
from .yourupload_resolver import obtener_link_mp4_yourupload
from .mega_downloader import descargar_video_mega
from .upnshare_resolver import obtener_link_mp4_upnshare
from .downloader import descargar_video
from .browser_manager import crear_pagina_stealth, obtener_ip_para_dominio, marcar_ip_bloqueada
from providers.base import BaseAnimeProvider
from config import TAMANIO_MINIMO_VIDEO_MB

async def procesar_episodio(browser, url_episodio: str, ep: str, serie: str, destino: str, provider: BaseAnimeProvider, session: object, sem: asyncio.Semaphore) -> tuple:
    nombre_archivo = f"{serie}_Cap_{ep}.mp4"
    ruta_completa = os.path.join(destino, nombre_archivo)

    # Evasión de redescargas
    if os.path.exists(ruta_completa):
        peso_mb = os.path.getsize(ruta_completa) / (1024 * 1024)
        if peso_mb > TAMANIO_MINIMO_VIDEO_MB:
            logging.info(f"[SKIP] [Cap {ep}] Ya existe ({peso_mb:.1f} MB).")
            return True, 0, 0, 0

    # Semáforo global estático exclusivo para descargas Mega, 1 a la vez para evitar EBLOCKED
    if not hasattr(procesar_episodio, "mega_semaforo"):
        procesar_episodio.mega_semaforo = asyncio.Semaphore(1)

    context = None
    try:
        # Escalonar con semaforo para no lanzar procesos anónimos al mismo milisegundo
        async with sem:
            context, page = await crear_pagina_stealth(browser)

            async def cerrar_popup(popup): await popup.close()
            page.on('popup', cerrar_popup)

            @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
            async def intentar_obtener_links():
                try:
                    # INYECCION DE DEPENDENCIA: el provider específico hace su magia
                    datos_enlace_lista = await provider.obtener_enlace_video(page, url_episodio)
                    if not datos_enlace_lista:
                        return None
                        
                    # Compatibility with older providers that return a single dict instead of list
                    if isinstance(datos_enlace_lista, dict):
                        datos_enlace_lista = [datos_enlace_lista]
                        
                    resultados_extraidos = []
                    for opc in datos_enlace_lista:
                        server = opc.get("server", "")
                        url = opc.get("url", "")
                        
                        try:
                            if server == "mediafire":
                                _link_mp4 = await obtener_link_mp4_mediafire(url, session)
                                if _link_mp4:
                                    resultados_extraidos.append({"tipo": "http", "url": _link_mp4, "server": server})
                            elif server == "yourupload":
                                _link_mp4 = await obtener_link_mp4_yourupload(url, session)
                                if _link_mp4:
                                    resultados_extraidos.append({"tipo": "http", "url": _link_mp4, "headers": {"Referer": "https://www.yourupload.com/"}, "server": server})
                            elif server == "mega":
                                resultados_extraidos.append({"tipo": "mega", "url": url, "server": server})
                            elif server == "upnshare":
                                _link_mp4 = await obtener_link_mp4_upnshare(page, url)
                                if _link_mp4:
                                    ua = await page.evaluate("navigator.userAgent")
                                    cookies_list = await page.context.cookies()
                                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])
                                    
                                    upnshare_dynamic_headers = {
                                        "Referer": page.url,
                                        "User-Agent": ua,
                                        "Cookie": cookie_str
                                    }
                                    
                                    resultados_extraidos.append({"tipo": "http", "url": _link_mp4, "headers": upnshare_dynamic_headers, "server": server})
                        except Exception as parse_e:
                            logging.warning(f"[Engine] Falló servidor secundario {server}: {parse_e}")
                            pass
                            
                    if resultados_extraidos:
                        return resultados_extraidos
                    return None
                except Exception as ex:
                    logging.error(f"[Engine] Fallo subyacente al obtener enlaces para Cap {ep}: {ex}")
                    try:
                        content_preview = (await page.content())[:1000]
                        logging.debug(f"[Engine] Preview de la pagina: {content_preview}")
                        timestamp = int(time.time())
                        screenshot_path = os.path.join(os.getcwd(), f"error_{provider.name}_{serie}_cap{ep}_{timestamp}.png")
                        await page.screenshot(path=screenshot_path)
                        logging.error(f"[Engine] Screenshot guardado en: {screenshot_path}")
                    except Exception as e_ss:
                        logging.error(f"[Engine] No se pudo guardar screenshot: {e_ss}")
                    raise ex

            logging.debug(f"Buscando enlaces para Cap {ep}...")
            t0_enlace = time.time()
            
            # Extraer dominio para gestión de IPs
            dominio = urlparse(url_episodio).netloc
            
            # Intentar obtener enlaces con reintento si falla
            # Nota: El cambio real de IP requiere recrear el navegador (browser_manager)
            # Aquí marcaremos el dominio como problemático para siguientes episodios
            intentos = 0
            max_intentos = 2
            datos_descarga_lista = None
            error_excepcion = False
            ip_excluir = None
            
            while intentos < max_intentos and not datos_descarga_lista:
                 error_excepcion = False
                 try:
                     datos_descarga_lista = await intentar_obtener_links()
                 except Exception as e:
                     error_excepcion = True
                     logging.warning(f"[Cap {ep}] Excepción en intento {intentos + 1}: {e}")
                 
                 if not datos_descarga_lista:
                     # Obtener una IP alternativa para el siguiente intento
                     # (Nota: el cambio real de IP requiere recrear el navegador)
                     ip_to_exclude_next_attempt = obtener_ip_para_dominio(dominio, ip_excluir)
                     
                     intentos += 1
                     if intentos < max_intentos:
                         if error_excepcion:
                             logging.debug(f"[Cap {ep}] Error. Reintento {intentos + 1}/{max_intentos}...")
                         else:
                             logging.debug(f"[Cap {ep}] Sin enlaces. Reintento {intentos + 1}/{max_intentos}...")
                         
                         # Simplemente recargar la página en lugar de cerrar/recrear contexto
                         # Esto evita condiciones de carrera cuando múltiples workers retryan
                         await page.goto("about:blank")
                         await asyncio.sleep(1)
                     
                     # Actualizar ip_excluir para el próximo ciclo
                     ip_excluir = ip_to_exclude_next_attempt
            
            # Log final si fallaron todos los intentos
            if not datos_descarga_lista:
                logging.error(f"[Cap {ep}] Fallaron todos los {max_intentos} intentos de obtener enlaces")
                # Bloquear la última IP usada para que no se use en futuros episodios
                if ip_excluir:
                    marcar_ip_bloqueada(ip_excluir, dominio)
            
            tiempo_enlace = time.time() - t0_enlace

        # === Fuera del semáforo: la descarga pesada ===
        if not datos_descarga_lista:
            return False, 0, 0, 0

        t0_descarga = time.time()
        exito = False
        bytes_descargados = 0
        
        for datos_descarga in datos_descarga_lista:
            logging.debug(f"[DOWNLOADING] Iniciando descarga de proveedor ({datos_descarga['tipo']} - {datos_descarga.get('server', 'unknown')}): {nombre_archivo}...")

            if datos_descarga["tipo"] == "http":
                @retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
                async def intentar_descarga_http():
                    ex_h, b_h = await descargar_video(
                        datos_descarga["url"],
                        serie,
                        nombre_archivo,
                        session,
                        headers_extra=datos_descarga.get("headers")
                    )
                    if not ex_h: raise Exception("Fallo descarga HTTP")
                    return ex_h, b_h
                try:
                    exito, bytes_descargados = await intentar_descarga_http()
                except Exception:
                    exito, bytes_descargados = False, 0
    
            elif datos_descarga["tipo"] == "mega":
                @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
                async def intentar_descarga_mega():
                    async with procesar_episodio.mega_semaforo:
                        res = await asyncio.to_thread(
                            descargar_video_mega, datos_descarga["url"], serie, nombre_archivo, destino
                        )
                    if not res: raise Exception("Fallo descarga Mega")
                    return res, 0
                try:
                    exito, bytes_descargados = await intentar_descarga_mega()
                except Exception:
                    exito, bytes_descargados = False, 0

            if exito:
                break
            else:
                logging.warning(f"[DOWNLOADING] Ocurrió un fallo en origen {datos_descarga.get('server', 'unknown')} para {nombre_archivo}. Pasando al siguiente proveedor si existe...")

        tiempo_descarga = time.time() - t0_descarga

        if exito:
            # Mostrar mensaje limpio con timestamp
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {ep} - Descargado")

        return exito, tiempo_enlace, tiempo_descarga, bytes_descargados

    except Exception as e:
        logging.error(f"[Error crítico Cap {ep}] Fallo al procesar: {str(e)}")
        return False, 0, 0, 0
    finally:
        # Garantizar cierre del contexto del navegador en CUALQUIER caso
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
