import os
import logging
import threading
from mega import Mega

# Candado global para Mega, ya que la librería mega.py (específicamente la desencriptación CBC) 
# NO es hilo-segura y causa WinError 32 o colisión de variables al crear archivos temporales concurrentes.
_mega_lock = threading.Lock()

def descargar_video_mega(url: str, serie: str, nombre_archivo: str, destino: str) -> bool:
    """
    Función completamente SÍNCRONA para descargar desde MEGA.
    Se conecta a la URL proveída y guarda el video en la carpeta especificada.
    Al ser síncrona/bloqueante, debe llamarse desde el engine mediante asyncio.to_thread().
    """
    print(f"📥 [MEGA] Añadiendo a la cola estricta: {nombre_archivo}...")
    
    with _mega_lock:
        print(f"📥 [MEGA] Iniciando conexión para desencriptar: {nombre_archivo}...")
        print(f"📥 [MEGA] URL recibida: {url}")
        try:
            # Silenciar la librería mega para que no imprima progreso de bytes "X of Y downloaded"
            logging.getLogger("mega").setLevel(logging.CRITICAL)
            
            mega = Mega()
            m = mega.login() # Login temporal anónimo
            
            # mega.py prefiere descargar a un directorio y hace un print intrusivo, lo silenciamos
            import sys
            from contextlib import redirect_stdout
            import io
            
            with io.StringIO() as buf, redirect_stdout(buf):
                # Descargamos
                archivo_descargado = m.download_url(url, dest_path=destino, dest_filename=nombre_archivo)
                
            if not archivo_descargado:
                 logging.error(f"[MEGA] La librería no devolvió una ruta válida para {nombre_archivo}.")
                 return False

            return True
        
        except Exception as e:
            logging.error(f"[MEGA] Fallo crítico descargando {nombre_archivo}: {e}")
            return False
