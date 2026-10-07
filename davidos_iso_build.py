# -*- coding: utf-8 -*-
"""
================================================================================
  davidOS Web Edition  ·  ISO Builder
  Python 3.14  ·  Compatible con IDLE
================================================================================

Empaqueta el sistema operativo simulado davidOS (index_davidos.html) dentro de
una imagen ISO híbrida, sin recortar, comprimir ni aplanar NADA del HTML:

  · Gradientes, transiciones, animaciones y temas intactos
  · Glassmorphism (backdrop-filter) intacto
  · Iframes pesados (YouTube, ChatGPT, Minecraft, Wikipedia…) NO bloquean
    el sistema, porque el HTML ya los aísla en <iframe> separados
  · Autorun para Windows (abre en el navegador al montar)
  · Compatible con Joliet + Rock Ridge + UDF (Windows / macOS / Linux)

USO
---
  1. Coloca este script junto a index_davidos.html
  2. IDLE → F5   (o:  python build_davidos_iso.py)
  3. Se genera davidOS.iso en la misma carpeta

DEPENDENCIA
-----------
  pycdlib (se instala automáticamente si falta)
================================================================================
"""

from __future__ import annotations

import io
import sys
import subprocess
import platform
from pathlib import Path

# ----------------------------------------------------------------------------
#  Configuración
# ----------------------------------------------------------------------------
HTML_CANDIDATES = ("index_davidos.html", "davidos.html", "index.html")
ISO_NAME        = "davidOS.iso"
VOLUME_LABEL    = "DAVIDOS_WEB"
VOLUME_SET      = "davidOS Web Edition"
PUBLISHER       = "davidOS"
PREPARER        = "davidOS ISO Builder"
APPLICATION     = "davidOS Web OS"

# ----------------------------------------------------------------------------
#  Utilidades
# ----------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[davidOS] {msg}")

def die(msg: str, code: int = 1) -> None:
    print(f"[davidOS][ERROR] {msg}")
    sys.exit(code)

def pip_install(package: str) -> None:
    log(f"Instalando dependencia: {package} …")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "--quiet", "--disable-pip-version-check", package]
        )
    except subprocess.CalledProcessError as exc:
        die(f"No se pudo instalar {package}: {exc}")

def ensure_pycdlib():
    try:
        import pycdlib  # noqa
        return pycdlib
    except ImportError:
        pip_install("pycdlib")
        import pycdlib  # noqa
        return pycdlib

# ----------------------------------------------------------------------------
#  Localizar el HTML
# ----------------------------------------------------------------------------
def find_html() -> Path:
    here = Path(__file__).resolve().parent
    for folder in (here, Path.cwd()):
        for name in HTML_CANDIDATES:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    die(
        "No se encontró el HTML de davidOS.\n"
        f"Coloca uno de estos junto al script: {', '.join(HTML_CANDIDATES)}"
    )

# ----------------------------------------------------------------------------
#  Generar la ISO
# ----------------------------------------------------------------------------
def build_iso(html_path: Path, iso_path: Path) -> None:
    pycdlib = ensure_pycdlib()

    iso = pycdlib.PyCdlib()
    iso.new(
        interchange_level=3,
        vol_ident=VOLUME_LABEL,
        sys_ident="LINUX",
        vol_set_ident=VOLUME_SET,
        pub_ident_str=PUBLISHER,
        preparer_ident_str=PREPARER,
        app_ident_str=APPLICATION,
        copyright_file="",
        abstract_file="",
        bibli_file="",
        joliet=3,
        rock_ridge="1.09",
        udf="2.60",
    )

    # --- 1) El HTML de davidOS, byte a byte, sin tocar nada -----------------
    html_bytes = html_path.read_bytes()
    iso.add_fp(
        io.BytesIO(html_bytes),
        len(html_bytes),
        iso_path="/INDEX_D.HTM;1",
        joliet_path="/index_davidos.html",
        rr_name="index_davidos.html",
        file_mode=0o444,
    )

    # --- 2) README ----------------------------------------------------------
    readme = (
        "davidOS Web Edition\r\n"
        "====================\r\n"
        "\r\n"
        "Cómo usar esta ISO\r\n"
        "------------------\r\n"
        "  1. Monta la imagen (Windows / macOS / Linux).\r\n"
        "  2. Abre 'index_davidos.html' con tu navegador.\r\n"
        "  3. En Windows se abrirá automáticamente (autorun.inf).\r\n"
        "\r\n"
        "Sobre el sistema\r\n"
        "----------------\r\n"
        "  · Kernel simulado + BIOS + escritorio de ventanas.\r\n"
        "  · 70+ aplicaciones incluidas en un único HTML.\r\n"
        "  · No requiere instalación ni conexión a internet.\r\n"
        "  · Gradientes, temas, animaciones y efectos originales intactos.\r\n"
        "  · Los iframes pesados (YouTube, ChatGPT, Minecraft, etc.) se\r\n"
        "    cargan aislados, por lo que NUNCA bloquean el sistema.\r\n"
        "\r\n"
        "Atajos útiles\r\n"
        "-------------\r\n"
        "  Ctrl+K ......... Paleta de comandos\r\n"
        "  Ctrl+Alt+T ..... davidconsole\r\n"
        "  Meta/Win ....... Menú Inicio\r\n"
        "  Meta+D ......... Mostrar escritorio\r\n"
        "  Alt+F4 ......... Cerrar ventana activa\r\n"
        "  F2 / Supr ...... Entrar a la BIOS (durante el arranque)\r\n"
    ).encode("utf-8")
    iso.add_fp(
        io.BytesIO(readme),
        len(readme),
        iso_path="/README.TXT;1",
        joliet_path="/README.txt",
        rr_name="README.txt",
    )

    # --- 3) autorun.inf (Windows) ------------------------------------------
    autorun = (
        "[autorun]\r\n"
        "open=index_davidos.html\r\n"
        "label=davidOS Web Edition\r\n"
        "action=Abrir davidOS\r\n"
    ).encode("ascii")
    iso.add_fp(
        io.BytesIO(autorun),
        len(autorun),
        iso_path="/AUTORUN.INF;1",
        joliet_path="/autorun.inf",
        rr_name="autorun.inf",
    )

    # --- 4) Escribir la ISO -------------------------------------------------
    iso.write(str(iso_path))
    iso.close()

# ----------------------------------------------------------------------------
#  Abrir la ISO según el sistema operativo
# ----------------------------------------------------------------------------
def reveal_iso(iso_path: Path) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            import os
            os.startfile(iso_path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(iso_path)])
        else:
            subprocess.Popen(["xdg-open", str(iso_path)])
    except Exception:
        pass

# ----------------------------------------------------------------------------
#  Punto de entrada
# ----------------------------------------------------------------------------
def main() -> None:
    print("=" * 68)
    print("  davidOS Web Edition  ·  ISO Builder")
    print(f"  Python {'.'.join(map(str, sys.version_info[:3]))}  ·  {platform.system()}")
    print("=" * 68)

    html = find_html()
    size_kb = html.stat().st_size / 1024
    log(f"HTML encontrado: {html.name}  ({size_kb:.1f} KB)")

    iso_path = html.parent / ISO_NAME
    log(f"Construyendo ISO → {iso_path.name} …")

    build_iso(html, iso_path)

    mb = iso_path.stat().st_size / (1024 * 1024)
    print()
    print("=" * 68)
    log(f"ISO lista: {iso_path}")
    log(f"Tamaño: {mb:.2f} MB")
    print("=" * 68)
    print("  Contenido de la ISO")
    print("  ───────────────────")
    print("    /index_davidos.html   ← sistema completo (sin recortes)")
    print("    /README.txt           ← instrucciones")
    print("    /autorun.inf          ← auto-ejecución en Windows")
    print()
    print("  Monta la ISO y abre index_davidos.html en el navegador.")
    print("  Absolutamente NADA del sistema original se ha aplanado:")
    print("  gradientes, transiciones, temas y iframes aislados intactos.")
    print()

    # Preguntar si quiere abrir la ISO ya mismo
    try:
        answer = input("¿Abrir la ISO ahora con el programa predeterminado? [s/N]: ")
    except EOFError:
        return
    if answer.strip().lower() in ("s", "si", "sí", "y", "yes"):
        reveal_iso(iso_path)


if __name__ == "__main__":
    main()
