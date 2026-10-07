# -*- coding: utf-8 -*-
"""
================================================================================
  davidOS Kiosk ISO Builder
  Bootable Alpine Linux + Chromium + tu davidOS, en una sola ISO
  Python 3.14  ·  IDLE-friendly  ·  Windows / macOS / Linux
================================================================================

Genera davidOS-kiosk.iso que ARRANCA en VirtualBox (o un PC real):
  BIOS → isolinux → kernel Linux → Alpine → Chromium kiosco → tu HTML

La primera vez que arranca descarga Chromium (~100 MB de internet,
VirtualBox ya tiene red NAT por defecto). Después funciona offline.
================================================================================
"""

from __future__ import annotations

import io
import re
import sys
import tarfile
import tempfile
import urllib.request
import subprocess
import platform
from pathlib import Path


# ────────────────────────────────────────────────────────────────────────────
#  Configuración
# ────────────────────────────────────────────────────────────────────────────
ALPINE_INDEX      = "https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/"
HTML_CANDIDATES   = ("index_davidos.html", "davidos.html", "index.html")
OUT_ISO_NAME      = "davidOS-kiosk.iso"
APKOVL_NAME       = "alpine.apkovl.tar.gz"
RAM_RECOMMENDED   = 2048   # MB


# ────────────────────────────────────────────────────────────────────────────
#  Utilidades
# ────────────────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[davidOS] {msg}", flush=True)

def die(msg: str, code: int = 1) -> None:
    print(f"\n[davidOS][ERROR] {msg}\n", flush=True)
    sys.exit(code)

def ensure(mod_name: str):
    try:
        return __import__(mod_name)
    except ImportError:
        log(f"Instalando dependencia: {mod_name} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "--quiet", "--disable-pip-version-check", mod_name])
        return __import__(mod_name)

def find_html() -> Path:
    here = Path(__file__).resolve().parent
    for folder in (here, Path.cwd()):
        for name in HTML_CANDIDATES:
            p = folder / name
            if p.is_file():
                return p
    die(f"No encontré el HTML. Coloca uno de estos junto al script: "
        f"{', '.join(HTML_CANDIDATES)}")


# ────────────────────────────────────────────────────────────────────────────
#  Descarga de Alpine
# ────────────────────────────────────────────────────────────────────────────
def find_alpine_url() -> str:
    log("Consultando la última versión de Alpine …")
    req = urllib.request.Request(ALPINE_INDEX, headers={"User-Agent": "davidOS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'href="(alpine-standard-[\d.]+-x86_64\.iso)"', html)
    if not m:
        die("No pude localizar la ISO de Alpine en el mirror.")
    url = ALPINE_INDEX + m.group(1)
    log(f"  Alpine: {m.group(1)}")
    return url

def download(url: str, dest: Path) -> None:
    log(f"Descargando Alpine (~200 MB) desde el mirror oficial …")
    total = 0
    def hook(blocks, bs, size):
        nonlocal total
        done = blocks * bs
        total = size
        if size > 0:
            pct = done * 100 / size
            filled = int(pct // 2)
            bar = "█" * filled + "░" * (50 - filled)
            mb = done / 1048576
            print(f"\r  [{bar}] {pct:5.1f}%  {mb:6.1f} MB", end="", flush=True)
    urllib.request.urlretrieve(url, str(dest), reporthook=hook)
    print()
    log(f"  Descargado ({dest.stat().st_size/1048576:.1f} MB)")


# ────────────────────────────────────────────────────────────────────────────
#  Overlay de Alpine (apkovl)
# ────────────────────────────────────────────────────────────────────────────
def build_apkovl(html_name: str, out_path: Path) -> None:
    """Crea el apkovl que Alpine aplicará sobre el sistema en vivo."""
    kiosk = f"""#!/bin/sh
# davidOS Web Edition · kiosk launcher
# Se ejecuta automáticamente tras el arranque, en tty7, sin login.

exec >/dev/console 2>&1
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   davidOS Web Edition · Arrancando kiosco    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Localizar el HTML en el medio de arranque
HTML=""
for p in /media/cdrom/{html_name} /media/sr0/{html_name} \\
         /media/*/{html_name} /mnt/{html_name} /run/media/*/{html_name}; do
    if [ -f "$p" ]; then HTML="$p"; break; fi
done
if [ -z "$HTML" ]; then
    HTML=$(find /media /mnt /run/media -name "{html_name}" 2>/dev/null | head -n1)
fi
if [ -z "$HTML" ]; then
    echo "ERROR: no se encontró {html_name} en el medio."
    exec /bin/sh
fi
echo "→ HTML: $HTML"

# Configurar mirror oficial
cat >/etc/apk/repositories <<EOF
https://dl-cdn.alpinelinux.org/alpine/latest-stable/main
https://dl-cdn.alpinelinux.org/alpine/latest-stable/community
EOF

# Esperar red (para iframes externos y para el apk add inicial)
echo "→ Esperando conexión de red …"
i=0
while [ $i -lt 30 ]; do
    ping -c1 -W1 8.8.8.8 >/dev/null 2>&1 && break
    i=$((i+1)); sleep 1
done

# Instalar Chromium y X.org si no están (solo la primera vez)
if ! command -v chromium-browser >/dev/null 2>&1; then
    echo "→ Instalando Chromium y X.org (una vez, ~100 MB) …"
    apk update
    apk add --no-cache \\
        xorg-server xf86-input-libinput xinit xorg-server-xvfb \\
        chromium ttf-dejavu font-noto mesa-dri-gallium \\
        || echo "WARN: algunos paquetes fallaron"
fi

# xinitrc
cat >/root/.xinitrc <<'XEOF'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
export KIOSK_URL
exec chromium-browser \\
    --kiosk \\
    --start-fullscreen \\
    --no-sandbox \\
    --disable-gpu \\
    --disable-software-rasterizer \\
    --disable-dev-shm-usage \\
    --no-first-run \\
    --no-default-browser-check \\
    --window-size=1366,768 \\
    "$KIOSK_URL"
XEOF
chmod +x /root/.xinitrc

export KIOSK_URL="file://$HTML"
echo "→ Lanzando Chromium en modo kiosco …"
exec startx /root/.xinitrc -- :0 vt7 -nolisten tcp
"""
    with tarfile.open(out_path, "w:gz") as tar:
        # /etc/local.d/kiosk.start
        data = kiosk.encode("utf-8")
        ti = tarfile.TarInfo("etc/local.d/kiosk.start")
        ti.size = len(data)
        ti.mode = 0o755
        tar.addfile(ti, io.BytesIO(data))

        # /etc/runlevels/default/local → symlink al servicio init
        ti = tarfile.TarInfo("etc/runlevels/default/local")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc/init.d/local"
        ti.mode = 0o777
        tar.addfile(ti)

        # /etc/motd
        motd = (b"\nWelcome to davidOS Web Edition (kiosk)\n"
                b"Chromium arrancar\xc3\xa1 en unos segundos...\n")
        ti = tarfile.TarInfo("etc/motd")
        ti.size = len(motd)
        ti.mode = 0o644
        tar.addfile(ti, io.BytesIO(motd))


# ────────────────────────────────────────────────────────────────────────────
#  Construcción de la ISO
# ────────────────────────────────────────────────────────────────────────────
def build_iso(html_path: Path, alpine_iso: Path, out_iso: Path) -> None:
    pycdlib = ensure("pycdlib")

    log("Abriendo ISO de Alpine …")
    iso = pycdlib.PyCdlib()
    iso.open(str(alpine_iso))

    # Guardar los primeros 432 bytes (código de arranque isohybrid)
    with open(alpine_iso, "rb") as f:
        isohybrid_mbr = f.read(432)

    # 1) Añadir el HTML sin modificar
    log(f"Añadiendo {html_path.name} (byte a byte) …")
    data = html_path.read_bytes()
    iso.add_fp(io.BytesIO(data), len(data),
               iso_path="/INDEX_D.HTM;1",
               joliet_path="/index_davidos.html",
               rr_name="index_davidos.html",
               file_mode=0o444)

    # 2) Añadir apkovl
    log("Generando apkovl de kiosco …")
    with tempfile.TemporaryDirectory() as td:
        apkovl = Path(td) / APKOVL_NAME
        build_apkovl(html_path.name, apkovl)
        data = apkovl.read_bytes()
        log(f"  apkovl: {len(data)/1024:.1f} KB")
        iso.add_fp(io.BytesIO(data), len(data),
                   iso_path="/ALPINE.APKOVL.TAR.GZ;1",
                   joliet_path="/" + APKOVL_NAME,
                   rr_name=APKOVL_NAME,
                   file_mode=0o644)

    # 3) Modificar isolinux.cfg para forzar nuestro apkovl
    log("Añadiendo apkovl a la línea de arranque …")
    try:
        with iso.open_file_from_iso(iso_path="/boot/isolinux/isolinux.cfg") as f:
            cfg = f.read().decode("utf-8", "replace")
    except Exception as e:
        die(f"No pude leer /boot/isolinux/isolinux.cfg: {e}")

    if "apkovl=" not in cfg:
        cfg = re.sub(r"(\bAPPEND\b[^\n]*)",
                     r"\1 apkovl=" + APKOVL_NAME,
                     cfg, count=1)

    data = cfg.encode("utf-8")
    try:
        iso.modify_file_in_place(io.BytesIO(data), len(data),
                                 iso_path="/boot/isolinux/isolinux.cfg")
    except Exception as e:
        log(f"  Aviso: modify_file_in_place falló ({e}); usando rm+add …")
        # Fallback: eliminar y volver a añadir
        try:
            iso.rm_file(iso_path="/boot/isolinux/isolinux.cfg")
        except Exception:
            pass
        iso.add_fp(io.BytesIO(data), len(data),
                   iso_path="/boot/isolinux/isolinux.cfg",
                   joliet_path="/boot/isolinux/isolinux.cfg",
                   rr_name="isolinux.cfg",
                   file_mode=0o644)

    # 4) Escribir la nueva ISO
    log(f"Escribiendo {out_iso.name} (puede tardar 30-60 s) …")
    iso.write(str(out_iso))
    iso.close()

    # 5) Restaurar el MBR isohybrid para que la BIOS la vea como disco
    with open(out_iso, "r+b") as f:
        f.write(isohybrid_mbr)

    log(f"  ISO lista: {out_iso.stat().st_size/1048576:.1f} MB")


# ────────────────────────────────────────────────────────────────────────────
#  Main
# ────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 68)
    print("  davidOS Kiosk ISO Builder")
    print(f"  Python {platform.python_version()}  ·  {platform.system()}")
    print("=" * 68)

    html = find_html()
    log(f"HTML encontrado: {html}  ({html.stat().st_size/1024:.1f} KB)")

    alpine_url = find_alpine_url()

    with tempfile.TemporaryDirectory() as td:
        alpine_iso = Path(td) / "alpine.iso"
        download(alpine_url, alpine_iso)
        out_iso = html.parent / OUT_ISO_NAME
        build_iso(html, alpine_iso, out_iso)

    print()
    print("=" * 68)
    print(f"  ✅  {OUT_ISO_NAME} lista")
    print("=" * 68)
    print()
    print("  Cómo arrancarla en VirtualBox")
    print("  ─────────────────────────────")
    print("   1. Nueva máquina virtual")
    print("      · Tipo: Linux")
    print("      · Versión: Other Linux (64-bit)")
    print("      · RAM: 2048 MB (recomendado; Chromium + X)")
    print("      · Disco duro: no hace falta (live)")
    print()
    print("   2. Configuración → Almacenamiento")
    print(f"      · Añade {OUT_ISO_NAME} como CD/DVD")
    print()
    print("   3. Red → NAT (por defecto). Se necesita internet")
    print("      la primera vez para bajar Chromium (~100 MB).")
    print()
    print("   4. Arranca la VM:")
    print("      BIOS/UEFI → isolinux → Alpine → apkovl")
    print("      → apk add chromium (~2 min) → Chromium kiosco")
    print("      → davidOS a pantalla completa 🚪")
    print()
    print("  También puedes grabarla en un USB con Rufus y")
    print("  arrancar un PC real (modo live).")
    print()
    print("=" * 68)

    # Ofrecer abrir la ISO
    try:
        ans = input("¿Montar la ISO ahora con el programa predeterminado? [s/N]: ")
    except EOFError:
        return
    if ans.strip().lower() in ("s", "si", "sí", "y", "yes"):
        try:
            if platform.system() == "Windows":
                import os
                os.startfile(str(out_iso))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(out_iso)])
            else:
                subprocess.Popen(["xdg-open", str(out_iso)])
        except Exception as e:
            log(f"No pude abrir la ISO automáticamente: {e}")


if __name__ == "__main__":
    main()
