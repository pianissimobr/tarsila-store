#!/bin/bash
# Monta o .deb da Tarsila Store.
#
# Autonomo: le tudo deste repositorio, sem depender de uma loja ja instalada
# na maquina. (O build antigo copiava capas, catalogo e whitelist de
# /opt/tarsila-store, o que so funcionava rodando dentro da propria TV.)
#
# Uso: bash build-deb.sh [pasta-de-destino]     # padrao: ./dist
set -euo pipefail

VER="4.0.0"
AQUI="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$AQUI/dist}"
STAGE="$(mktemp -d)/tarsila-store-${VER}"
trap 'rm -rf "$(dirname "$STAGE")"' EXIT

command -v dpkg-deb >/dev/null || { echo "ERRO: falta dpkg-deb (apt install dpkg-dev)" >&2; exit 1; }

mkdir -p "$DEST" \
         "$STAGE/DEBIAN" \
         "$STAGE/opt/tarsila-store/bin" \
         "$STAGE/opt/tarsila-store/loja" \
         "$STAGE/opt/tarsila-store/motor" \
         "$STAGE/usr/local/lib/tarsila" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/tarsila/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$STAGE/etc/sudoers.d"

# --- dados: catalogo, capas, icones, whitelist -------------------------
# O catalogo em loja/catalog/ e a fonte unica (formato JavaScript da versao
# web, lido pelo GTK sem segunda copia dos dados).
cp -a "$AQUI/loja/." "$STAGE/opt/tarsila-store/loja/"
install -m 644 "$AQUI/whitelist.txt" "$STAGE/opt/tarsila-store/whitelist.txt"

# --- backend (motor da loja) -------------------------------------------
# tarsila-atalho-criar, tarsila-deb-instalar e tarsila-deb-gui.py vivem no
# tarsila-app-management; aqui so o tarsila-pkg (whitelist + apt) e o
# handler do protocolo tarsila://.
install -m 755 "$AQUI/backend/tarsila-pkg" \
               "$STAGE/opt/tarsila-store/bin/tarsila-pkg"
install -m 755 "$AQUI/backend/tarsila-store-handler.sh" \
               "$STAGE/opt/tarsila-store/tarsila-store-handler.sh"

# --- o aplicativo GTK --------------------------------------------------
install -m 755 "$AQUI/src/tarsila-store-gtk.py" \
               "$STAGE/opt/tarsila-store/bin/tarsila-store-gtk.py"
install -m 644 "$AQUI/src/tarsila_store_dados.py" \
               "$STAGE/usr/local/lib/tarsila/tarsila_store_dados.py"
install -m 644 "$AQUI/src/tarsila_store_visual.py" \
               "$STAGE/usr/local/lib/tarsila/tarsila_store_visual.py"
ln -sf /opt/tarsila-store/bin/tarsila-store-gtk.py "$STAGE/usr/bin/tarsila-store"

install -m 644 "$AQUI/desktop/appstore.png" \
               "$STAGE/usr/share/icons/hicolor/256x256/apps/tarsila-store.png"

# --- motor de fallback (headless) --------------------------------------
# Se o tarsila-app-management nao estiver instalado, o postinst instala
# estes helpers headless a partir daqui, SEM a resolucao grafica que o
# app-management traz junto (appfinder-yad, deb-gui).
install -m 755 "$AQUI/motor/tarsila-atalho-criar" \
               "$STAGE/opt/tarsila-store/motor/tarsila-atalho-criar"
install -m 755 "$AQUI/motor/tarsila-app-uninstall.sh" \
               "$STAGE/opt/tarsila-store/motor/tarsila-app-uninstall.sh"

# --- sudoers (tarsila-pkg so roda com NOPASSWD; ALL = qualquer usuario) -
install -m 440 "$AQUI/etc/sudoers.d/tarsila-store" \
               "$STAGE/etc/sudoers.d/tarsila-store"

# --- atalhos -----------------------------------------------------------
# O atalho comum chama /usr/bin/tarsila-store direto -- funciona em qualquer
# Debian. O "-tarsila" passa pelos wrappers do Tarsila OS (tarsila-abrindo e
# tarsila-uma-janela), que fora dele nao existem; por isso ele vai so para a
# grade curada do sistema, e nunca para /usr/share/applications.
for d in tarsila-store.desktop tarsila-protocol.desktop; do
  install -m 644 "$AQUI/desktop/$d" "$STAGE/usr/share/applications/$d"
done
install -m 644 "$AQUI/desktop/tarsila-store-tarsila.desktop" \
               "$STAGE/usr/share/tarsila/applications/tarsila-store.desktop"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: tarsila-store
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, sudo
Recommends: libnotify-bin, policykit-1, yad
Maintainer: Tarsila OS <tarsila@local>
Description: Loja de aplicativos do Tarsila OS
 Interface nativa em GTK3 para instalar e remover aplicativos e jogos de uma
 lista curada. Sem WebKit e sem servidor HTTP em processo separado: um unico
 processo Python, pensado para maquina de 2 GB de RAM.
 .
 A instalacao em si passa pelo tarsila-pkg, que so aceita pacotes da
 whitelist -- a loja nunca chama o apt diretamente. Se o tarsila-app-management
 estiver instalado, a loja usa os helpers dele; se nao, o postinst instala o
 "motor" headless (atalho curado + desinstalador) sem a interface grafica.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
# O backend HTTP da versao web nao existe mais: se ficou algum rodando de uma
# sessao anterior, so ocuparia memoria -- a loja GTK nao fala com ele.
pkill -f /opt/tarsila-store/bin/tarsila-backend.py 2>/dev/null || true
# Falha fechada: se a regra de sudoers nao validar, a loja nao instala nada.
visudo -c >/dev/null 2>&1 || echo "AVISO: sudoers invalido — a loja nao vai conseguir instalar" >&2
# Se o tarsila-app-management nao esta instalado, instala o "motor" headless
# (criacao de atalho curado + desinstalador) que a loja precisa, sem a
# resolucao grafica do app-management (appfinder-yad, deb-gui).
if ! command -v tarsila-atalho-criar >/dev/null 2>&1; then
  install -m 755 /opt/tarsila-store/motor/tarsila-atalho-criar /usr/local/bin/tarsila-atalho-criar
  install -m 755 /opt/tarsila-store/motor/tarsila-app-uninstall.sh /usr/local/bin/tarsila-app-uninstall.sh
  echo "tarsila-store: tarsila-app-management ausente — instalado o motor headless."
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

dpkg-deb --root-owner-group --build "$STAGE" "$DEST/tarsila-store_${VER}_all.deb" >/dev/null
echo "OK: $DEST/tarsila-store_${VER}_all.deb"
ls -lh "$DEST/tarsila-store_${VER}_all.deb" | awk '{print "  tamanho:", $5}'
