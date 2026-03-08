import os
import logging
from mega import Mega

def descargar_video_mega(url: str, serie: str, nombre_archivo: str, destino: str) -> bool:
    """
    Función completametne SÍNCRONA para descargar desde MEGA.
    Se conecta a la URL proveída y guarda el video en la carpeta especificada.
    Al ser síncrona/bloqueante, debe llamarse desde el engine mediante asyncio.to_thread().
    """
    print(f"📥 [MEGA] Iniciando conexión para desencriptar: {nombre_archivo}...")
    try:
        mega = Mega()
        m = mega.login() # Login temporal anónimo
        
        # mega.py prefiere descargar a un directorio
        print(f"📥 [MEGA] Desencriptando y descargando...")
        
        # Descargamos
        archivo_descargado = m.download_url(url, dest_path=destino)
        
        if not archivo_descargado:
             logging.error(f"[MEGA] La librería no devolvió una ruta válida para {nombre_archivo}.")
             return False

        # Renombrar al formato deseado de tu arquitectura
        if os.path.exists(archivo_descargado) and archivo_descargado != os.path.join(destino, nombre_archivo):
            try:
                os.rename(archivo_descargado, os.path.join(destino, nombre_archivo))
            except FileExistsError:
                # Si por algún motivo ya había uno... eliminamos el recién descargado para no saturar.
                os.remove(archivo_descargado)
                return True
            except Exception as e:
                logging.error(f"[MEGA] Fallo al renombrar archivo: {e}")
                return False

        return True
    
    except Exception as e:
        logging.error(f"[MEGA] Fallo crítico descargando {nombre_archivo}: {e}")
        return False
