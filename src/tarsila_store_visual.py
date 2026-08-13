#!/usr/bin/env python3
"""Aparencia da Tarsila Store em GTK: cores, capas e cartoes.

As cores e medidas sao as MESMAS do css/store.css da versao web -- copiadas
uma a uma dos :root de la. E o que faz a loja continuar reconhecivel: o GTK3
tem motor CSS proprio, entao os tokens do desenho original atravessam quase
sem traducao.
"""

from __future__ import annotations

import math
import os

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango  # noqa: E402

import tarsila_store_dados as dados  # noqa: E402

# ------------------------------------------------------------------ cores
# Copiadas do :root do store.css. Manter os dois lados iguais e o que garante
# que a loja GTK e a web sejam a mesma loja.
TEMAS = {
    "claro": {
        "fundo": "#E9EEF3", "superficie": "#FFFFFF",
        "tinta": "#17212A", "tinta2": "#5B6873",
        "linha": "rgba(23,33,42,.13)", "veu": "rgba(23,33,42,.06)",
        "veu2": "rgba(23,33,42,.12)",
        "b_ram_bg": "rgba(62,124,177,.16)", "b_ram_c": "#24507a",
        "b_ok_bg": "rgba(31,169,122,.18)", "b_ok_c": "#0e5c41",
        "b_warn_bg": "rgba(217,89,61,.16)", "b_warn_c": "#8a2f1c",
        "b_sol_bg": "rgba(242,183,5,.22)", "b_sol_c": "#6b5303",
        "cmd_c": "#0c6b4c", "marca_b": "#b3860a",
        # Botao secundario ("Mais informacoes"): ele fica SOBRE a imagem do
        # destaque, onde "sem fundo" virava texto solto disputando com a foto.
        # Gelo quase opaco resolve a leitura sem competir com o botao
        # principal, que e sol cheio -- a hierarquia continua obvia.
        "gelo": "rgba(255,255,255,.92)", "gelo_c": "#17212A",
        "gelo_hover": "#FFFFFF",
    },
    "escuro": {
        "fundo": "#101418", "superficie": "#171d23",
        "tinta": "#F5F1E6", "tinta2": "#9aa3a9",
        "linha": "rgba(245,241,230,.14)", "veu": "rgba(245,241,230,.08)",
        "veu2": "rgba(245,241,230,.16)",
        "b_ram_bg": "rgba(62,124,177,.28)", "b_ram_c": "#bcd9f0",
        "b_ok_bg": "rgba(31,169,122,.25)", "b_ok_c": "#8ff0cd",
        "b_warn_bg": "rgba(217,89,61,.25)", "b_warn_c": "#ffc4b3",
        "b_sol_bg": "rgba(242,183,5,.2)", "b_sol_c": "#F2B705",
        "cmd_c": "#9fe8c9", "marca_b": "#F2B705",
        # No escuro o gelo seria um borrao branco: aqui ele vira vidro
        # escuro, mesma funcao com o contraste invertido.
        "gelo": "rgba(23,29,35,.86)", "gelo_c": "#F5F1E6",
        "gelo_hover": "rgba(23,29,35,.96)",
    },
}

# Paleta Tarsila -- igual nos dois temas.
SOL = "#F2B705"
SOL_INK = "#231a00"
MATA = "#1FA97A"
TERRA = "#D9593D"

NAV_H = 40
RADIUS = 10
CARD_W = 104          # tile quadrado do tamanho do icone, como no CSS
CAPA_H = 104
RAIL_CARD_W = 176     # o trilho mostra descricao, entao e mais largo
RAIL_CAPA_H = 108


def css_do_tema(nome):
    c = TEMAS[nome]
    return ("""
    /* Mesma pilha de fontes do store.css da web -- inclusive a ausencia de
       fonte de emoji: a golden nao traz nenhuma, entao os emoji das
       categorias caem no mesmo fallback nas DUAS versoes. */
    window, .fundo {
      background: %(fundo)s; color: %(tinta)s;
      font-family: "DejaVu Sans", "Liberation Sans", sans-serif;
    }

    /* ---- barra de cima ---- */
    .nav { background: %(fundo)s; border-bottom: 1px solid %(linha)s; }
    .brand-name { font-size: 15px; font-weight: 800; color: %(tinta)s; }
    .brand-b { color: %(marca_b)s; font-weight: 800; }
    .nav-link {
      background: none; border: none; box-shadow: none;
      color: %(tinta2)s; font-size: 14px; padding: 6px 2px;
      border-bottom: 2px solid transparent;
    }
    .nav-link:hover { color: %(tinta)s; }
    .nav-link.on { color: %(tinta)s; border-bottom: 2px solid %(sol)s; }
    .busca {
      background: %(veu)s; border: 1px solid %(linha)s;
      border-radius: 999px; padding: 4px 10px; color: %(tinta)s;
      caret-color: %(tinta)s;
    }
    .busca:focus { border: 1px solid %(sol)s; }
    .tema-btn {
      background: %(veu)s; border: 1px solid %(linha)s;
      border-radius: 999px; padding: 2px 8px; color: %(tinta)s;
    }
    .tema-btn:hover { background: %(veu2)s; }

    /* ---- cartao ---- */
    .card { background: none; border: none; box-shadow: none; padding: 0; }
    .card-nome {
      font-size: 12px; font-weight: 700; color: %(tinta)s;
    }
    .card-desc { font-size: 11px; color: %(tinta2)s; }
    .capa {
      background: %(fundo)s; border-radius: %(radius)spx;
    }

    /* ---- selos ---- */
    .selo {
      font-size: 10px; padding: 1px 6px; border-radius: 999px;
      background: %(veu)s; color: %(tinta2)s;
    }
    .selo-ram  { background: %(b_ram_bg)s;  color: %(b_ram_c)s; }
    .selo-ok   { background: %(b_ok_bg)s;   color: %(b_ok_c)s; }
    .selo-warn { background: %(b_warn_bg)s; color: %(b_warn_c)s; }
    .selo-sol  { background: %(b_sol_bg)s;  color: %(b_sol_c)s; }

    /* ---- trilhos e titulos ---- */
    .rail-titulo { font-size: 15px; font-weight: 700; color: %(tinta)s; }
    .rail-n { font-size: 11px; color: %(tinta2)s; }
    .rail-seta {
      background: %(superficie)s; border: 1px solid %(linha)s;
      border-radius: 999px; color: %(tinta)s; padding: 0 8px;
    }
    .rail-seta:hover { background: %(veu2)s; }

    /* ---- hero ---- */
    .hero { border-radius: 14px; }
    .hero-eyebrow {
      font-size: 11px; font-weight: 700; color: %(b_sol_c)s;
    }
    .hero-titulo { font-size: 26px; font-weight: 800; color: %(tinta)s; }
    .hero-desc { font-size: 13px; color: %(tinta2)s; }
    .ponto {
      background: rgba(245,241,230,.35); border: none; border-radius: 999px;
      min-width: 8px; min-height: 8px; padding: 0;
    }
    .ponto.on { background: %(sol)s; }

    /* ---- botoes ---- */
    .btn-sol {
      background: %(sol)s; color: %(sol_ink)s; font-weight: 700;
      border: none; border-radius: 999px; padding: 6px 16px;
    }
    .btn-sol:hover { background: #ffc61f; }
    .btn-sol:disabled { background: %(veu2)s; color: %(tinta2)s; }
    .btn-ghost {
      background: %(gelo)s; color: %(gelo_c)s; border: 1px solid %(linha)s;
      border-radius: 999px; padding: 6px 16px;
    }
    .btn-ghost:hover { background: %(gelo_hover)s; }
    .btn-remove {
      background: %(terra)s; color: #fff; font-weight: 700;
      border: none; border-radius: 999px; padding: 6px 16px;
    }
    .chip {
      background: %(veu)s; color: %(tinta2)s; border: 1px solid %(linha)s;
      border-radius: 999px; padding: 3px 12px; font-size: 12px;
    }
    .chip.on { background: %(sol)s; color: %(sol_ink)s; font-weight: 700; }

    /* ---- grade / modal / rodape ---- */
    .grid-titulo { font-size: 22px; font-weight: 800; color: %(tinta)s; }
    .grid-sub { font-size: 12px; color: %(tinta2)s; }
    .vazio { font-size: 13px; color: %(tinta2)s; }
    .modal { background: %(superficie)s; border-radius: 14px; }
    .modal-titulo { font-size: 20px; font-weight: 800; color: %(tinta)s; }
    .modal-desc { font-size: 13px; color: %(tinta)s; }
    .modal-quote { font-size: 12px; color: %(tinta2)s; font-style: italic; }
    .modal-cmd { font-family: "DejaVu Sans Mono", monospace; font-size: 11px; color: %(cmd_c)s; }
    .modal-status { font-size: 11px; color: %(tinta2)s; }
    .foot { font-size: 11px; color: %(tinta2)s; }
    .toast {
      background: %(tinta)s; color: %(fundo)s; border-radius: 8px;
      padding: 8px 14px; font-size: 12px;
    }
    """ % dict(c, sol=SOL, sol_ink=SOL_INK, terra=TERRA, radius=RADIUS))


# Qual tema esta no ar. A Capa precisa disto para escolher a cor do papel
# sob os icones com transparencia -- ela desenha em Cairo, fora do CSS.
TEMA_EM_USO = "claro"


def aplica_tema(nome):
    global TEMA_EM_USO
    TEMA_EM_USO = nome if nome in TEMAS else "claro"
    prov = Gtk.CssProvider()
    prov.load_from_data(css_do_tema(nome).encode("utf-8"))
    tela = Gdk.Screen.get_default()
    Gtk.StyleContext.add_provider_for_screen(
        tela, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return prov


def tira_provider(prov):
    if prov is not None:
        Gtk.StyleContext.remove_provider_for_screen(
            Gdk.Screen.get_default(), prov)


# ------------------------------------------------------------------ capas
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


class Capa(Gtk.DrawingArea):
    """A capa do cartao: a imagem do app ou, se nao houver, o desenho gerado.

    O desenho e o mesmo blob da versao web -- mesmas cores, mesmo hash, mesmas
    formulas dos circulos -- para o app que nao tem imagem continuar com a
    cara que o usuario ja conhece.
    """

    _cache = {}

    def __init__(self, item, larg, alt, mostrar_iniciais=True, respiro=0.04,
                 fundo_sempre=False, veu=False):
        """respiro: a folga em volta da foto, como o padding do CSS.

        A web usa 4% no cartao e 8% no hero (.capa-foto / .hero-foto).
        """
        super().__init__()
        self.item = item
        self.larg = larg
        self.alt = alt
        self.mostrar_iniciais = mostrar_iniciais
        self.respiro = respiro
        # No DESTAQUE o fundo colorido fica sempre, mesmo havendo icone: o
        # titulo e a descricao de la sao cor creme, escritos para um fundo
        # escuro. Sem o fundo, o texto some -- foi o que aconteceu quando
        # tirei o blob de todo lugar de uma vez. Na web e a mesma divisao: a
        # regra que apaga o fundo (.capa.foto-ok svg.blob) vale so para o
        # cartao; o destaque tem .hero-art, que nunca sai.
        self.fundo_sempre = fundo_sempre
        # O veu do destaque: dois gradientes na cor do fundo, por cima da
        # arte. E o .hero-scrim da web, que eu nao tinha portado -- sem ele o
        # texto do destaque disputava com a cor da categoria, e a linha
        # "App em destaque" (amarela) sumia sobre um destaque amarelo.
        self.veu = veu
        self.set_size_request(larg, alt)
        # O que fica atras do icone. E o FUNDO da pagina, nao a superficie
        # branca: na web o .capa nao declara fundo nenhum, entao o icone
        # sempre apareceu sobre o fundo do aplicativo. Pintar de branco criava
        # um azulejo claro que nao existe no desenho original.
        self.papel = _rgb(TEMAS[TEMA_EM_USO]["fundo"]) + (1.0,)
        self.pixbuf = self._carrega()
        self.connect("draw", self._desenha)

    def _carrega(self):
        caminho = dados.capa_de(self.item)
        if not caminho:
            return None
        # "object-fit: contain" com padding: a foto cabe na caixa menos o
        # respiro, mantendo a proporcao.
        cx = max(1, int(self.larg * (1 - 2 * self.respiro)))
        cy = max(1, int(self.alt * (1 - 2 * self.respiro)))
        chave = (caminho, cx, cy)
        if chave in Capa._cache:
            return Capa._cache[chave]
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(caminho, cx, cy, True)
        except Exception:
            pb = None
        # Cache com teto: 173 itens em varias telas encheriam a memoria sem
        # limite, e o ganho de RAM e justamente o motivo desta versao existir.
        if len(Capa._cache) > 400:
            Capa._cache.clear()
        Capa._cache[chave] = pb
        return pb

    def _desenha(self, _w, cr):
        larg = self.get_allocated_width()
        alt = self.get_allocated_height()

        # Canto arredondado, como o border-radius do CSS.
        r = RADIUS
        cr.new_sub_path()
        cr.arc(larg - r, r, r, -math.pi / 2, 0)
        cr.arc(larg - r, alt - r, r, 0, math.pi / 2)
        cr.arc(r, alt - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 1.5 * math.pi)
        cr.close_path()
        cr.clip()

        # QUEM TEM ICONE NAO GANHA FUNDO (04/08).
        #
        # A versao web punha o blob colorido sempre, com a <img> por cima --
        # e foi assim que isto nasceu aqui, por fidelidade. Na tela, porem, o
        # icone do proprio aplicativo ja e a identidade dele, e a mancha de
        # cor atras so competia com ele.
        #
        # O fundo passa a ter uma funcao unica: dizer alguma coisa quando NAO
        # ha o que mostrar. Sem icone, o blob com as iniciais e o que evita um
        # cartao vazio.
        if self.pixbuf is None or self.fundo_sempre:
            self._blob(cr, larg, alt, com_iniciais=(self.pixbuf is None))
        if self.pixbuf is not None and self.fundo_sempre:
            px = (larg - self.pixbuf.get_width()) / 2
            py = (alt - self.pixbuf.get_height()) / 2
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, px, py)
            cr.paint()
        elif self.pixbuf is not None:
            # Papel neutro sob o icone: PNG com transparencia precisa de algo
            # atras, e esse algo deve ser a superficie do cartao, nao cor.
            cr.set_source_rgba(*self.papel)
            cr.paint()
            px = (larg - self.pixbuf.get_width()) / 2
            py = (alt - self.pixbuf.get_height()) / 2
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, px, py)
            cr.paint()

        if self.veu:
            self._scrim(cr, larg, alt)
        return False

    def _scrim(self, cr, larg, alt):
        """Os dois gradientes do .hero-scrim, na mesma ordem da web."""
        r, g, b = _rgb(TEMAS[TEMA_EM_USO]["fundo"])

        # De baixo para cima: o destaque derrete no fundo da pagina.
        de_baixo = cairo.LinearGradient(0, alt, 0, 0)
        de_baixo.add_color_stop_rgba(0.00, r, g, b, 1.0)
        de_baixo.add_color_stop_rgba(0.04, r, g, b, 1.0)
        de_baixo.add_color_stop_rgba(0.45, r, g, b, 0.0)
        cr.set_source(de_baixo)
        cr.paint()

        # Da esquerda: e este que sustenta o texto.
        da_esquerda = cairo.LinearGradient(0, 0, larg, 0)
        da_esquerda.add_color_stop_rgba(0.00, r, g, b, 0.90)
        da_esquerda.add_color_stop_rgba(0.25, r, g, b, 0.90)
        da_esquerda.add_color_stop_rgba(0.55, r, g, b, 0.45)
        da_esquerda.add_color_stop_rgba(0.78, r, g, b, 0.0)
        cr.set_source(da_esquerda)
        cr.paint()

    def _blob(self, cr, larg, alt, com_iniciais=True):
        """O mesmo desenho do capaSVG() da versao web."""
        c1, c2 = dados.cor_de(self.item)
        h = dados.hash_nome(self.item.name)
        r1 = 40 + h % 45
        r2 = 30 + (h >> 3) % 50
        r3 = 25 + (h >> 6) % 40
        x1 = (h >> 2) % 100
        y1 = (h >> 4) % 100
        x2 = (h >> 5) % 100
        y2 = (h >> 7) % 100

        # O SVG usa viewBox 0..100 com "slice": escala pelo MAIOR lado.
        k = max(larg, alt) / 100.0
        cr.save()
        cr.translate((larg - 100 * k) / 2, (alt - 100 * k) / 2)
        cr.scale(k, k)

        cr.set_source_rgb(*_rgb(c2))
        cr.rectangle(0, 0, 100, 100)
        cr.fill()

        def circulo(x, y, raio, cor, alfa):
            cr.set_source_rgba(*_rgb(cor), alfa)
            cr.arc(x, y, raio, 0, 2 * math.pi)
            cr.fill()

        circulo(x1, y1, r1, c1, 0.88)
        circulo(x2, y2, r2, "#F5F1E6", 0.12)
        circulo((x1 + 60) % 100, (y2 + 40) % 100, r3, "#101418", 0.22)
        cr.restore()

        if not (self.mostrar_iniciais and com_iniciais):
            return
        texto = dados.iniciais(self.item.name)
        cr.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(max(16, min(larg, alt) * 0.30))
        ext = cr.text_extents(texto)
        cr.move_to(larg / 2 - ext.width / 2 - ext.x_bearing,
                   alt / 2 - ext.height / 2 - ext.y_bearing)
        cr.set_source_rgba(0.96, 0.945, 0.90, 0.92)
        cr.show_text(texto)


# ----------------------------------------------------------------- selos
def selos_de(item, instalados, mini=False):
    """Os mesmos selos da versao web, na mesma ordem."""
    saida = []
    if item.ram:
        txt = ("%g GB" % (item.ram / 1024)) if item.ram >= 1024 else ("%d MB" % item.ram)
        saida.append((txt + " RAM", "selo-ram"))
    if not mini:
        if item.ptbr:
            saida.append(("PT-BR", "selo-ok"))
        if item.gamepad:
            saida.append(("🎮 Controle", "selo-ok"))
        if item.gpu3d:
            saida.append(("Requer 3D", "selo-warn"))
        if item.licenca:
            saida.append((item.licenca, "selo"))
        if not item.apt:
            saida.append(("Instalação manual", "selo-sol"))
    if item.pkg and item.pkg in instalados:
        saida.append(("✓ Instalado", "selo-ok"))
    return saida


def caixa_de_selos(item, instalados, mini=False):
    cx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    for texto, classe in selos_de(item, instalados, mini):
        r = Gtk.Label(label=texto)
        r.get_style_context().add_class("selo")
        if classe != "selo":
            r.get_style_context().add_class(classe)
        r.set_ellipsize(Pango.EllipsizeMode.END)
        cx.pack_start(r, False, False, 0)
    return cx


# ---------------------------------------------------------------- cartao
class Cartao(Gtk.Button):
    """Cartao do app: capa, nome e (nos trilhos) a descricao.

    O nome fica SEMPRE visivel embaixo -- decisao de UX da versao web, para
    publico leigo, mantida aqui de proposito.
    """

    def __init__(self, item, instalados, ao_clicar, com_descricao=False):
        super().__init__()
        self.item = item
        self.get_style_context().add_class("card")
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_tooltip_text(item.name)

        larg = RAIL_CARD_W if com_descricao else CARD_W
        alt_capa = RAIL_CAPA_H if com_descricao else CAPA_H

        cx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cx.set_size_request(larg, -1)

        pilha = Gtk.Overlay()
        self.capa = Capa(item, larg, alt_capa)
        pilha.add(self.capa)

        self.selos = caixa_de_selos(item, instalados, mini=True)
        self.selos.set_halign(Gtk.Align.START)
        self.selos.set_valign(Gtk.Align.START)
        self.selos.set_margin_top(6)
        self.selos.set_margin_start(6)
        pilha.add_overlay(self.selos)
        cx.pack_start(pilha, False, False, 0)

        nome = Gtk.Label(label=item.name, xalign=0)
        nome.get_style_context().add_class("card-nome")
        nome.set_ellipsize(Pango.EllipsizeMode.END)
        nome.set_max_width_chars(1)
        cx.pack_start(nome, False, False, 0)

        if com_descricao:
            d = Gtk.Label(label=item.desc, xalign=0)
            d.get_style_context().add_class("card-desc")
            d.set_line_wrap(True)
            d.set_lines(2)
            d.set_ellipsize(Pango.EllipsizeMode.END)
            d.set_max_width_chars(24)
            cx.pack_start(d, False, False, 0)

        self.add(cx)
        self.connect("clicked", lambda *_: ao_clicar(item))

    def repinta(self, instalados):
        """Atualiza so os selos -- e o que muda quando algo e instalado."""
        pai = self.selos.get_parent()
        if pai is None:
            return
        pai.remove(self.selos)
        self.selos = caixa_de_selos(self.item, instalados, mini=True)
        self.selos.set_halign(Gtk.Align.START)
        self.selos.set_valign(Gtk.Align.START)
        self.selos.set_margin_top(6)
        self.selos.set_margin_start(6)
        pai.add_overlay(self.selos)
        pai.show_all()
