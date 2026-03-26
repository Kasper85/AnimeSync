#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uploader de archivos a Telegram usando Telethon
=================================================

Este script permite subir archivos locales a un canal de Telegram usando
una cuenta de usuario personal (no bot). Compatible con cuentas Premium
que tienen límites de hasta 4 GB por archivo.

----------------------------------------------------------------------
ESTRUCTURA MODULAR:
----------------------------------------------------------------------
- config.py   : Carga y validación de configuración desde .env
- auth.py     : Login interactivo y gestión de sesiones
- files.py    : Utilidades para obtener, filtrar y mostrar archivos
- uploader.py: Lógica de upload con manejo de errores robusto
- main.py     : Punto de entrada que orquesta todo

----------------------------------------------------------------------
INSTRUCCIONES DE CONFIGURACIÓN
----------------------------------------------------------------------

1. CREAR ARCHIVO .env:
   Copia el archivo .env.example como .env y completa los valores:
   
   API_ID=12345678        (tu API ID de my.telegram.org)
   API_HASH=xxxx...       (tu API hash de my.telegram.org)
   PHONE=+511234567890    (tu número con código de país)
   CHANNEL=mi_canal       (username sin @ o ID numérico -100xxx)

2. OBTENER API_ID y API_HASH:
   - Ve a https://my.telegram.org/apps
   - Inicia sesión con tu cuenta de Telegram
   - Crea una nueva aplicación (Development)
   - Copia el api_id y api_hash generados
   - IMPORTANTE: Nunca compartas estos datos

3. CONFIGURAR EL CANAL:
   - Tu cuenta debe ser administrador del canal
   - Necesitas permisos de "Publicar mensajes"
   - El canal puede ser público (@username) o privado (ID -100xxx)

4. SEGURIDAD:
   ⚠️ NUNCA subas el archivo .session a GitHub
   ⚠️ NUNCA subas el archivo .env a GitHub
   ⚠️ Añade ambos a tu .gitignore

5. PRIMER LOGIN:
   - La primera ejecución te pedirá un código SMS
   - Si tienes 2FA, te pedirá la contraseña
   - El código llega por Telegram (no SMS real si tienes 2FA)
   - La sesión se guarda en uploader.session (no sobrescribir si existe)

----------------------------------------------------------------------
DEPENDENCIAS:
   pip install telethon python-dotenv tqdm

   Opcional (recomendado para velocidad):
   pip install cryptg
----------------------------------------------------------------------
"""

import asyncio
import logging
import sys
import os

# Configurar UTF-8 para Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Módulos propios
from config import Config, load_config
from auth import create_client, ensure_session, disconnect_client, is_valid_session_file
from files import (
    get_files_in_directory,
    print_files_summary,
    parse_extensions,
    select_sort_option,
    get_max_files_input,
    validate_directory,
    FileInfo,
)
from uploader import get_channel_entity, upload_files, UploadStats


# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


# ============================================================
# VERIFICAR DEPENDENCIAS OPCIONALES
# ============================================================

def check_optional_dependencies() -> bool:
    """Verifica si cryptg está disponible para aceleración"""
    try:
        import cryptg
        return True
    except ImportError:
        return False


# ============================================================
# FLUJO PRINCIPAL
# ============================================================

async def main(auto_paths=None, auto_confirm=False) -> None:
    """
    Función principal del programa - Orquesta todos los módulos
    """
    print("\n" + "="*60)
    print("🚀 TELEGRAM UPLOADER - Telethon ( Modular )")
    print("="*60)
    
    # Verificar dependencias opcionales
    cryptg_available = check_optional_dependencies()
    if cryptg_available:
        print("✓ cryptg disponible - velocidad de carga optimizada")
    else:
        print("ℹ️  cryptg no disponible - usando cifrado estándar")
    print()
    
    # ============================================================
    # CARGAR CONFIGURACIÓN
    # ============================================================
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        return
    
    # ============================================================
    # CREAR CLIENTE Y AUTENTICAR
    # ============================================================
    if config.session_file.exists():
        if not await is_valid_session_file(config.session_file):
            logger.info("Archivo de sesión inválido o corrupto eliminado")

    client = await create_client(config)
    
    try:
        # Asegurar sesión válida
        if not await ensure_session(client, config):
            logger.error("No se pudo establecer la sesión")
            return
        
        # ============================================================
        # OBTENER ENTIDAD DEL CANAL
        # ============================================================
        try:
            channel_entity = await get_channel_entity(client, config.channel)
        except ValueError as e:
            logger.error(f"Error al obtener canal: {e}")
            return
        
        # ============================================================
        # SOLICITAR RUTAS DE CARPETAS
        # ============================================================
        paths = []
        if auto_paths:
            for folder_path in auto_paths:
                path = validate_directory(folder_path)
                if path and path not in paths:
                    paths.append(path)
            print(f"✓ Usando {len(paths)} carpeta(s) proveída(s) automáticamente.")
        else:
            print("\n--- SELECCIÓN DE CARPETAS ---")
            print("Ingresa las rutas ABSOLUTAS de las carpetas (una por línea).")
            print("Para terminar, deja la línea en blanco y presiona ENTER.")
            
            while True:
                folder_path = input("Ruta (o ENTER para continuar): ").strip()
                if not folder_path:
                    if paths:
                        break
                    else:
                        print("✗ Debes ingresar al menos una ruta.")
                        continue
                        
                path = validate_directory(folder_path)
                if path:
                    if path not in paths:
                        paths.append(path)
                        print(f"✓ Carpeta añadida: {path}")
                    else:
                        print("ℹ️ Esta carpeta ya fue añadida.")
        
        # ============================================================
        # OPCIONES DE FILTRADO Y ORDEN
        # ============================================================
        
        extensions = None
        sort_by = 'name'
        max_files = None
        
        if not auto_confirm:
            print("\n--- OPCIONES DE SUBIDA ---")
            
            # Filtrar por extensión
            filter_ext = input(
                "Filtrar por extensiones? (ej: .mp4 .mkv .zip) [ENTER = todas]: "
            ).strip()
            
            extensions = parse_extensions(filter_ext)
            if extensions:
                print(f"✓ Filtrando: {', '.join(extensions)}")
            
            # Orden de archivos
            sort_by = select_sort_option()
            
            # Límite de archivos
            max_files = get_max_files_input()
            if max_files:
                print(f"✓ Límite: {max_files} archivos")
        
        # ============================================================
        # OBTENER Y MOSTRAR ARCHIVOS
        # ============================================================
        all_folder_files = []
        total_files = 0
        
        for path in paths:
            files = get_files_in_directory(
                path,
                extensions=extensions,
                sort_by=sort_by,
                max_files=max_files,
            )
            if files:
                all_folder_files.append((path, files))
                total_files += len(files)
        
        if not all_folder_files:
            logger.error("No se encontraron archivos en las carpetas proporcionadas")
            return
        
        print(f"\nSe procesarán {len(all_folder_files)} carpetas con un total de {total_files} archivos.")
        for path, files in all_folder_files:
            print(f"\nCarpeta: {path.name}")
            print_files_summary(files)
        
        # Confirmar subida
        if not auto_confirm:
            confirm = input("¿Subir todos los archivos de todas las carpetas? (s/n): ").strip().lower()
            
            if confirm != 's':
                logger.info("Operación cancelada por el usuario")
                return
        else:
            print("\n✓ Autoconfirmación activa. Iniciando subida...")
        
        # ============================================================
        # SUBIR ARCHIVOS
        # ============================================================
        print("\n" + "="*60)
        print("📤 INICIANDO SUBIDA MÚLTIPLE")
        print("="*60 + "\n")
        
        global_uploaded = 0
        global_skipped = 0
        global_failed = 0
        global_time = 0.0
        global_links = []
        
        for path, files in all_folder_files:
            print("\n" + "="*60)
            print(f"📁 ENVIANDO CARPETA: {path.name}")
            print("="*60)
            
            # Enviar mensaje con el título de la carpeta
            await client.send_message(channel_entity, f"**{path.name}**")
            
            # Ejecutar upload
            stats = await upload_files(client, channel_entity, files)
            
            global_uploaded += stats.uploaded
            global_skipped += stats.skipped
            global_failed += stats.failed
            global_time += stats.total_time
            if stats.links:
                global_links.extend(stats.links)
                
            await asyncio.sleep(2)
        
        # Mostrar estadísticas finales
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS GLOBALES DE SUBIDA")
        print("="*60)
        print(f"  ✅ Subidos exitosamente: {global_uploaded}")
        print(f"  ⏭️  Saltados (>4 GB):    {global_skipped}")
        print(f"  ❌ Fallidos:             {global_failed}")
        print(f"  ⏱️  Tiempo total:         {global_time:.1f} segundos")
        
        if global_time > 0 and global_uploaded > 0:
            speed = global_uploaded / global_time * 60
            print(f"  📈 Velocidad promedio:   {speed:.1f} archivos/min")
        
        if global_links:
            print("\n--- ENLACES DE ARCHIVOS SUBIDOS ---")
            for link in global_links:
                print(f"  • {link}")
        
        print("\n" + "="*60)
        print("🎉 OPERACIÓN COMPLETADA")
        print("="*60 + "\n")
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("\n⚠️  Operación cancelada por el usuario")
        
    finally:
        # Cerrar conexión
        await disconnect_client(client)


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    # Ejecutar con asyncio
    asyncio.run(main())