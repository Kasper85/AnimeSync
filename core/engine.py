import os
import asyncio
import time
import logging
from tenacity import retry, stop_after_attempt, wait_fixed
from .mediafire_resolver import obtener_link_mp4_mediafire
from .mega_downloader import descargar_video_mega
from .upnshare_resolver import obtener_link_mp4_upnshare
from .downloader import descargar_video
from .browser_manager import crear_pagina_stealth
from providers.base import BaseAnimeProvider
from config import TAMANIO_MINIMO_VIDEO_MB, UPNSHARE_HEADERS

async def procesar_episodio(browser, url_episodio: str, ep: str, serie: str, destino: str, provider: BaseAnimeProvider, session: object, sem: asyncio.Semaphore) -> tuple:
    nombre_archivo = f"{serie}_Cap_{ep}.mp4"
    ruta_completa = os.path.join(destino, nombre_archivo)

    # Evasión de redescargas
    if os.path.exists(ruta_completa):
        peso_mb = os.path.getsize(ruta_completa) / (1024 * 1024)
        if peso_mb > TAMANIO_MINIMO_VIDEO_MB:
            logging.info(f"[SKIP] [Cap {ep}] Ya existe ({peso_mb:.1f} MB).")
            return True, 0, 0, 0

    context = None
    try:
        # Escalonar con semaforo para no lanzar procesos anónimos al mismo milisegundo
        async with sem:
            context, page = await crear_pagina_stealth(browser)

            async def cerrar_popup(popup): await popup.close()
            page.on('popup', cerrar_popup)

            @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
            async def intentar_obtener_links():
                # INYECCION DE DEPENDENCIA: el provider específico hace su magia
                datos_enlace = await provider.obtener_enlace_video(page, url_episodio)
                if not datos_enlace:
                    return None

                server = datos_enlace.get("server", "")
                url = datos_enlace.get("url", "")

                if server == "mediafire":
                    _link_mp4 = await obtener_link_mp4_mediafire(url, session)
                    if not _link_mp4:
                        return None
                    return {"tipo": "http", "url": _link_mp4}
                elif server == "mega":
                    return {"tipo": "mega", "url": url}
                elif server == "upnshare":
                    _link_mp4 = await obtener_link_mp4_upnshare(page, url)
                    if not _link_mp4:
                        return None
                    return {"tipo": "http", "url": _link_mp4, "headers": UPNSHARE_HEADERS}

                return None

            logging.info(f"Buscando enlace para Cap {ep}...")
            t0_enlace = time.time()
            datos_descarga = await intentar_obtener_links()
            tiempo_enlace = time.time() - t0_enlace

        # === Fuera del semáforo: la descarga pesada ===
        if not datos_descarga:
            return False, 0, 0, 0

        logging.info(f"[DOWNLOADING] Iniciando descarga ({datos_descarga['tipo']}): {nombre_archivo}...")
        t0_descarga = time.time()
        exito = False
        bytes_descargados = 0

        if datos_descarga["tipo"] == "http":
            @retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
            async def intentar_descarga_http():
                return await descargar_video(
                    datos_descarga["url"],
                    serie,
                    nombre_archivo,
                    session,
                    headers_extra=datos_descarga.get("headers")
                )
            exito, bytes_descargados = await intentar_descarga_http()

        elif datos_descarga["tipo"] == "mega":
            @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
            async def intentar_descarga_mega():
                res = await asyncio.to_thread(
                    descargar_video_mega, datos_descarga["url"], serie, nombre_archivo, destino
                )
                return res, 0
            exito, bytes_descargados = await intentar_descarga_mega()

        tiempo_descarga = time.time() - t0_descarga

        if exito:
            logging.info(f"[OK] ¡LISTO! {nombre_archivo} descargado.")

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
