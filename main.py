import os
import sys
import asyncio
import time
import logging
import aiohttp
from playwright.async_api import async_playwright

if sys.platform == 'win32' and sys.stdout and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from config import setup_logging
from providers import get_provider_for_url
from core.browser_manager import crear_navegador
from core.engine import procesar_episodio

# Iniciar configuración de loggers
setup_logging()

async def run_scraper():
    print("==============================================")
    print("   🚀 MULTI-SCRAPER ASÍNCRONO DE ANIME 🚀   ")
    print("        [ Arquitectura Modular v2.0 ]         ")
    print("==============================================")
    
    url_base = input("\nIngresa la URL principal de la serie (Ej. jkanime.net/naruto): ").strip()
    if not url_base:
        logging.error("No se ingresó ninguna URL.")
        return
        
    try:
        provider = get_provider_for_url(url_base)
    except ValueError as e:
        logging.error(str(e))
        return
        
    print(f"✅ Sitio detectado y soportado por provider: {provider.name}")
    
    modo = input("¿Deseas descargar toda la serie desde el cap 1? (s/n): ").strip().lower()
    if modo == 'n':
        ep_inicio = int(input("Ingresa el episodio INICIAL (ej. 10): "))
        ep_fin = int(input("Ingresa el episodio FINAL (ej. 24): "))
    else:
        ep_inicio = 1
        ep_fin = 9999 
        
    print("\n[INFO] Determinando lista de episodios...")
    # Delegamos al provider cómo generar o raspar las URLs válidas para esta serie
    try:
        urls_episodios = await provider.get_episode_list(url_base, ep_inicio, ep_fin)
        print(f"[PREPARE] URLs obtenidas: {urls_episodios}")
    except Exception as e:
        logging.error(f"Fallo al construir URLs para la serie: {e}")
        return
        
    if not urls_episodios:
        logging.error("La lista de episodios está vacía.")
        return
        
    # Obtener un nombre de serie base para las carpetas 
    nombre_serie = [p for p in url_base.rstrip('/').split('/') if p][-1]
    ruta_destino = os.path.join(os.getcwd(), nombre_serie)
    os.makedirs(ruta_destino, exist_ok=True)
    
    # Empaquetamos en formato Tarea
    tareas_iniciales = []
    for i, url in enumerate(urls_episodios, start=ep_inicio):
        print(f"[PREPARE] Añadiendo tarea Ep {i}: {url}")
        tareas_iniciales.append({
            "url": url,
            "ep": str(i),
            "serie": nombre_serie,
            "destino": ruta_destino,
            "provider": provider,
            "fin_dinamico": ep_fin == 9999
        })
        
    print(f"[PREPARE] Total tareas iniciales: {len(tareas_iniciales)}")
        
    async with async_playwright() as p:
        # Browser inyectando reglas de bypass de DNS para el dominio del provider
        browser = await crear_navegador(p, provider.domain)
        
        # Objeto de control de concurrencia para evitar saturar protección anti-bot (ej. Katanime a Max 2 por vez)
        limite_concurrencia = 2 if provider.name == "Katanime" else 10
        sem_nav = asyncio.Semaphore(limite_concurrencia)
        
        connector = aiohttp.TCPConnector(limit=0) # Sin limite de conexiones TCP simultaneas
        async with aiohttp.ClientSession(connector=connector) as session:

            cola_tareas = asyncio.Queue(maxsize=10)
            estado = {
                "series_canceladas": set(),  # Set de O(1) para purgar hilos sobrantes de series 404
                "total_bytes": 0,
                "total_tiempo_enlaces": 0,
                "total_tiempo_descargas": 0,
                "tiempo_inicio": time.time(),
                "descargas": {"exitos": set(), "fallos": set()}
            }
    
            async def worker(worker_id):
                while True:
                    tarea = await cola_tareas.get()
                    print(f"[{worker_id}] Tarea obtenida: {tarea['ep']} - URL: {tarea['url']}")
                    try:
                        # Aborte ultra-rápido en O(1) si la serie topó pared 404
                        if tarea['serie'] in estado["series_canceladas"]:
                            print(f"[{worker_id}] Serie cancelada, saltando: {tarea['serie']}")
                            continue
                            
                        print(f"[{worker_id}] Iniciando descarga: CAPÍTULO {tarea['ep']} ({tarea['serie']}) - {tarea['url']}")
                        logging.info(f"\n▶ --- INICIANDO DESCARGA: CAPÍTULO {tarea['ep']} ({tarea['serie']}) ---")
                        
                        resultado, t_enlaces, t_descarga, b_descargados = await procesar_episodio(
                            browser, 
                            tarea['url'], 
                            tarea['ep'], 
                            tarea['serie'], 
                            tarea['destino'], 
                            tarea['provider'], 
                            session, 
                            sem_nav
                        )
    
                        if not resultado and tarea['fin_dinamico']:
                            logging.info(f"🛑 [Cap {tarea['ep']}] No encontrado tras reintentos. Finalizando proceso de serie.")
                            estado["series_canceladas"].add(tarea['serie'])
                            
                        else:
                            if resultado:
                                estado["total_bytes"] += b_descargados
                                estado["total_tiempo_enlaces"] += t_enlaces
                                estado["total_tiempo_descargas"] += t_descarga
                                estado["descargas"]["exitos"].add(tarea['ep'])
                            else:
                                estado["descargas"]["fallos"].add(tarea['ep'])
                    finally:
                        cola_tareas.task_done()
    
            # Numero maximo de workers paralelos a desplegar
            num_workers = 10
            workers = [asyncio.create_task(worker(i)) for i in range(num_workers)]
    
            for tarea in tareas_iniciales:
                await cola_tareas.put(tarea)
                 
            # Esperamos a drenar la cola
            await cola_tareas.join()
            
            for w in workers:
                w.cancel()

        tiempo_total_app = time.time() - estado["tiempo_inicio"]
        megas_totales = estado["total_bytes"] / (1024 * 1024)
        
        logging.info(f"\n🎉 --- PROCESO COMPLETADO --- 🎉")
        print("\n" + "="*50)
        print("📊 ESTADÍSTICAS FINALES 📊")
        print("="*50)
        print(f"⏱️ Tiempo total de ejecución : {tiempo_total_app:.2f} segundos")
        print(f"⏱️ Tiempo extracción enlaces : {estado['total_tiempo_enlaces']:.2f} segundos")
        print(f"⏱️ Tiempo de descarga videos : {estado['total_tiempo_descargas']:.2f} segundos")
        print(f"💾 Datos totales descargados : {megas_totales:.2f} MB")
        print("="*50 + "\n")
        
        exitos = sorted([int(x) if str(x).isdigit() else x for x in estado["descargas"]["exitos"]], key=lambda x: (isinstance(x, str), x))
        fallos = sorted([int(x) if str(x).isdigit() else x for x in estado["descargas"]["fallos"]], key=lambda x: (isinstance(x, str), x))
        
        if fallos:
            print(f"[❌] Faltan los capítulos: {', '.join(map(str, fallos))}")
        elif exitos:
            if all(isinstance(x, int) for x in exitos) and exitos == list(range(min(exitos), max(exitos) + 1)):
                rango_str = f"({min(exitos)}-{max(exitos)})" if len(exitos) > 1 else f"({exitos[0]})"
                print(f"[✔️] Todos los capítulos descargados {rango_str}.")
            else:
                print(f"[✔️] Todos los capítulos solicitados fueron descargados.")
        else:
            print(f"[⚠️] No se procesó ninguna descarga.")

        await browser.close()

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_scraper())
        finally:
            loop.run_until_complete(loop.shutdown_default_executor())
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            
    except KeyboardInterrupt:
        logging.error("\n[Abortado] Detenido por el usuario.")
    except ValueError:
        logging.error("\n[Error] Por favor, ingresa números válidos.")