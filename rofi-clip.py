#!/usr/bin/env python3

import sys
import subprocess
import html
import re
import os
import shutil

# --- PALETA (Estilo Compacto) ---
C = {
    "bg":     "#0a0a0af2",
    "fg":     "#e0e0e0",
    "border": "#40a02b",
    "sel_bg": "#202020",
    "sel_fg": "#ffffff",
    "accent": "#ff3d2b",
    "img":    "#cba6f7",
    "url":    "#1e66f5",
    "env":    "#df8e1d",
}

FONT = "JetBrainsMono Nerd Font 11"
THEME_FILE = "/tmp/rofi_clip_compact.rasi"

# --- VERIFICACIÓN OPSEC/ENTORNO ---
def check_deps():
    """Valida dependencias en el PATH de NixOS antes de ejecutar."""
    deps = ["rofi", "cliphist", "wl-copy", "wl-paste"]
    missing = [cmd for cmd in deps if shutil.which(cmd) is None]
    if missing:
        print(f"[FATAL] Dependencias no encontradas en PATH: {', '.join(missing)}")
        sys.exit(1)

# --- GENERACIÓN DE TEMA COMPACTO ---
def generate_theme():
    css = f"""
    * {{
        background-color: transparent;
        text-color:       {C['fg']};
        font:             "{FONT}";
    }}
    window {{
        background-color: {C['bg']};
        border:           2px;
        border-color:     {C['border']};
        border-radius:    4px;
        width:            900px;
        padding:          10px;
    }}
    mainbox {{ spacing: 5px; }}
    inputbar {{
        children: [ prompt, entry ];
        margin:   0 0 5px 0;
        text-color: {C['border']};
    }}
    prompt {{
        font: "JetBrainsMono Nerd Font Bold 11";
        margin: 0 10px 0 0;
        text-color: {C['border']};
    }}
    entry {{ placeholder: "Escribe para filtrar..."; placeholder-color: #666; }}

    listview {{
        lines: 12;
        spacing: 2px;
        scrollbar: true;
        scrollbar-width: 4px;
        fixed-height: false;
    }}
    element {{
        padding: 4px 8px;
        border-radius: 3px;
    }}
    element selected {{
        background-color: {C['sel_bg']};
        text-color:       {C['sel_fg']};
        border:           1px;
        border-color:     {C['border']};
    }}
    element-text {{
        highlight: bold #a6e3a1;
        vertical-align: 0.5;
    }}
    """
    with open(THEME_FILE, "w") as f: f.write(css)

# --- LÓGICA DE DETECCIÓN INTELIGENTE ---
def format_line(line):
    parts = line.split("\t", 1)
    if len(parts) < 2: return line
    clip_id, text = parts[0], parts[1].strip()

    safe_text = html.escape(text.replace("\n", " ↵ "))

    # 1. IMAGEN
    if "[[ binary data" in text:
        meta = text.replace("[[ binary data", "").replace("]]", "").strip()
        display = f"<span color='{C['img']}'><b>  IMAGEN</b></span> <span size='small' color='#888'>({meta})</span>"
        return f"{clip_id}\t{display}\0icon\x1fimage-x-generic"

    # 2. CÓDIGO / CMD
    if re.search(r'^\s*(sudo|git|pacman|yay|nix|docker|npm|pip|ssh|cd|ls|mkdir|chmod|python|import|def|class|const|var|let|function|#!)', text):
        display = f"<span color='{C['accent']}'><b>  CMD</b></span>  {safe_text}"
        return f"{clip_id}\t{display}"

    # 3. ENV VARS / CRYPTO
    if re.match(r'^[A-Z0-9_]+=', text) or re.search(r'\b0x[a-fA-F0-9]{10,}\b', text) or re.search(r'\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b', text):
        display = f"<span color='{C['env']}'><b>  KEY</b></span>  {safe_text}"
        return f"{clip_id}\t{display}"

    # 4. URLS
    if re.search(r'(https?://|@)', text):
        display = f"<span color='{C['url']}'><b>  LINK</b></span> {safe_text}"
        return f"{clip_id}\t{display}"

    # 5. TEXTO PLANO
    return f"{clip_id}\t<span color='#888'> </span> {safe_text}"

def rofi_menu(formatted_lines):
    input_str = "\n".join(formatted_lines)
    cmd = [
        "rofi", "-dmenu",
        "-theme", THEME_FILE,
        "-p", "❯ Portapapeles",
        "-markup-rows",
        "-format", "i s",
        "-kb-custom-1", "Alt+Left",
        "-kb-custom-2", "Alt+Right"
    ]

    try:
        proc = subprocess.run(cmd, input=input_str, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip()
    except Exception:
        return 1, ""

def main():
    check_deps()
    generate_theme()

    try:
        raw_output = subprocess.check_output(["cliphist", "list"], text=True).strip()
    except subprocess.CalledProcessError:
        sys.exit(1)

    if not raw_output: sys.exit()

    lines = raw_output.splitlines()
    formatted_data = [format_line(l) for l in lines]

    while True:
        code, result = rofi_menu(formatted_data)

        if code == 1: sys.exit(0)

        if not result: continue

        try:
            selection_text = result.split(" ", 1)[1] if " " in result else ""
            clip_id = selection_text.split("\t")[0]
        except IndexError:
            continue

        if code == 0: # ENTER -> Copiar
            subprocess.run(f"cliphist decode {clip_id} | wl-copy", shell=True)
            sys.exit(0)

        elif code == 11: # Alt+Der -> Borrar
            subprocess.run(f"cliphist delete {clip_id}", shell=True)
            sys.exit(0)

        elif code == 10: # Alt+Izq -> PREVIEW
            try:
                content = subprocess.check_output(f"cliphist decode {clip_id}", shell=True)
                try:
                    text_content = content.decode('utf-8')
                    view_str = html.escape(text_content)
                except UnicodeDecodeError:
                    view_str = "🖼️\n\nEste elemento es una imagen o dato binario.\nPresiona Enter para copiarlo."
            except Exception:
                view_str = "Error al leer contenido."

            subprocess.run([
                "rofi", "-e", view_str,
                "-theme", THEME_FILE,
                "-theme-str", 'window { width: 800px; }',
                "-theme-str", f'message {{ padding: 20px; font: "{FONT}"; }}'
            ])

if __name__ == "__main__":
    main()

