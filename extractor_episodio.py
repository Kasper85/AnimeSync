import logging

# ==========================================
# CONSTANTES DE SELECCIÓN Y CONFIGURACIÓN
# ==========================================
DOMINIO_JKANIME = "jkanime.net"
DOMINIO_LATANIME = "latanime.org"
DOMINIO_KATANIME = "katanime.net"

# Servidores por orden de prioridad para JKAnime
PRIORIDAD_SERVIDORES = ["Mediafire", "Mega", "Streamwish", "VOE", "Mp4upload", "Vidhide"]

async def _extraer_latanime(page, url_episodio):
    """Extrae el enlace usando la lógica exclusiva de LatAnime."""
    try:
        selector_mediafire = 'a.direct-link[href*="mediafire.com"]'
        await page.wait_for_selector(selector_mediafire, timeout=10000)
        enlace = await page.locator(selector_mediafire).get_attribute('href')
        return enlace.strip() if enlace else None
    except Exception as e:
        logging.warning(f"No se encontró Mediafire en LatAnime para {url_episodio}.")
        return None

async def _extraer_jkanime(page):
    """Extrae el enlace de la tabla de servidores de JKAnime."""
    boton_descarga = page.locator('#dwld')
    await boton_descarga.wait_for(state="visible")
    await boton_descarga.click()
    
    try:
        await page.wait_for_selector('table tbody tr', timeout=4000)
    except Exception:
        await boton_descarga.click(force=True)
        await page.wait_for_selector('table tbody tr', timeout=10000)
    
    filas = await page.locator('table tbody tr:not(:first-child)').all()
    opciones_descarga = {}
    
    for fila in filas:
        celdas = await fila.locator('td').all()
        if len(celdas) >= 4:
            servidor = await celdas[0].inner_text()
            enlace = await celdas[3].locator('a').get_attribute('href')
            opciones_descarga[servidor.strip()] = enlace
            
    if not opciones_descarga:
        return None

    for servidor_ideal in PRIORIDAD_SERVIDORES:
        if servidor_ideal in opciones_descarga:
            return opciones_descarga[servidor_ideal]

    servidor_fallback = list(opciones_descarga.keys())[0]
    return opciones_descarga[servidor_fallback]

async def _extraer_katanime(page, url_episodio):
    """Extrae el enlace interactuando agresivamente con los pop-unders y captchas de Katanime."""
    try:
        logging.info(f"[Katanime Trace] Empezando con {url_episodio}")
        
        boton_descarga = page.locator('button.btn-descargar.btn')
        await boton_descarga.wait_for(state="visible", timeout=10000)
        
        # Selector hiper-estricto para evadir botones fantasma o de otros servidores como Mega
        selector_mediafire = 'a.downbtn:has-text("Mediafire")'
        
        for _ in range(3):
            await boton_descarga.click(force=True)
            try:
                await page.wait_for_selector(selector_mediafire, timeout=3000)
                break
            except Exception:
                pass
        
        await page.wait_for_selector(selector_mediafire, timeout=5000)
        enlace_espera = await page.locator(selector_mediafire).first.get_attribute('href')
        
        if not enlace_espera:
            return None
            
        logging.info("[Katanime Trace] Navegando a página de espera...")
        await page.goto(enlace_espera)
        
        selector_linkbutton = '#linkButton'
        try:
            # Tolerancia radical a la carga de Cloudflare del modal 
            await page.wait_for_selector(selector_linkbutton, state="attached", timeout=45000)
            await page.wait_for_function('document.querySelector("#linkButton") && document.querySelector("#linkButton").href.includes("mediafire.com")', timeout=45000)
        except Exception as wait_e:
            logging.warning(f"Timeout esperando #linkButton para Mediafire en Katanime.")
            return None
        
        enlace_mediafire = await page.locator(selector_linkbutton).get_attribute('href')
        return enlace_mediafire.strip() if enlace_mediafire else None
        
    except Exception as e:
        logging.warning(f"Error procesando katanime.net para {url_episodio}: {e}")
        return None

# ==========================================
# RUTEO PÚBLICO (STRATEGY PATTERN)
# ==========================================
async def obtener_enlace_intermedio(page, url_episodio, dominio="jkanime.net"):
    """Punto de entrada orquestador que ruteará la estrategia de extracción según el dominio."""
    
    # Katanime explota si bloqueamos sus recursos media, por lo que bloqueamos todo menos en ese sitio
    if DOMINIO_KATANIME not in dominio:
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font", "media"] else route.continue_())
    
    await page.goto(url_episodio)

    if DOMINIO_LATANIME in dominio:
        return await _extraer_latanime(page, url_episodio)
    
    elif DOMINIO_JKANIME in dominio:
        return await _extraer_jkanime(page)
        
    elif DOMINIO_KATANIME in dominio:
        return await _extraer_katanime(page, url_episodio)
        
    return None