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
    print("        [ AnimeSync v2.1 ]         ")
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
    
    # Delegamos al provider para saber si pegaron un episodio aislado
    info_episodio = provider.extract_episode_info(url_base)
    
    es_dinamico = False
    
    if info_episodio:
        print(f"\n📌 Has ingresado la URL de UN SOLO episodio (Cap {info_episodio['ep_num']}). Se descargará individualmente.")
        ep_inicio = info_episodio['ep_num']
        ep_fin = ep_inicio
        urls_episodios = [url_base]
        nombre_serie = info_episodio.get('serie', 'descarga_suelta')
        
    else:
        modo = input("¿Deseas descargar toda la serie desde el cap 1? (s/n): ").strip().lower()
        if modo == 'n':
            ep_inicio = int(input("Ingresa el episodio INICIAL (ej. 10): "))
            ep_fin = int(input("Ingresa el episodio FINAL (ej. 24): "))
        else:
            ep_inicio = 1
            ep_fin = 9999 
            
        print("\n[INFO] Determinando lista de episodios...")
        try:
            urls_episodios = await provider.get_episode_list(url_base, ep_inicio, ep_fin)
            
            # Si el provider devolvió una lista razonable (scrapeó la página), usarla tal cual
            if ep_fin == 9999 and len(urls_episodios) < 9000:
                ep_fin = ep_inicio + len(urls_episodios) - 1
                print(f"[PREPARE] El provider detectó {len(urls_episodios)} episodios.")
            elif ep_fin == 9999:
                # El provider no pudo detectar el total (modo ciego) -> activar modo dinámico
                es_dinamico = True
                print(f"[PREPARE] No se pudo detectar el total de episodios. Modo dinámico activado.")
            else:
                print(f"[PREPARE] {len(urls_episodios)} episodios en rango solicitado.")
                
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
    
    if es_dinamico:
        print(f"\n[PREPARE] Buscando dinámicamente episodios desde el cap {ep_inicio} en adelante...")
    else:
        print(f"\n[PREPARE] Total de tareas: {len(urls_episodios)} (Caps {ep_inicio} al {ep_fin})")
        
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
                "descargas": {"exitos": set(), "fallos": set()},
                "ultimo_ep_exitoso": 0,     # Track del último episodio exitoso (para stats limpias)
            }
    
            async def worker(worker_id):
                while True:
                    tarea = await cola_tareas.get()
                    try:
                        # Aborte ultra-rápido en O(1) si la serie topó pared 404
                        if tarea['serie'] in estado["series_canceladas"]:
                            continue
                            
                        print(f"[{worker_id}] Tarea obtenida: {tarea['ep']} - URL: {tarea['url']}")
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
    
                        if not resultado:
                            estado["descargas"]["fallos"].add(tarea['ep'])
                            
                            # Lógica de 3 fallos consecutivos para series dinámicas
                            if tarea.get('fin_dinamico') and str(tarea['ep']).isdigit():
                                fallos_ints = {int(x) for x in estado["descargas"]["fallos"] if str(x).isdigit()}
                                ep_int = int(tarea['ep'])
                                
                                if (ep_int - 2 in fallos_ints and ep_int - 1 in fallos_ints and ep_int in fallos_ints) or \
                                   (ep_int - 1 in fallos_ints and ep_int in fallos_ints and ep_int + 1 in fallos_ints) or \
                                   (ep_int in fallos_ints and ep_int + 1 in fallos_ints and ep_int + 2 in fallos_ints):
                                    logging.info(f"🛑 [Cap {ep_int}] 3 fallos consecutivos detectados. Finalizando búsqueda para la serie.")
                                    estado["series_canceladas"].add(tarea['serie'])
                                    
                                    # Vaciar la cola para evitar que workers procesen más caps
                                    while not cola_tareas.empty():
                                        try:
                                            cola_tareas.get_nowait()
                                            cola_tareas.task_done()
                                        except asyncio.QueueEmpty:
                                            break
                                else:
                                    logging.info(f"⚠️ [Cap {ep_int}] Falló pero no se aborta la serie aún (regla de 3 fallos).")
                            
                        else:
                            estado["total_bytes"] += b_descargados
                            estado["total_tiempo_enlaces"] += t_enlaces
                            estado["total_tiempo_descargas"] += t_descarga
                            estado["descargas"]["exitos"].add(tarea['ep'])
                            
                            # Actualizar el último episodio exitoso
                            if str(tarea['ep']).isdigit():
                                ep_int = int(tarea['ep'])
                                if ep_int > estado["ultimo_ep_exitoso"]:
                                    estado["ultimo_ep_exitoso"] = ep_int
                    finally:
                        cola_tareas.task_done()
    
            # Numero maximo de workers paralelos a desplegar
            num_workers = 10
            workers = [asyncio.create_task(worker(i)) for i in range(num_workers)]
    
            # === PRODUCTOR: alimentar la cola de tareas ===
            for i, url in enumerate(urls_episodios, start=ep_inicio):
                # CLAVE: Si la serie fue cancelada, dejar de meter tareas inmediatamente
                if nombre_serie in estado["series_canceladas"]:
                    break
                    
                tarea = {
                    "url": url,
                    "ep": str(i),
                    "serie": nombre_serie,
                    "destino": ruta_destino,
                    "provider": provider,
                    "fin_dinamico": es_dinamico
                }
                await cola_tareas.put(tarea)
                 
            try:
                # Esperamos a drenar la cola
                await cola_tareas.join()
            except asyncio.CancelledError:
                logging.warning("\n[Abortado] Detenido por el usuario durante las descargas.")
            finally:
                for w in workers:
                    w.cancel()

        tiempo_total_app = time.time() - estado["tiempo_inicio"]
        megas_totales = estado["total_bytes"] / (1024 * 1024)
        
        logging.info("\n🎉 --- PROCESO COMPLETADO --- 🎉")
        print("\n" + "="*50)
        print("📊 ESTADÍSTICAS FINALES 📊")
        print("="*50)
        print(f"⏱️ Tiempo total de ejecución : {tiempo_total_app:.2f} segundos")
        print(f"⏱️ Tiempo extracción enlaces : {estado['total_tiempo_enlaces']:.2f} segundos")
        print(f"⏱️ Tiempo de descarga videos : {estado['total_tiempo_descargas']:.2f} segundos")
        print(f"💾 Datos totales descargados : {megas_totales:.2f} MB")
        print("="*50 + "\n")
        
        exitos = sorted([int(x) if str(x).isdigit() else x for x in estado["descargas"]["exitos"]], key=lambda x: (isinstance(x, str), x))
        fallos_raw = sorted([int(x) if str(x).isdigit() else x for x in estado["descargas"]["fallos"]], key=lambda x: (isinstance(x, str), x))
        
        # En modo dinámico, solo mostrar fallos REALES (dentro del rango de éxitos), 
        # no los caps de sondeo que fallaron porque la serie ya terminó
        if es_dinamico and estado["ultimo_ep_exitoso"] > 0:
            fallos = [f for f in fallos_raw if isinstance(f, int) and f <= estado["ultimo_ep_exitoso"]]
        else:
            fallos = fallos_raw
        
        if fallos:
            print(f"[❌] Faltan los capítulos: {', '.join(map(str, fallos))}")
        elif exitos:
            if all(isinstance(x, int) for x in exitos) and exitos == list(range(min(exitos), max(exitos) + 1)):
                rango_str = f"({min(exitos)}-{max(exitos)})" if len(exitos) > 1 else f"({exitos[0]})"
                print(f"[✔️] Todos los capítulos descargados {rango_str}.")
            else:
                print("[✔️] Todos los capítulos solicitados fueron descargados.")
        else:
            print("[⚠️] No se procesó ninguna descarga.")

        await browser.close()

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        main_task = loop.create_task(run_scraper())
        
        try:
            loop.run_until_complete(main_task)
        except KeyboardInterrupt:
            main_task.cancel()
            try:
                loop.run_until_complete(main_task)
            except asyncio.CancelledError:
                pass
        finally:
            loop.run_until_complete(loop.shutdown_default_executor())
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            
    except ValueError:
        logging.error("\n[Error] Por favor, ingresa números válidos.")