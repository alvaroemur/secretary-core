"""Menu guiado interactivo para secretary."""
from __future__ import annotations

import sys

import typer

try:
    import questionary
except ImportError:
    questionary = None

from secretary.main import (
    FreshFormat,
    OutputFormat,
    fresh_cmd,
    paths_list,
    recall_cmd,
    routines_setup,
    wiki_build,
    wiki_serve,
)


def run_menu() -> None:
    """Entrypoint para el comando interactivo."""
    if questionary is None:
        print("El módulo 'questionary' no está instalado. Ejecuta 'pip install questionary'.", file=sys.stderr)
        sys.exit(1)

    while True:
        action = questionary.select(
            "¿Qué acción deseas ejecutar en Secretary?",
            choices=[
                questionary.Choice("📚 Wiki: Construir HTML (build)", "wiki_build"),
                questionary.Choice("🌐 Wiki: Servir localmente (serve)", "wiki_serve"),
                questionary.Choice("🔍 Search: Buscar en la memoria (recall)", "recall"),
                questionary.Choice("📊 Módulos: Ver estado actual (fresh)", "fresh"),
                questionary.Choice("⚙️  Config: Configurar Rutinas (setup)", "setup"),
                questionary.Choice("📂 Config: Listar paths (paths)", "paths"),
                questionary.Choice("❌ Salir", "exit"),
            ]
        ).ask()

        if not action or action == "exit":
            print("Saliendo de Secretary Menu.")
            break

        try:
            if action == "wiki_build":
                print("\n[Ejecutando: secretary wiki build]")
                wiki_build()
                
            elif action == "wiki_serve":
                port_str = questionary.text("Puerto (por defecto 8123):", default="8123").ask()
                if port_str:
                    port = int(port_str) if port_str.isdigit() else 8123
                    print(f"\n[Ejecutando: secretary wiki serve --port {port}]")
                    wiki_serve(port)

            elif action == "recall":
                query = questionary.text("Término de búsqueda (query):").ask()
                if query:
                    print(f"\n[Ejecutando: secretary recall '{query}']")
                    recall_cmd(query=query, out_fmt=OutputFormat.table)

            elif action == "fresh":
                mod = questionary.select(
                    "Módulo a consultar:",
                    choices=["all", "mail", "meeting", "whatsapp", "job-search", "wiki"]
                ).ask()
                if mod:
                    print(f"\n[Ejecutando: secretary fresh {mod}]")
                    fresh_cmd(module=mod, out_fmt=FreshFormat.table, local=False)

            elif action == "setup":
                print("\n[Ejecutando: secretary routines setup]")
                routines_setup()

            elif action == "paths":
                print("\n[Ejecutando: secretary paths]")
                paths_list()

        except typer.Exit as e:
            # Typer usa typer.Exit() para terminar el comando. 
            # Si el código es 0, podemos continuar en el menú o salir. 
            # Por consistencia con un menú persistente, si es 0, simplemente volvemos al loop.
            if e.code != 0:
                print(f"El comando falló con código {e.code}", file=sys.stderr)
                sys.exit(e.code)
            
        except KeyboardInterrupt:
            # CTRL+C interrumpe el comando actual pero te devuelve al menú.
            print("\nAcción cancelada.")
            
        print("\n" + "-"*40 + "\n")
