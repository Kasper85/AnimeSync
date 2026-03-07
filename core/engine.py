import os
import asyncio
import time
import logging
from tenacity import retry, stop_after_attempt, wait_fixed
from .mediafire_resolver import obtener_link_mp4_mediafire
from .downloader import descargar_video
from providers.base import BaseAnimeProvider

async def procesar_episodio(browser, url_episodio: str, ep: str, serie: str, destino: str, provider: BaseAnimeProvider, session: object, sem: asyncio.Semaphore) -> tuple:
    nombre_archivo = f"{serie}_Cap_{ep}.mp4"
    ruta_completa = os.path.join(destino, nombre_archivo)

    # Evasión de redescargas
    if os.path.exists(ruta_completa):
        peso_mb = os.path.getsize(ruta_completa) / (1024 * 1024)
        if peso_mb > 50.0:
            logging.info(f"⏭️  [Cap {ep}] Ya existe ({peso_mb:.1f} MB).")
            return True, 0, 0, 0
            
    try:
        # Escalonar con semaforo para no lanzar procesos anónimos al mismo milisegundo
        async with sem:
            context = await browser.new_context()
            page = await context.new_page()
            
            async def cerrar_popup(popup): await popup.close()
            page.on('popup', cerrar_popup)

            @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
            async def intentar_obtener_links():
                # INYECCION DE DEPENDENCIA: el provider específico hace su magia
                _enlace_intermedio = await provider.extract_mediafire_link(page, url_episodio)
                if not _enlace_intermedio:
                     return None
                _link_mp4 = await obtener_link_mp4_mediafire(_enlace_intermedio, session)
                if not _link_mp4:
                     return None
                return _link_mp4

            print(f"Buscando enlace para Cap {ep}...")
            t0_enlace = time.time()
            link_mp4 = await intentar_obtener_links()
            
            if not page.is_closed():
                 await page.close()
                 
            if not link_mp4:
                 return False, 0, 0, 0
                 
            tiempo_enlace = time.time() - t0_enlace

        # === Fuera del semáforo: la descarga pesada ===
        print(f"📥 Iniciando descarga: {nombre_archivo}...")
        t0_descarga = time.time()
        
        @retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
        async def intentar_descarga():
           return await descargar_video(link_mp4, serie, nombre_archivo, session)
           
        exito, bytes_descargados = await intentar_descarga()
        tiempo_descarga = time.time() - t0_descarga
        
        await context.close()
        
        if exito:
            print(f"✅ ¡LISTO! {nombre_archivo} descargado.")
            
        return exito, tiempo_enlace, tiempo_descarga, bytes_descargados

    except Exception as e:
        logging.error(f"[Error crítico Cap {ep}] Fallo al procesar: {str(e)}")
        if 'page' in locals() and not page.is_closed():
            await page.close()
        if 'context' in locals():
            await context.close()
        return False, 0, 0, 0
