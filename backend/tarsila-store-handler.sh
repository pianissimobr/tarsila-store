#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# TARSILA STORE — handler do protocolo tarsila://
# Recebe:  tarsila://install/<pacote>
# Camada de segurança: só instala pacotes presentes na whitelist
# gerada a partir dos catálogos da loja (nunca comando arbitrário).
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

LOJA_DIR="/opt/tarsila-store"
WHITELIST="$LOJA_DIR/whitelist.txt"
LOG="$HOME/.local/share/tarsila-store/instalacoes.log"
mkdir -p "$(dirname "$LOG")"

URI="${1:-}"

notifica() {
    command -v notify-send >/dev/null && notify-send -a "Tarsila Store" "$1" "$2" || true
}

# ── 1. Parse e validação rígida da URI ──────────────────────
if [[ ! "$URI" =~ ^tarsila://install/([a-z0-9][a-z0-9+._-]*)$ ]]; then
    notifica "Solicitação recusada" "Endereço inválido: $URI"
    echo "$(date -Is) RECUSADO uri_invalida $URI" >> "$LOG"
    exit 1
fi
PKG="${BASH_REMATCH[1]}"

# ── 2. Whitelist: o pacote precisa estar no catálogo ────────
if [[ ! -f "$WHITELIST" ]] || ! grep -qxF "$PKG" "$WHITELIST"; then
    notifica "Pacote fora do catálogo" "'$PKG' não está na lista aprovada da Tarsila Store."
    echo "$(date -Is) RECUSADO fora_da_whitelist $PKG" >> "$LOG"
    exit 1
fi

# ── 3. Já instalado? ────────────────────────────────────────
if dpkg -s "$PKG" >/dev/null 2>&1; then
    notifica "Já instalado" "$PKG já está no seu computador. Procure no menu Aplicativos."
    exit 0
fi

# ── 4. Instalação com feedback visual ───────────────────────
notifica "Instalando $PKG" "Aguarde, baixando da internet…"
echo "$(date -Is) INICIO $PKG" >> "$LOG"

instala() {
    # pkexec pede a senha em janela gráfica (policykit-1 + agente do XFCE)
    pkexec /usr/bin/apt-get install -y --no-install-recommends "$PKG"
}

if command -v zenity >/dev/null; then
    ( instala ) 2>&1 | zenity --progress --pulsate --auto-close --no-cancel \
        --title="Tarsila Store" --text="Instalando <b>$PKG</b>…" --width=380 || RC=$? && RC=${RC:-0}
else
    instala; RC=$?
fi

# ── 5. Resultado ────────────────────────────────────────────
if dpkg -s "$PKG" >/dev/null 2>&1; then
    notifica "✓ Pronto!" "$PKG instalado. Ele já aparece no menu Aplicativos."
    echo "$(date -Is) OK $PKG" >> "$LOG"
else
    notifica "Não foi possível instalar" "$PKG — verifique a internet e tente de novo."
    echo "$(date -Is) FALHA $PKG rc=$RC" >> "$LOG"
    exit 1
fi
