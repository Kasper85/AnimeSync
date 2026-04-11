import re
import os
import sys
import asyncio
import time
import logging
import aiohttp
from playwright.async_api import async_playwright

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

if sys.platform == 'win32' and sys.stdout and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from config import setup_logging
from providers import get_provider_for_url
from core.browser_manager import crear_navegador
from core.engine import procesar_episodio

# Iniciar configuración de loggers
setup_logging()

console = Console()

async def interactive_menu():
    while True:
        console.clear()
        console.print(Panel.fit("[bold cyan]🚀 MULTI-SCRAPER ASÍNCRONO DE ANIME 🚀[/bold cyan]\n[green]        [ AnimeSync v2.1 ]         [/green]", title="Menú Principal", border_style="blue"))
        console.print("\n[1] Descargar Serie (AnimeSync)")
        console.print("[2] Subir carpetas a Telegram (Telegram Updater)")
        console.print("[3] Descargar y Subir a Telegram (Juntos)")
        console.print("[4] Salir")
        
        opcion = Prompt.ask("\nSelecciona una opción", choices=["1", "2", "3", "4"], default="1")
        
        if opcion == "4":
            console.print("[yellow]Saliendo...[/yellow]")
            break
        elif opcion == "2":
            import telegram_updater.main as t_main
            await t_main.main()
            Prompt.ask("\n[bold]Presiona ENTER para volver al menú[/bold]")
        elif opcion in ["1", "3"]:
            carpetas_descargadas = await run_scraper()
            if opcion == "3" and carpetas_descargadas:
                console.print("\n[bold green]Iniciando subida a Telegram de las carpetas descargadas...[/bold green]")
                import telegram_updater.main as t_main
                await t_main.main(auto_paths=carpetas_descargadas, auto_confirm=True)
            
            Prompt.ask("\n[bold]Presiona ENTER para volver al menú[/bold]")

async def run_scraper():
    carpetas_completas = []
    
    # Solicitar URL(s) - soporta múltiples URLs separadas por coma o nueva línea
    url_input = Prompt.ask("\nIngresa la(s) URL(s) de la serie (Ej. jkanime.net/naruto)").strip()
    if not url_input:
        console.print("[red]No se ingreso ninguna URL.[/red]")
        return []
    
    # Parsear múltiples URLs (separadas por coma, espacio o newline)
    urls = [u.strip() for u in re.split(r'[\s,]+', url_input) if u.strip()]
    
    if not urls:
        console.print("[red]No se encontraron URLs válidas.[/red]")
        return []
    
    console.print(f"\n[bold green]✅ Se procesarán {len(urls)} serie(s)[/bold green]")
    
    # Estado global para acumular estadísticas de todas las series
    estado_global = {
        "total_bytes": 0,
        "total_tiempo_enlaces": 0,
        "total_tiempo_descargas": 0,
        "tiempo_inicio": time.time(),
    }
    
    # Procesar cada URL - compartir navegador entre series para eficiencia
    async with async_playwright() as p:
        browser = None
        
        for idx, url_base in enumerate(urls, 1):
            print(f"\n{'='*50}")
            print(f"📺 PROCESANDO SERIE {idx}/{len(urls)}")
            print(f"{'='*50}")
            
            try:
                provider = get_provider_for_url(url_base)
            except ValueError as e:
                console.print(f"[yellow]⚠️ URL ignorada (provider no soportado): {url_base} - {e}[/yellow]")
                continue
                
            console.print(f"[bold green]✅ Sitio detectado y soportado por provider: {provider.name}[/bold green]")
            
            # Crear browser si es la primera serie o si el dominio cambió
            if browser is None:
                browser = await crear_navegador(p, provider.domain)
            
            # Delegamos al provider para saber si pegaron un episodio aislado
            info_episodio = provider.extract_episode_info(url_base)
            
            es_dinamico = False
            
            if info_episodio:
                console.print(f"\n[cyan]📌 Has ingresado la URL de UN SOLO episodio (Cap {info_episodio['ep_num']}). Se descargará individualmente.[/cyan]")
                ep_inicio = info_episodio['ep_num']
                ep_fin = ep_inicio
                urls_episodios = [url_base]
                nombre_serie = info_episodio.get('serie', 'descarga_suelta')
                
            else:
                modo = Prompt.ask("¿Deseas descargar toda la serie desde el cap 1?", choices=["s", "n"], default="s")
                if modo == 'n':
                    ep_inicio = int(Prompt.ask("Ingresa el episodio INICIAL (ej. 10)"))
                    ep_fin = int(Prompt.ask("Ingresa el episodio FINAL (ej. 24)"))
                else:
                    ep_inicio = 1
                    ep_fin = 9999 
                    
                console.print("\n[magenta][INFO] Determinando lista de episodios...[/magenta]")
                try:
                    urls_episodios = await provider.get_episode_list(url_base, ep_inicio, ep_fin, browser)
                    
                    # Si el provider devolvió una lista razonable (scrapeó la página), usarla tal cual
                    if ep_fin == 9999 and len(urls_episodios) < 9000:
                        ep_fin = ep_inicio + len(urls_episodios) - 1
                        console.print(f"[cyan][PREPARE] El provider detectó {len(urls_episodios)} episodios.[/cyan]")
                    elif ep_fin == 9999:
                        # El provider no pudo detectar el total (modo ciego) -> activar modo dinámico
                        es_dinamico = True
                        console.print(f"[yellow][PREPARE] No se pudo detectar el total de episodios. Modo dinámico activado.[/yellow]")
                    else:
                        console.print(f"[cyan][PREPARE] {len(urls_episodios)} episodios en rango solicitado.[/cyan]")
                        
                except Exception as e:
                    console.print(f"[red]Fallo al construir URLs para la serie: {e}[/red]")
                    continue
                    
                if not urls_episodios:
                    console.print("[red]La lista de episodios está vacía.[/red]")
                    continue
                
                # Obtener un nombre de serie base para las carpetas
                nombre_serie = [p for p in url_base.rstrip('/').split('/') if p][-1]
                
            ruta_destino = os.path.join(os.getcwd(), nombre_serie)
            os.makedirs(ruta_destino, exist_ok=True)
            
            if es_dinamico:
                console.print(f"\n[cyan][PREPARE] Buscando dinámicamente episodios desde el cap {ep_inicio} en adelante...[/cyan]")
            else:
                console.print(f"\n[cyan][PREPARE] Total de tareas: {len(urls_episodios)} (Caps {ep_inicio} al {ep_fin})[/cyan]")
            
            # Reutilizar el browser existente en lugar de crear uno nuevo
            # (El código antiguo creaba uno nuevo en línea 118, lo cual era incorrecto)
            
            # Objeto de control de concurrencia para evitar saturar protección anti-bot (ej. Katanime a Max 2 por vez)
            limite_concurrencia = 2 if provider.name in ["Katanime", "JKAnime"] else 10
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
                                
                            # Solo mostrar inicio de descarga si es el primer worker (para evitar spam)
                            if worker_id == 0:
                                console.print(f"[blue]▶ BUSCANDO:[/blue] CAPÍTULO {tarea['ep']} - {tarea['serie']}")
                            
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
        
                            # Mostrar resultado de descarga
                            if resultado:
                                console.print(f"[bold green]✅ [Cap {tarea['ep']}] Descargado[/bold green]")
                                estado["total_bytes"] += b_descargados
                                estado["total_tiempo_enlaces"] += t_enlaces
                                estado["total_tiempo_descargas"] += t_descarga
                                estado["descargas"]["exitos"].add(tarea['ep'])
                                
                                # Actualizar el último episodio exitoso
                                if str(tarea['ep']).isdigit():
                                    ep_int = int(tarea['ep'])
                                    if ep_int > estado["ultimo_ep_exitoso"]:
                                        estado["ultimo_ep_exitoso"] = ep_int
                            else:
                                console.print(f"[bold red]❌ [Cap {tarea['ep']}] Falló[/bold red]")
                                estado["descargas"]["fallos"].add(tarea['ep'])
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

            # Acumular estadísticas de esta serie en el estado global
            estado_global["total_bytes"] += estado["total_bytes"]
            estado_global["total_tiempo_enlaces"] += estado["total_tiempo_enlaces"]
            estado_global["total_tiempo_descargas"] += estado["total_tiempo_descargas"]
            
            # Mostrar estadísticas de esta serie
            tiempo_serie = time.time() - estado["tiempo_inicio"]
            megas_serie = estado["total_bytes"] / (1024 * 1024)
            
            console.print(Panel.fit(
                f"[bold cyan]⏱️ Tiempo:[/bold cyan] {tiempo_serie:.2f} seg\n[bold cyan]💾 Descargado:[/bold cyan] {megas_serie:.2f} MB", 
                title=f"📊 ESTADÍSTICAS SERIE: {nombre_serie}", 
                border_style="green"
            ))
            
            exitos = sorted([int(x) if str(x).isdigit() else x for x in estado["descargas"]["exitos"]], key=lambda x: (isinstance(x, str), x))
            fallos_raw = sorted([int(x) if str(x).isdigit() else x for x in estado["descargas"]["fallos"]], key=lambda x: (isinstance(x, str), x))
            
            # En modo dinámico, solo mostrar fallos REALES (dentro del rango de éxitos), 
            # no los caps de sondeo que fallaron porque la serie ya terminó
            if es_dinamico and estado["ultimo_ep_exitoso"] > 0:
                fallos = [f for f in fallos_raw if isinstance(f, int) and f <= estado["ultimo_ep_exitoso"]]
            else:
                fallos = fallos_raw
            
            if fallos:
                console.print(f"[bold red][❌] Faltan los capítulos: {', '.join(map(str, fallos))}[/bold red]")
                console.print("[yellow][⚠️] La serie no se subirá a Telegram porque tiene capítulos fallidos o faltantes.[/yellow]")
            elif exitos:
                if ruta_destino not in carpetas_completas:
                    carpetas_completas.append(ruta_destino)
                if all(isinstance(x, int) for x in exitos) and exitos == list(range(min(exitos), max(exitos) + 1)):
                    rango_str = f"({min(exitos)}-{max(exitos)})" if len(exitos) > 1 else f"({exitos[0]})"
                    console.print(f"[bold green][✔️] Todos los capítulos descargados {rango_str}.[/bold green]")
                else:
                    console.print("[bold green][✔️] Todos los capítulos solicitados fueron descargados.[/bold green]")
            else:
                console.print("[yellow][⚠️] No se procesó ninguna descarga.[/yellow]")
        
        # Cerrar navegador al terminar todas las series
        if browser:
            try:
                await browser.close()
            except Exception as e:
                logging.debug(f"Navegador ya cerrado o error: {e}")

    # Mostrar estadísticas globales de todas las series
    tiempo_total_app = time.time() - estado_global["tiempo_inicio"]
    megas_totales = estado_global["total_bytes"] / (1024 * 1024)
    
    if len(urls) > 1:
        console.print(Panel.fit(
            f"[bold cyan]⏱️ Tiempo total:[/bold cyan] {tiempo_total_app:.2f} seg\n[bold cyan]💾 Descargado total:[/bold cyan] {megas_totales:.2f} MB", 
            title="📊 ESTADÍSTICAS GLOBALES (TODAS LAS SERIES)", 
            border_style="magenta"
        ))
    
    return carpetas_completas

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        main_task = loop.create_task(interactive_menu())
        
        try:
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                loop.run_until_complete(loop.shutdown_default_executor())
            except Exception:
                pass
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            
            try:
                loop.close()
            except Exception:
                pass
            
    except ValueError:
        logging.error("\n[Error] Por favor, ingresa números válidos.")
    except KeyboardInterrupt:
        console.print("\n[yellow]Saliendo de AnimeSync... (Cancelado por el usuario)[/yellow]")
        sys.exit(0)
