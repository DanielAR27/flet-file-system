import flet as ft
import os
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

    # Diálogo de Confirmación para Sobrescritura
    def handle_confirm_yes(e):
        nonlocal pending_action
        confirm_dialog.open = False
        page.update()
        if pending_action:
            try:
                result_message = pending_action(True)
                log_area.controls.append(ft.Text(result_message, color="#81c784"))
            except FileSystemException as ex:
                log_area.controls.append(ft.Text(f"Error: {str(ex)}", color="#e57373"))
            except Exception as ex:
                log_area.controls.append(ft.Text(f"Error inesperado: {str(ex)}", color="#e57373"))
            
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
        title=ft.Text("Confirmar Sobrescritura"),
        content=ft.Text("El archivo o directorio ya existe en el destino. ¿Deseas sobreescribirlo?"),
        actions=[
            ft.TextButton("Sí, Sobrescribir", on_click=handle_confirm_yes),
            ft.TextButton("No, Cancelar", on_click=handle_confirm_no),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(confirm_dialog)

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
        parts = cmd_str.split()
        if not parts:
            return ""
        
        main_cmd = parts[0].upper()

        if main_cmd == "HELP":
            return (
                "Comandos soportados en esta versión preliminar:\n"
                "  CREATE <sectores> <tamaño>        - Inicializa el disco virtual\n"
                "  MKDIR <nombre>                    - Crea un nuevo directorio\n"
                "  CD <ruta_virtual>                 - Cambia de directorio\n"
                "  COPY <ruta_origen> <ruta_destino> - Copia archivos (Real<->Virt, Virt<->Virt)\n"
                "  HELP                              - Muestra esta ayuda"
            )

        elif main_cmd == "CREATE":
            if len(parts) < 3:
                raise FileSystemException("Sintaxis incorrecta. Uso: CREATE <sectores> <tamaño_sector>")
            try:
                sectores = int(parts[1])
                tamano = int(parts[2])
            except ValueError:
                raise FileSystemException("Los parámetros de sectores y tamaño deben ser números enteros.")
            return fs.cmd_create(sectores, tamano)

        elif main_cmd == "MKDIR":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: MKDIR <nombre_directorio>")
            return fs.cmd_mkdir(parts[1])

        elif main_cmd == "CD":
            if len(parts) < 2:
                raise FileSystemException("Sintaxis incorrecta. Uso: CD <ruta_virtual>")
            return fs.cmd_cd(parts[1])

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
                log_area.controls.append(ft.Text(result, color="#81c784"))
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
