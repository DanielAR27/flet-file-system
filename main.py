import flet as ft
import os
import shlex
import threading
import asyncio
from core.file_system import (
    FileSystem, 
    FileSystemException, 
    FileExistsConflictException, 
    DiskFullException
)

def main(page: ft.Page):
    page.title = "File System Emulator"
    page.bgcolor = "#2289ff"  # Fondo de la app
    page.padding = 10
    page.spacing = 10

    # Configuración de colores para el Scrollbar (barra blanquita)
    page.theme = ft.Theme(
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
            track_color=ft.Colors.TRANSPARENT,
            interactive=True,
            thickness=8,
            radius=4
        )
    )

    # Inicializar el File System principal
    fs = FileSystem()

    # Icono de ventana - Flet 0.85+
    page.window.icon = "assets/fs_icon.ico"

    # Estado para manejar confirmaciones pendientes de sobrescritura
    pending_action = None  # Almacena una función lambda con la acción a ejecutar si se confirma

    # UI Components

    # 1. Header (Logo, Título y Ruta Actual)
    path_text = ft.Text("Ruta Actual: /", size=18, weight=ft.FontWeight.W_500, color="#fef600")
    
    header_content = ft.Row(
        [
            ft.Image(
                src="/fs_icon.png",
                width=40,
                height=40,
                fit=ft.BoxFit.CONTAIN,
                border_radius=ft.BorderRadius.all(5)
            ),
            ft.VerticalDivider(width=10, color=ft.Colors.TRANSPARENT),
            ft.Column(
                [
                    ft.Text("FILE SYSTEM EMULATOR", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    path_text
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=2
            )
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER
    )

    header = ft.Container(
        content=header_content,
        padding=15,
        bgcolor="#003790",  # Barra oscura
        border_radius=10,
        height=80,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)
        )
    )

    # Función helper para generar líneas de árbol con colores personalizados
    def make_tree_item(prefix_lines, label, is_folder, node):
        controls = []
        is_current = (node is fs.current_dir)

        for line in prefix_lines:
            line_color = "#81c784" if is_current else "#fef600"
            controls.append(ft.Text(line, color=line_color, font_family="monospace", size=14, weight=ft.FontWeight.BOLD))
        
        icon_emoji = "📂" if (is_folder and is_current) else ("📁" if is_folder else "📄")
        controls.append(ft.Text(f"{icon_emoji} ", size=14))
        
        label_color = "#81c784" if is_current else ("#1e81fd" if is_folder else ft.Colors.WHITE)
        label_weight = ft.FontWeight.BOLD if is_current else ft.FontWeight.W_500
        controls.append(ft.Text(label, color=label_color, size=14, weight=label_weight, font_family="monospace"))
        
        # Marcador de directorio actual
        if is_current:
            controls.append(ft.Text(" ◄", color="#81c784", size=12, font_family="monospace"))
        
        return ft.Row(controls, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # 2. Sidebar (TREE)
    tree_view = ft.ListView(
        controls=[],
        expand=True,
        spacing=8,
        padding=5
    )
    
    sidebar = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ACCOUNT_TREE, color="#fef600"),
                        ft.Text("ESTRUCTURA (TREE)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                    ]
                ),
                ft.Divider(color="#2289ff"),
                tree_view
            ],
            expand=True
        ),
        width=280,
        bgcolor="#003790",  # Barra oscura
        padding=15,
        border_radius=10,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)
        )
    )

    # 3. Main Terminal / Logs
    log_area = ft.ListView(
        controls=[
            ft.Text("Bienvenido al File System Emulator v1.0", color="#81c784", size=14, weight=ft.FontWeight.BOLD),
            ft.Text("Use 'help' para ver los comandos disponibles.", color="#ffd54f", size=13),
            ft.Text("----------------------------------------------------------------", color=ft.Colors.BLUE_GREY_400)
        ],
        expand=True,
        auto_scroll=True,
        spacing=5,
        padding=10
    )

    # ── Helpers para abrir/cerrar diálogos (Flet 0.85.x) ──────────────────────
    def open_dialog(dlg):
        try:
            page.show_dialog(dlg)
        except Exception as ex:
            if "already opened" in str(ex):
                dlg.open = True
                dlg.update()

    def close_dialog(dlg):
        try:
            dlg.open = False
            dlg.update()
        except Exception:
            pass

    # Diálogo de Confirmación para Sobrescritura
    def handle_confirm_yes(e):
        nonlocal pending_action
        confirm_dialog.open = False
        page.update()
        if pending_action:
            try:
                result_message = pending_action(True)
                log_area.controls.append(ft.Text(result_message, color="#81c784", font_family="monospace"))
            except FileSystemException as ex:
                msg = str(ex)
                display_msg = msg if msg.startswith("Error") else f"Error: {msg}"
                log_area.controls.append(ft.Text(display_msg, color="#e57373", font_family="monospace"))
            except Exception as ex:
                log_area.controls.append(ft.Text(f"Error inesperado: {str(ex)}", color="#e57373", font_family="monospace"))
            
            pending_action = None
            update_ui()
        page.update()

    def handle_confirm_no(e):
        nonlocal pending_action
        confirm_dialog.open = False
        pending_action = None
        log_area.controls.append(ft.Text("Operación cancelada por el usuario.", color="#ffd54f"))
        page.update()

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Confirmar Sobrescritura", color=ft.Colors.WHITE),
        bgcolor="#003790",
        content=ft.Text("El archivo o directorio ya existe en el destino. ¿Deseas sobreescribirlo?", color=ft.Colors.WHITE70),
        actions=[
            ft.FilledButton("Sí, Sobrescribir", icon=ft.Icons.CHECK, on_click=handle_confirm_yes, style=ft.ButtonStyle(bgcolor="#e57373", color=ft.Colors.WHITE)),
            ft.FilledButton("No, Cancelar", icon=ft.Icons.CANCEL, on_click=handle_confirm_no, style=ft.ButtonStyle(bgcolor="#2289ff", color=ft.Colors.WHITE)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(confirm_dialog)

    # ─── Diálogo: Crear Archivo (FILE) - VERSIÓN DINÁMICA ─────────────────────
    def show_file_editor(initial_path: str, initial_content: str):
        active_task = None

        async def auto_close_banner():
            try:
                await asyncio.sleep(5.0)
                error_banner.visible = False
                page.update()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        def close_error_banner(e=None):
            nonlocal active_task
            if active_task:
                active_task.cancel()
                active_task = None
            error_banner.visible = False
            try:
                page.update()
            except Exception:
                pass

        error_banner = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.WHITE),
                ft.Text("", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, font_family="monospace", expand=True),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_color=ft.Colors.WHITE,
                    tooltip="Cerrar",
                    on_click=close_error_banner,
                    icon_size=18,
                    padding=0
                )
            ]),
            bgcolor="#e57373", padding=10, border_radius=8, visible=False
        )
        name_label = ft.Text("Nombre del archivo", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, font_family="monospace")
        name_input = ft.TextField(
            hint_text="Ingrese el nombre del archivo...",
            hint_style=ft.TextStyle(color=ft.Colors.with_opacity(0.45, ft.Colors.WHITE), font_family="monospace"),
            bgcolor="#14315e",
            color=ft.Colors.WHITE,
            border_color="#2289ff",
            focused_border_color="#81c784",
            cursor_color="#81c784",
            text_style=ft.TextStyle(font_family="monospace"),
            border_radius=8,
            value=initial_path
        )
        content_label = ft.Text("Contenido del archivo", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, font_family="monospace")
        content_input = ft.TextField(
            hint_text="Ingrese el contenido del archivo...",
            hint_style=ft.TextStyle(color=ft.Colors.with_opacity(0.45, ft.Colors.WHITE), font_family="monospace"),
            multiline=True,
            min_lines=15,
            max_lines=25,
            expand=True,
            bgcolor="#14315e",
            color=ft.Colors.WHITE,
            border_color="#2289ff",
            focused_border_color="#81c784",
            cursor_color="#81c784",
            text_style=ft.TextStyle(font_family="monospace"),
            border_radius=8,
            value=initial_content,
            autofocus=True
        )

        def handle_save(e):
            nonlocal pending_action, active_task
            path = (name_input.value or "").strip()
            content = content_input.value or ""
            if active_task:
                active_task.cancel()
                active_task = None
            error_banner.visible = False
            if not path:
                name_input.error_text = "El nombre no puede estar vacío."
                name_input.update()
                return
            name_input.error_text = None
            try:
                result = fs.cmd_file(path, content, overwrite=False)
                log_area.controls.append(ft.Text(result, color="#81c784", font_family="monospace"))
                update_ui()
                close_dialog(dlg)
            except FileExistsConflictException as fec:
                close_dialog(dlg)
                pending_action = lambda ow: fs.cmd_file(path, content, overwrite=ow)
                confirm_dialog.open = True
                page.update()
            except FileSystemException as ex:
                msg = str(ex)
                display_msg = msg if msg.startswith("Error") else f"Error: {msg}"
                error_banner.content.controls[1].value = display_msg
                error_banner.visible = True
                
                if active_task:
                    active_task.cancel()
                
                active_task = page.run_task(auto_close_banner)
                dlg.update()
            except Exception:
                pass

        def handle_cancel(e):
            nonlocal active_task
            if active_task:
                active_task.cancel()
                active_task = None
            close_dialog(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.Icons.NOTE_ADD, color="#ffd54f"), ft.Text("Editor de Archivos", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)],
                alignment=ft.MainAxisAlignment.START
            ),
            bgcolor="#003790",
            content=ft.Container(
                content=ft.Column(
                    [error_banner, name_label, name_input, content_label, content_input],
                    spacing=10, tight=True,
                ),
                width=680, padding=ft.Padding.all(5),
            ),
            actions=[
                ft.FilledButton("Cancelar", icon=ft.Icons.CANCEL, on_click=handle_cancel, style=ft.ButtonStyle(bgcolor="#e57373", color=ft.Colors.WHITE)),
                ft.FilledButton("Guardar Archivo", icon=ft.Icons.SAVE, on_click=handle_save, style=ft.ButtonStyle(bgcolor="#81c784", color="#003790")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        open_dialog(dlg)

    # ─── Diálogo: Modificar Archivo (MODFILE) ─────────────────────────────────

    modfile_task = None

    async def auto_close_modfile_banner():
        try:
            await asyncio.sleep(5.0)
            modfile_error_banner.visible = False
            page.update()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def close_modfile_error_banner(e=None):
        nonlocal modfile_task
        if modfile_task:
            modfile_task.cancel()
            modfile_task = None
        modfile_error_banner.visible = False
        try:
            page.update()
        except Exception:
            pass

    modfile_error_banner = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.WHITE),
            ft.Text("", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, font_family="monospace", expand=True),
            ft.IconButton(
                icon=ft.Icons.CLOSE,
                icon_color=ft.Colors.WHITE,
                tooltip="Cerrar",
                on_click=close_modfile_error_banner,
                icon_size=18,
                padding=0
            )
        ]),
        bgcolor="#e57373", padding=10, border_radius=8, visible=False
    )

    modfile_target_path  = [""]
    modfile_path_label   = ft.Text(
        "", color="#ffd54f", size=13, font_family="monospace", italic=True
    )
    modfile_content_label = ft.Text("Contenido del archivo", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, font_family="monospace")
    modfile_content_input = ft.TextField(
        hint_text="Ingrese el contenido del archivo...",
        hint_style=ft.TextStyle(color=ft.Colors.with_opacity(0.45, ft.Colors.WHITE), font_family="monospace"),
        multiline=True,
        min_lines=9,
        max_lines=14,
        bgcolor="#14315e",
        color=ft.Colors.WHITE,
        border_color="#2289ff",
        focused_border_color="#81c784",
        cursor_color="#81c784",
        text_style=ft.TextStyle(font_family="monospace"),
        width=650,
    )

    def handle_modfile_save(e):
        nonlocal modfile_task
        content = modfile_content_input.value or ""
        if modfile_task:
            modfile_task.cancel()
            modfile_task = None
        modfile_error_banner.visible = False
        try:
            result = fs.cmd_modfile(modfile_target_path[0], content)
            modfile_dialog.open = False
            log_area.controls.append(ft.Text(result, color="#81c784", font_family="monospace"))
            update_ui()
        except FileSystemException as ex:
            msg = str(ex)
            display_msg = msg if msg.startswith("Error") else f"Error: {msg}"
            modfile_error_banner.content.controls[1].value = display_msg
            modfile_error_banner.visible = True
            
            modfile_task = page.run_task(auto_close_modfile_banner)
            modfile_dialog.update()
            return
        page.update()

    def handle_modfile_cancel(e):
        nonlocal modfile_task
        if modfile_task:
            modfile_task.cancel()
            modfile_task = None
        modfile_dialog.open = False
        modfile_content_input.error_text = None
        modfile_error_banner.visible = False
        page.update()

    modfile_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [ft.Icon(ft.Icons.EDIT_DOCUMENT, color="#ffd54f"), ft.Text("Modificar Archivo", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)],
            alignment=ft.MainAxisAlignment.START
        ),
        bgcolor="#003790",
        content=ft.Container(
            content=ft.Column(
                [modfile_error_banner, modfile_path_label, modfile_content_label, modfile_content_input],
                spacing=12,
                tight=True,
            ),
            width=680,
            padding=ft.Padding.all(10),
        ),
        actions=[
            ft.FilledButton(
                "Cancelar",
                icon=ft.Icons.CANCEL,
                on_click=handle_modfile_cancel,
                style=ft.ButtonStyle(bgcolor="#e57373", color=ft.Colors.WHITE),
            ),
            ft.FilledButton(
                "Guardar Cambios",
                icon=ft.Icons.SAVE,
                on_click=handle_modfile_save,
                style=ft.ButtonStyle(bgcolor="#81c784", color=ft.Colors.WHITE),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=12)
    )
    page.overlay.append(modfile_dialog)

    # Función para actualizar los elementos visuales de la interfaz
    def update_ui():
        path_text.value = f"Ruta Actual: {fs.get_current_path_str()}"
        
        tree_items = []
        structure = fs.get_tree_structure()
        for prefix, name, is_dir, node in structure:  # Ahora incluye referencia al nodo
            tree_items.append(make_tree_item(prefix, name, is_dir, node))
        tree_view.controls = tree_items
        page.update()

    def execute_command_logic(cmd_str: str, overwrite: bool = False) -> str:
        """
        Interpreta y ejecuta el comando en el FileSystem del backend.
        Retorna el mensaje de resultado para mostrar en el log.
        """
        nonlocal pending_action
        try:
            parts = shlex.split(cmd_str, posix=False)
            parts = [p.strip('"\'') for p in parts]
        except ValueError as e:
            raise FileSystemException(f"Error en el comando: {str(e)}")
            
        if not parts:
            return ""
        
        main_cmd = parts[0].upper()

        if main_cmd not in ["HELP", "CREATE"]:
            if not fs.disk.is_initialized:
                raise FileSystemException("El disco virtual no está inicializado. Use CREATE primero.")

        if main_cmd == "HELP":
            cmds = [
                ("CREATE <sectores> <tamaño>", "Inicializa el disco virtual"),
                ("FILE [nombre.ext]", "Crea un archivo (abre editor)"),
                ("MODFILE <ruta>", "Modifica contenido de un archivo"),
                ("VERFILE <ruta>", "Muestra contenido de un archivo"),
                ("VERPROPIEDADES <ruta>", "Muestra propiedades de un elemento"),
                ("MKDIR <ruta>", "Crea un directorio (soporta rutas)"),
                ("CAMBIARDIR <ruta>", "Cambia de directorio (.., ., absoluta)"),
                ("LISTARDIR [ruta]", "Lista contenido del directorio"),
                ("TREE", "Muestra la estructura de árbol del File System"),
                ("FIND <patrón> [ruta]", "Busca archivos (soporta * y ?)"),
                ("MOVER <origen> <destino>", "Mueve o renombra archivo/directorio"),
                ("REMOVE <ruta>", "Elimina archivo o directorio"),
                ("COPY <origen> <destino>", "Copia (Real->Virt, Virt->Real, Virt->Virt)"),
                ("MAPA", "Muestra el estado de la FAT"),
                ("HELP", "Muestra esta ayuda")
            ]
            help_lines = ["Comandos disponibles:"]
            for cmd, desc in cmds:
                # Se calcula la cantidad de espacios necesarios para que quede parejito (hasta la columna 40)
                espacios = " " * (40 - len(cmd))
                help_lines.append(f"  {cmd}{espacios}- {desc}")
            return "\n".join(help_lines)

        elif main_cmd == "CREATE":
            if len(parts) < 3:
                raise FileSystemException("Sintaxis incorrecta. Uso: CREATE <sectores> <tamaño_sector>")
            try:
                sectores = int(parts[1])
                tamano = int(parts[2])
            except ValueError:
                raise FileSystemException("Los parámetros de sectores y tamaño deben ser números enteros.")
            return fs.cmd_create(sectores, tamano)

        elif main_cmd == "FILE":
            target_path = parts[1] if len(parts) > 1 else ""
            if not target_path and fs.disk.is_initialized and fs.disk.get_free_sectors_count() == 0:
                raise FileSystemException("El disco está lleno. No hay espacio para archivos nuevos.")
                
            loaded_content = ""
            if target_path and fs.disk.is_initialized:
                target_node = fs.resolve_virtual_path(target_path)
                if not target_node and fs.disk.get_free_sectors_count() == 0:
                    raise FileSystemException("El disco está lleno. No hay espacio para archivos nuevos.")
                if target_node and not target_node.is_directory:
                    loaded_content = fs.read_virtual_file_content(target_node).decode("utf-8", errors="replace")
            
            show_file_editor(target_path, loaded_content)
            return ""

        elif main_cmd == "MODFILE":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: MODFILE <ruta_archivo>")
            _path = parts[1]
            _target = fs.resolve_virtual_path(_path)
            if _target is None:
                raise FileSystemException(f"El archivo '{_path}' no existe.")
            if _target.is_directory:
                raise FileSystemException(f"'{_path}' es un directorio, no un archivo.")
            # Pre-llenar con el contenido actual y abrir diálogo
            current_content = fs.read_virtual_file_content(_target).decode("utf-8", errors="replace")
            modfile_target_path[0]        = _path
            modfile_path_label.value      = f"Editando: {fs.get_path_for_node(_target)}"
            modfile_content_input.value   = current_content
            modfile_content_input.error_text = None
            
            nonlocal modfile_task
            if modfile_task:
                modfile_task.cancel()
                modfile_task = None
            modfile_error_banner.visible = False
            
            modfile_dialog.open = True
            page.update()
            return ""

        elif main_cmd == "VERFILE":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: VERFILE <ruta_archivo>")
            return fs.cmd_verfile(parts[1])

        elif main_cmd == "VERPROPIEDADES":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: VERPROPIEDADES <ruta>")
            return fs.cmd_verpropiedades(parts[1])

        elif main_cmd == "MOVER":
            if len(parts) < 3:
                raise FileSystemException("Sintaxis incorrecta. Uso: MOVER <origen> <destino>")
            return fs.cmd_mover(parts[1], parts[2])

        elif main_cmd == "MKDIR":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: MKDIR <nombre_directorio>")
            return fs.cmd_mkdir(parts[1])

        elif main_cmd == "CAMBIARDIR":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: CAMBIARDIR <ruta_virtual>")
            return fs.cmd_cd(parts[1])

        elif main_cmd == "LISTARDIR":
            path_arg = parts[1] if len(parts) > 1 else None
            return fs.cmd_lsdir(path_arg)

        elif main_cmd == "TREE":
            return fs.cmd_tree()

        elif main_cmd == "FIND":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: FIND <patrón> [ruta_inicio]")
            pattern   = parts[1]
            start_arg = parts[2] if len(parts) > 2 else None
            return fs.cmd_find(pattern, start_arg)

        elif main_cmd == "REMOVE":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: REMOVE <ruta> [ruta2 ...]")
            
            results = []
            for path_arg in parts[1:]:
                try:
                    res = fs.cmd_remove(path_arg)
                    results.append(res)
                except FileSystemException as e:
                    results.append(f"Error al eliminar '{path_arg}': {str(e)}")
            return "\n".join(results)

        elif main_cmd == "COPY":
            if len(parts) < 3:
                raise FileSystemException("Sintaxis incorrecta. Uso: COPY <ruta_origen> <ruta_destino>")
            src = parts[1]
            dest = parts[2]
            
            try:
                return fs.cmd_copy(src, dest, overwrite=overwrite)
            except FileExistsConflictException as fec:
                pending_action = lambda ow: fs.cmd_copy(src, dest, overwrite=ow)
                confirm_dialog.open = True
                page.update()
                raise fec

        elif main_cmd == "MAPA":
            return fs.cmd_mapa()

        else:
            raise FileSystemException(f"Comando '{main_cmd}' no reconocido o responsabilidad de otro módulo.")

    # Estado de foco del input (para saber si debe interceptar Tab)
    input_focused = [False]

    # Historial de comandos estilo bash (↑/↓ para navegar)
    command_history = []
    history_index = [-1]    # -1 = no navegando, >= 0 = índice en historial
    current_draft = [""]    # Guarda el borrador antes de navegar al historial

    def on_command_submit(e):
        cmd = command_input.value.strip()
        if not cmd:
            return  # No hacer nada en vacío, el foco ya permanece
        
        # Guardar en historial (sin duplicados consecutivos)
        if not command_history or command_history[-1] != cmd:
            command_history.append(cmd)
        history_index[0] = -1
        current_draft[0] = ""
        
        # Mostrar el comando en la terminal
        log_area.controls.append(
            ft.Row([
                ft.Text("// ", color="#118b64", weight=ft.FontWeight.BOLD, font_family="monospace"),
                ft.Text(cmd, color=ft.Colors.WHITE, font_family="monospace")
            ], spacing=0)
        )
        
        try:
            result = execute_command_logic(cmd)
            if result:
                for line in result.split("\n"):
                    log_area.controls.append(ft.Text(line, color="#81c784", font_family="monospace"))
            update_ui()
        except FileExistsConflictException:
            log_area.controls.append(ft.Text("Elemento existente. Esperando confirmación de sobrescritura...", color="#ffd54f"))
        except FileSystemException as ex:
            # Evitar doble prefijo "Error: Error:"
            msg = str(ex)
            display = msg if msg.startswith("Error") else f"Error: {msg}"
            log_area.controls.append(ft.Text(display, color="#e57373"))
        except Exception as ex:
            log_area.controls.append(ft.Text(f"Error crítico del sistema: {str(ex)}", color="#e57373"))
        
        command_input.value = ""
        page.update()

    # Divisor con efecto glow animado al enfocar la terminal
    focus_line = ft.Container(
        height=2,
        bgcolor=ft.Colors.with_opacity(0.15, "#118b64"),
        border_radius=ft.BorderRadius.all(2),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=0,
            color=ft.Colors.TRANSPARENT
        ),
        animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT)
    )

    def on_input_focus(e):
        input_focused[0] = True
        focus_line.bgcolor = "#118b64"
        focus_line.shadow = ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color=ft.Colors.with_opacity(0.6, "#118b64")
        )
        page.update()

    def on_input_blur(e):
        input_focused[0] = False
        focus_line.bgcolor = ft.Colors.with_opacity(0.15, "#118b64")
        focus_line.shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=0,
            color=ft.Colors.TRANSPARENT
        )
        page.update()

    def on_keyboard_event(e: ft.KeyboardEvent):
        """Atajos de teclado estilo bash en la terminal."""
        if not input_focused[0]:
            return

        key = e.key
        ctrl = e.ctrl

        # --- FLECHA ARRIBA: comando anterior del historial ---
        if key in ("Arrow Up", "ArrowUp"):
            if not command_history:
                return
            if history_index[0] == -1:
                current_draft[0] = command_input.value
                history_index[0] = len(command_history) - 1
            elif history_index[0] > 0:
                history_index[0] -= 1
            command_input.value = command_history[history_index[0]]
            page.update()
            return

        # --- FLECHA ABAJO: comando siguiente del historial ---
        if key in ("Arrow Down", "ArrowDown"):
            if history_index[0] == -1:
                return
            if history_index[0] < len(command_history) - 1:
                history_index[0] += 1
                command_input.value = command_history[history_index[0]]
            else:
                history_index[0] = -1
                command_input.value = current_draft[0]
            page.update()
            return

        # --- CTRL+U: borrar toda la línea ---
        if ctrl and key.lower() == "u":
            command_input.value = ""
            current_draft[0] = ""
            history_index[0] = -1
            page.update()
            return

        # --- CTRL+W: borrar la última palabra ---
        if ctrl and key.lower() == "w":
            val = command_input.value
            stripped = val.rstrip(" ")
            last_space = stripped.rfind(" ")
            command_input.value = "" if last_space == -1 else stripped[:last_space + 1]
            page.update()
            return

        # --- CTRL+K: borrar desde el cursor hasta el final (aprox: borrar línea) ---
        if ctrl and key.lower() == "k":
            command_input.value = ""
            current_draft[0] = ""
            page.update()
            return

        # --- TAB: autocompletar rutas virtuales (estilo Linux) ---
        if key == "Tab":
            current_val = command_input.value
            parts = current_val.split(" ")
            if not parts:
                return
            partial = parts[-1]  # Último token = lo que se está escribiendo
            completions = fs.get_completions(partial)
            if len(completions) == 1:
                # Completado único: reemplazar el token directamente
                parts[-1] = completions[0]
                command_input.value = " ".join(parts)
                page.update()
            elif len(completions) > 1:
                # Múltiples opciones: mostrarlas en la terminal como Linux
                log_area.controls.append(
                    ft.Text("  ".join(completions), color="#ffd54f", font_family="monospace", size=13)
                )
                # Completar el prefijo común
                common = os.path.commonprefix(completions)
                if common and common != partial:
                    parts[-1] = common
                    command_input.value = " ".join(parts)
                page.update()

    page.on_keyboard_event = on_keyboard_event

    command_input = ft.TextField(
        hint_text="Digite un comando y presiona Enter...",
        hint_style=ft.TextStyle(color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE), font_family="monospace"),
        on_submit=on_command_submit,
        on_focus=on_input_focus,
        on_blur=on_input_blur,
        expand=True,
        border_radius=5,
        border_color=ft.Colors.TRANSPARENT,
        bgcolor="#14315e",
        color=ft.Colors.WHITE,
        content_padding=15,
        prefix=ft.Text("// ", color="#118b64", weight=ft.FontWeight.BOLD, size=16),
        cursor_color="#118b64",
        autofocus=True,  # Foco automático al iniciar
        text_style=ft.TextStyle(font_family="monospace"),
    )

    terminal_container = ft.Container(
        content=log_area,
        bgcolor="#14315e",
        expand=True,
        border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
        padding=10
    )

    input_container = ft.Container(
        content=command_input,
        bgcolor="#14315e",
        padding=ft.Padding.only(left=10, right=10, bottom=10),
        border_radius=ft.BorderRadius.only(bottom_left=10, bottom_right=10)
    )

    main_content = ft.Column(
        [
            terminal_container,
            focus_line,
            input_container
        ],
        expand=True,
        spacing=0
    )

    # Ensamble Layout Principal
    body = ft.Row(
        [
            sidebar,
            main_content
        ],
        expand=True,
        spacing=10
    )

    # Cargar UI inicial
    update_ui()

    page.add(
        ft.Column(
            [
                header,
                body
            ],
            expand=True,
            spacing=10
        )
    )

if __name__ == "__main__":
    ft.run(
        main=main,
        assets_dir="assets"
    )
