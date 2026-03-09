import logging
import os

# ==========================================
# CONSTANTES GLOBALES DE CONFIGURACIÓN
# ==========================================

# Tamaño mínimo para considerar un archivo de video como válido (evita re-descargar archivos corruptos)
TAMANIO_MINIMO_VIDEO_MB = 50.0

# Headers HTTP estándar para servidores que requieren autenticación básica
UPNSHARE_HEADERS = {
    "Referer": "https://animetv.upns.live/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def setup_logging():
    """Configura el logger global con handlers para consola y archivo."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Evitar duplicar handlers si se llama más de una vez
    if logger.hasHandlers():
        logger.handlers.clear()

    fmt = logging.Formatter("%(message)s")

    # Handler de consola
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Handler de archivo (persistencia de errores post-ejecución)
    fh = logging.FileHandler("animesync.log", encoding="utf-8")
    fh.setLevel(logging.WARNING)  # Solo guardamos warnings/errores en el archivo
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
