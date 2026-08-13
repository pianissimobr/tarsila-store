#!/usr/bin/env python3
"""Tarsila Store — versão GTK, sem navegador embutido.

Substitui o shell WebKit da v3. A loja continua a mesma: mesmas cores, mesmos
cartões, mesmas seções, mesmo catálogo. O que sai é o peso — o WebKit inteiro
carregado só para desenhar uma lista de aplicativos, e o servidor HTTP que
existia só para o JavaScript conversar com o dpkg.

Estrutura:
  tarsila_store_dados.py    catálogo, dpkg, instalar/remover
  tarsila_store_visual.py   cores, capas, cartões
  este arquivo              telas e navegação

Uso:  tarsila-store-gtk.py
"""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/usr/local/lib/tarsila")

import tarsila_store_dados as dados      # noqa: E402
import tarsila_store_visual as visual    # noqa: E402

INTERVALO_HERO = 9          # segundos, como na versão web
TOAST_MS = 4200


class Loja(Gtk.Window):

    def __init__(self):
        super().__init__(title="Tarsila Store")
        self.set_default_size(980, 620)
        self.set_name("tarsila-store")
        try:
            ico = os.path.join(dados.ICONES, "tarsila-store-128.png")
            if os.path.exists(ico):
                self.set_icon_from_file(ico)
        except Exception:
            pass

        self.tema = dados.le_tema()
        self._prov = visual.aplica_tema(self.tema)
        self.instalados = set()
        self.cartoes = []
        self.filtro = ""
        self.hero_i = 0
        self.hero_timer = None
        self.toast_timer = None
        self.busca_timer = None
        self.modal = None
        self.rota = "home"

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(raiz)
        raiz.pack_start(self._monta_nav(), False, False, 0)

        # O toast flutua sobre o conteúdo, como na versão web.
        self.pilha_toast = Gtk.Overlay()
        raiz.pack_start(self.pilha_toast, True, True, 0)

        self.telas = Gtk.Stack()
        self.telas.set_transition_type(Gtk.StackTransitionType.NONE)
        self.pilha_toast.add(self.telas)

        self.toast = Gtk.Label(label="")
        self.toast.get_style_context().add_class("toast")
        self.toast.set_halign(Gtk.Align.CENTER)
        self.toast.set_valign(Gtk.Align.END)
        self.toast.set_margin_bottom(18)
        self.toast.set_no_show_all(True)
        self.pilha_toast.add_overlay(self.toast)

        self.telas.add_named(self._monta_home(), "home")
        self.telas.add_named(self._monta_grade(), "grid")

        raiz.pack_start(self._monta_rodape(), False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._tecla)

        self._sincroniza()
        self._inicia_hero()
        self.mostrar_home()
        # Re-varre o dpkg de tempos em tempos, como a versão web fazia: o
        # usuário pode instalar algo por fora (terminal, .deb avulso).
        GLib.timeout_add_seconds(60, self._sincroniza_periodico)

    # ------------------------------------------------------------- topo
    def _monta_nav(self):
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        nav.get_style_context().add_class("nav")
        nav.set_size_request(-1, visual.NAV_H)
        nav.set_margin_start(14)
        nav.set_margin_end(14)

        marca = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        try:
            p = os.path.join(dados.ICONES, "tarsila-store-64.png")
            if os.path.exists(p):
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(p, 22, 22, True)
                marca.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
        except Exception:
            pass
        nome = Gtk.Label()
        nome.set_markup('<span font_weight="800">TARSILA</span>')
        nome.get_style_context().add_class("brand-name")
        marca.pack_start(nome, False, False, 0)
        store = Gtk.Label(label="store")
        store.get_style_context().add_class("brand-b")
        marca.pack_start(store, False, False, 0)
        nav.pack_start(marca, False, False, 0)

        self.links = {}
        for rota, texto in (("home", "Início"), ("apps", "Aplicativos"),
                            ("jogos", "Jogos"), ("leves", "Superleves")):
            b = Gtk.Button(label=texto)
            b.get_style_context().add_class("nav-link")
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.connect("clicked", self._clique_nav, rota)
            nav.pack_start(b, False, False, 0)
            self.links[rota] = b

        # direita: tema + busca
        self.btn_tema = Gtk.Button(label="🌙" if self.tema == "claro" else "☀️")
        self.btn_tema.get_style_context().add_class("tema-btn")
        self.btn_tema.set_relief(Gtk.ReliefStyle.NONE)
        self.btn_tema.connect("clicked", self._troca_tema)
        nav.pack_end(self.btn_tema, False, False, 0)

        self.entrada = Gtk.SearchEntry()
        self.entrada.set_placeholder_text("Buscar app ou jogo  ( / )")
        self.entrada.get_style_context().add_class("busca")
        self.entrada.set_width_chars(24)
        self.entrada.connect("search-changed", self._digitou)
        nav.pack_end(self.entrada, False, False, 0)
        return nav

    def _monta_rodape(self):
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        r.set_margin_start(14)
        r.set_margin_end(14)
        r.set_margin_top(4)
        r.set_margin_bottom(4)
        e = Gtk.Label(label="Tarsila OS · dando vida nova a computadores esquecidos",
                      xalign=0)
        e.get_style_context().add_class("foot")
        r.pack_start(e, False, False, 0)
        d = Gtk.Label(label="%d apps · %d jogos" % (len(dados.APPS), len(dados.JOGOS)))
        d.get_style_context().add_class("foot")
        r.pack_end(d, False, False, 0)
        return r

    # ------------------------------------------------------------- home
    def _monta_home(self):
        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        caixa.set_margin_start(14)
        caixa.set_margin_end(14)
        caixa.set_margin_top(12)
        caixa.set_margin_bottom(18)
        rolagem.add(caixa)

        caixa.pack_start(self._monta_hero(), False, False, 0)
        for titulo, itens in self._trilhos():
            if itens:
                caixa.pack_start(self._monta_trilho(titulo, itens), False, False, 0)
        return rolagem

    def _trilhos(self):
        """As mesmas seções da home da versão web, na mesma ordem."""
        saida = [("Novos na loja", dados.TUDO[:12]),
                 ("Superleves — rodam com 256 MB",
                  [x for x in dados.TUDO if 0 < x.ram <= 256]),
                 ("Jogos para jogar no controle",
                  [j for j in dados.JOGOS if j.gamepad])]
        for c in dados.CATEGORIAS_APP:
            saida.append((c, [a for a in dados.APPS if a.cat == c]))
        for t in dados.TRILHOS_JOGO:
            saida.append(("🎮 " + t, [j for j in dados.JOGOS if j.trilho == t]))
        return saida

    def _monta_hero(self):
        self.destaques = ([j for j in dados.JOGOS if j.destaque and j.apt][:4] +
                          [a for a in dados.APPS
                           if a.name in ("FreeTube", "AbiWord", "Pinta")])[:6]
        if not self.destaques:
            self.destaques = dados.TUDO[:6]

        self.hero_pilha = Gtk.Overlay()
        self.hero_pilha.set_size_request(-1, 210)
        self.hero_art = visual.Capa(self.destaques[0], 980, 210,
                                    mostrar_iniciais=False, respiro=0.08,
                                    fundo_sempre=True, veu=True)
        self.hero_pilha.add(self.hero_art)

        cx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cx.set_halign(Gtk.Align.START)
        cx.set_valign(Gtk.Align.CENTER)
        cx.set_margin_start(26)
        cx.set_margin_end(26)

        self.hero_eyebrow = Gtk.Label(label="", xalign=0)
        self.hero_eyebrow.get_style_context().add_class("hero-eyebrow")
        cx.pack_start(self.hero_eyebrow, False, False, 0)

        self.hero_titulo = Gtk.Label(label="", xalign=0)
        self.hero_titulo.get_style_context().add_class("hero-titulo")
        cx.pack_start(self.hero_titulo, False, False, 0)

        self.hero_selos = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        cx.pack_start(self.hero_selos, False, False, 0)

        self.hero_desc = Gtk.Label(label="", xalign=0)
        self.hero_desc.get_style_context().add_class("hero-desc")
        self.hero_desc.set_line_wrap(True)
        self.hero_desc.set_max_width_chars(60)
        cx.pack_start(self.hero_desc, False, False, 0)

        acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.hero_btn = Gtk.Button(label="▶  Instalar")
        self.hero_btn.get_style_context().add_class("btn-sol")
        acoes.pack_start(self.hero_btn, False, False, 0)
        b2 = Gtk.Button(label="Mais informações")
        b2.get_style_context().add_class("btn-ghost")
        b2.connect("clicked", lambda *_: self.abrir_modal(self.destaques[self.hero_i]))
        acoes.pack_start(b2, False, False, 0)
        cx.pack_start(acoes, False, False, 6)
        self.hero_pilha.add_overlay(cx)

        self.pontos = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pontos.set_halign(Gtk.Align.END)
        self.pontos.set_valign(Gtk.Align.END)
        self.pontos.set_margin_end(16)
        self.pontos.set_margin_bottom(12)
        for i in range(len(self.destaques)):
            p = Gtk.Button()
            p.get_style_context().add_class("ponto")
            p.set_relief(Gtk.ReliefStyle.NONE)
            p.connect("clicked", self._clique_ponto, i)
            self.pontos.pack_start(p, False, False, 0)
        self.hero_pilha.add_overlay(self.pontos)

        quadro = Gtk.Box()
        quadro.get_style_context().add_class("hero")
        quadro.pack_start(self.hero_pilha, True, True, 0)
        return quadro

    def _pinta_hero(self, i):
        if not self.destaques:
            return
        self.hero_i = i % len(self.destaques)
        d = self.destaques[self.hero_i]

        pai = self.hero_art.get_parent()
        if pai is not None:
            pai.remove(self.hero_art)
            self.hero_art = visual.Capa(d, 980, 210,
                                        mostrar_iniciais=False, respiro=0.08,
                                        fundo_sempre=True, veu=True)
            pai.add(self.hero_art)
            pai.show_all()

        self.hero_eyebrow.set_text(
            ("Jogo em destaque · " if d.tipo == "jogo" else "App em destaque · ")
            + (d.cat_label or ""))
        self.hero_titulo.set_text(d.name)
        self.hero_desc.set_text(d.desc + (" — " + d.destaque if d.destaque else ""))

        for f in self.hero_selos.get_children():
            self.hero_selos.remove(f)
        for texto, classe in visual.selos_de(d, self.instalados):
            r = Gtk.Label(label=texto)
            r.get_style_context().add_class("selo")
            if classe != "selo":
                r.get_style_context().add_class(classe)
            self.hero_selos.pack_start(r, False, False, 0)
        self.hero_selos.show_all()

        self._configura_botao(self.hero_btn, d)
        for j, p in enumerate(self.pontos.get_children()):
            ctx = p.get_style_context()
            (ctx.add_class if j == self.hero_i else ctx.remove_class)("on")

    def _inicia_hero(self):
        self._pinta_hero(0)
        self._reinicia_hero()

    def _reinicia_hero(self):
        if self.hero_timer:
            GLib.source_remove(self.hero_timer)
        self.hero_timer = GLib.timeout_add_seconds(
            INTERVALO_HERO, self._avanca_hero)

    def _avanca_hero(self):
        self._pinta_hero(self.hero_i + 1)
        return True

    def _clique_ponto(self, _b, i):
        self._pinta_hero(i)
        self._reinicia_hero()

    # ----------------------------------------------------------- trilho
    def _monta_trilho(self, titulo, itens):
        sec = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        topo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        t = Gtk.Label(label=titulo, xalign=0)
        t.get_style_context().add_class("rail-titulo")
        topo.pack_start(t, False, False, 0)
        n = Gtk.Label(label="%d títulos" % len(itens))
        n.get_style_context().add_class("rail-n")
        topo.pack_start(n, False, False, 0)

        setas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        ant = Gtk.Button(label="‹")
        prox = Gtk.Button(label="›")
        for b in (ant, prox):
            b.get_style_context().add_class("rail-seta")
            b.set_relief(Gtk.ReliefStyle.NONE)
        setas.pack_start(ant, False, False, 0)
        setas.pack_start(prox, False, False, 0)
        topo.pack_end(setas, False, False, 0)
        sec.pack_start(topo, False, False, 0)

        rol = Gtk.ScrolledWindow()
        rol.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        rol.set_size_request(-1, visual.RAIL_CAPA_H + 74)
        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for it in itens:
            c = visual.Cartao(it, self.instalados, self.abrir_modal,
                              com_descricao=True)
            self.cartoes.append(c)
            linha.pack_start(c, False, False, 0)
        rol.add(linha)
        sec.pack_start(rol, False, False, 0)

        def desliza(_b, sinal):
            aj = rol.get_hadjustment()
            aj.set_value(aj.get_value() + sinal * aj.get_page_size() * 0.85)
        ant.connect("clicked", desliza, -1)
        prox.connect("clicked", desliza, 1)
        return sec

    # ------------------------------------------------------------ grade
    def _monta_grade(self):
        rol = Gtk.ScrolledWindow()
        rol.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        cx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        cx.set_margin_start(14)
        cx.set_margin_end(14)
        cx.set_margin_top(12)
        cx.set_margin_bottom(18)
        rol.add(cx)

        self.grade_titulo = Gtk.Label(label="", xalign=0)
        self.grade_titulo.get_style_context().add_class("grid-titulo")
        cx.pack_start(self.grade_titulo, False, False, 0)

        self.grade_sub = Gtk.Label(label="", xalign=0)
        self.grade_sub.get_style_context().add_class("grid-sub")
        cx.pack_start(self.grade_sub, False, False, 0)

        self.chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cx.pack_start(self.chips, False, False, 0)

        self.grade = Gtk.FlowBox()
        self.grade.set_valign(Gtk.Align.START)
        self.grade.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grade.set_max_children_per_line(30)
        self.grade.set_column_spacing(14)
        self.grade.set_row_spacing(14)
        self.grade.set_homogeneous(True)
        cx.pack_start(self.grade, True, True, 0)

        self.vazio = Gtk.Label(
            label="Nada encontrado com esse nome.\n"
                  "Tente outra palavra — ou navegue pelas categorias no menu.")
        self.vazio.get_style_context().add_class("vazio")
        self.vazio.set_no_show_all(True)
        cx.pack_start(self.vazio, False, False, 10)
        return rol

    def _monta_chips(self, chips):
        for f in self.chips.get_children():
            self.chips.remove(f)
        if not chips:
            self.chips.hide()
            return
        self.chips.show()

        def faz(rotulo, valor):
            b = Gtk.Button(label=rotulo)
            b.get_style_context().add_class("chip")
            b.set_relief(Gtk.ReliefStyle.NONE)
            if self.filtro == valor:
                b.get_style_context().add_class("on")
            b.connect("clicked", self._clique_chip, valor, chips)
            return b

        self.chips.pack_start(faz("Todos", ""), False, False, 0)
        for c in chips:
            self.chips.pack_start(faz(c, c), False, False, 0)
        self.chips.show_all()

    def _clique_chip(self, _b, valor, chips):
        self.filtro = valor
        self._monta_chips(chips)
        self._pinta_grade()

    def mostrar_grade(self, titulo, sub, itens, chips=None):
        self.grade_itens = itens
        self.grade_titulo.set_text(titulo)
        self.grade_sub.set_text(sub)
        self._monta_chips(chips)
        self._pinta_grade()
        self.telas.set_visible_child_name("grid")

    def _pinta_grade(self):
        for f in self.grade.get_children():
            self.grade.remove(f)
        self.cartoes = [c for c in self.cartoes if c.get_parent() is not None]
        vis = [x for x in self.grade_itens
               if not self.filtro
               or self.filtro in (x.cat or "") or x.trilho == self.filtro]
        for it in vis:
            c = visual.Cartao(it, self.instalados, self.abrir_modal)
            self.cartoes.append(c)
            self.grade.add(c)
        self.grade.show_all()
        self.vazio.set_visible(not vis)

    # ------------------------------------------------------- navegacao
    def _clique_nav(self, _b, rota):
        self.entrada.set_text("")
        self.ir(rota)

    def ir(self, rota):
        self.filtro = ""
        self.rota = rota
        for r, b in self.links.items():
            ctx = b.get_style_context()
            (ctx.add_class if r == rota else ctx.remove_class)("on")
        if rota == "apps":
            self.mostrar_grade(
                "Aplicativos",
                "%d apps curados para ARM — instalação com um clique" % len(dados.APPS),
                dados.APPS, dados.FILTROS_APP)
        elif rota == "jogos":
            self.mostrar_grade(
                "Jogos",
                "%d jogos open source testados em hardware modesto" % len(dados.JOGOS),
                dados.JOGOS, dados.TRILHOS_JOGO)
        elif rota == "leves":
            leves = sorted([x for x in dados.TUDO if 0 < x.ram <= 512],
                           key=lambda x: x.ram)
            self.mostrar_grade(
                "Superleves",
                "Títulos que rodam confortavelmente com até 512 MB de RAM",
                leves, None)
        else:
            self.mostrar_home()

    def mostrar_home(self):
        self.rota = "home"
        for r, b in self.links.items():
            ctx = b.get_style_context()
            (ctx.add_class if r == "home" else ctx.remove_class)("on")
        self.telas.set_visible_child_name("home")

    def _digitou(self, entrada):
        if self.busca_timer:
            GLib.source_remove(self.busca_timer)
        self.busca_timer = GLib.timeout_add(160, self._faz_busca,
                                            entrada.get_text())

    def _faz_busca(self, texto):
        self.busca_timer = None
        q = texto.strip()
        if not q:
            self.ir("home")
            return False
        res = dados.busca(q)
        self.filtro = ""
        for b in self.links.values():
            b.get_style_context().remove_class("on")
        self.mostrar_grade("Resultados para “%s”" % q,
                           "%d títulos encontrados" % len(res), res, None)
        return False

    def _tecla(self, _w, ev):
        nome = Gdk.keyval_name(ev.keyval)
        if nome == "slash" and not self.entrada.has_focus():
            self.entrada.grab_focus()
            return True
        if nome == "Escape":
            if self.modal is not None:
                self.modal.destroy()
                self.modal = None
            else:
                self.entrada.set_text("")
            return True
        return False

    def _troca_tema(self, _b):
        self.tema = "escuro" if self.tema == "claro" else "claro"
        dados.grava_tema(self.tema)
        visual.tira_provider(self._prov)
        self._prov = visual.aplica_tema(self.tema)
        self.btn_tema.set_label("🌙" if self.tema == "claro" else "☀️")

    # ---------------------------------------------------------- modal
    def abrir_modal(self, item):
        if self.modal is not None:
            self.modal.destroy()
        d = Gtk.Dialog(title=item.name, transient_for=self, modal=True)
        d.set_default_size(560, 420)
        d.get_style_context().add_class("modal")
        self.modal = d
        self.modal_item = item

        cx = d.get_content_area()
        cx.set_spacing(10)
        cx.set_margin_start(18)
        cx.set_margin_end(18)
        cx.set_margin_top(12)
        cx.set_margin_bottom(14)

        cx.pack_start(visual.Capa(item, 520, 150,
                                  mostrar_iniciais=False, respiro=0.08,
                                  fundo_sempre=True),
                      False, False, 0)

        cat = Gtk.Label(label=item.cat + (" · " + item.cat_label
                                          if item.tipo == "jogo" else ""), xalign=0)
        cat.get_style_context().add_class("hero-eyebrow")
        cx.pack_start(cat, False, False, 0)

        t = Gtk.Label(label=item.name, xalign=0)
        t.get_style_context().add_class("modal-titulo")
        cx.pack_start(t, False, False, 0)

        self.modal_selos = visual.caixa_de_selos(item, self.instalados)
        cx.pack_start(self.modal_selos, False, False, 0)

        desc = Gtk.Label(label=item.desc, xalign=0)
        desc.get_style_context().add_class("modal-desc")
        desc.set_line_wrap(True)
        cx.pack_start(desc, False, False, 0)

        if item.destaque:
            q = Gtk.Label(label="“%s”" % item.destaque, xalign=0)
            q.get_style_context().add_class("modal-quote")
            q.set_line_wrap(True)
            cx.pack_start(q, False, False, 0)

        self.modal_status = Gtk.Label(label="", xalign=0)
        self.modal_status.get_style_context().add_class("modal-status")
        cx.pack_start(self.modal_status, False, False, 0)

        acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.modal_btn = Gtk.Button()
        acoes.pack_start(self.modal_btn, False, False, 0)
        copiar = Gtk.Button(label="Copiar comando")
        copiar.get_style_context().add_class("btn-ghost")
        copiar.connect("clicked", lambda *_: self._copiar(item))
        acoes.pack_start(copiar, False, False, 0)
        if item.url:
            site = Gtk.Button(label="Site oficial")
            site.get_style_context().add_class("btn-ghost")
            site.connect("clicked", lambda *_: self._abrir_site(item.url))
            acoes.pack_start(site, False, False, 0)
        cx.pack_start(acoes, False, False, 4)

        cmd = Gtk.Label(label=dados.comando_de(item), xalign=0)
        cmd.get_style_context().add_class("modal-cmd")
        cmd.set_selectable(True)
        cx.pack_start(cmd, False, False, 0)

        self._configura_botao(self.modal_btn, item)
        self._atualiza_status_modal()

        def fechou(*_a):
            self.modal = None
        d.connect("destroy", fechou)
        d.show_all()

    def _atualiza_status_modal(self):
        if self.modal is None:
            return
        ocupado = self.modal_item.pkg and dados.ocupado(self.modal_item.pkg)
        self.modal_status.set_text(
            "Trabalhando em segundo plano — pode continuar navegando."
            if ocupado else "")

    # -------------------------------------------------- instalar/remover
    def _configura_botao(self, botao, item):
        ctx = botao.get_style_context()
        for c in ("btn-sol", "btn-remove", "btn-ghost"):
            ctx.remove_class(c)
        botao.set_sensitive(True)
        for cid in getattr(botao, "_conexoes", []):
            try:
                botao.disconnect(cid)
            except Exception:
                pass
        botao._conexoes = []

        def liga(fn):
            botao._conexoes.append(botao.connect("clicked", lambda *_: fn(item)))

        if not item.apt:
            ctx.add_class("btn-sol")
            botao.set_label("Instalação manual")
            liga(self._instalacao_manual)
            return
        if item.pkg and dados.ocupado(item.pkg):
            ctx.add_class("btn-sol")
            botao.set_sensitive(False)
            botao.set_label("Removendo…" if item.pkg in self.instalados
                            else "Instalando…")
            return
        if item.pkg in self.instalados:
            ctx.add_class("btn-remove")
            botao.set_label("🗑  Desinstalar")
            liga(self._desinstalar)
        else:
            ctx.add_class("btn-sol")
            botao.set_label("▶  Instalar")
            liga(self._instalar)

    def _instalacao_manual(self, item):
        self._copiar(item)
        self.diz("Este título não está no apt — instruções copiadas: "
                 + (item.instalacao or ""))

    def _instalar(self, item):
        dados.executar(item, "instalar", self._terminou)
        self.diz("Instalando %s em segundo plano…" % item.name)
        self._repinta()

    def _desinstalar(self, item):
        dados.executar(item, "desinstalar", self._terminou)
        self.diz("Removendo %s…" % item.name)
        self._repinta()

    def _terminou(self, pkg, ok, msg):
        """Chamado de dentro da thread do dados.executar."""
        GLib.idle_add(self._terminou_na_interface, pkg, ok, msg)

    def _terminou_na_interface(self, pkg, ok, msg):
        item = next((x for x in dados.TUDO if x.pkg == pkg), None)
        nome = item.name if item else pkg
        t = dados.tarefa_de(pkg)
        if ok:
            if t.get("acao") == "instalar":
                self.diz("✓ %s instalado — o atalho já está na área de trabalho."
                         % nome)
            else:
                self.diz("%s removido do computador." % nome)
        else:
            self.diz("Falha com %s: verifique a internet e tente de novo." % nome)
        self._sincroniza()
        return False

    def _sincroniza(self):
        self.instalados = dados.instalados()
        self._repinta()

    def _sincroniza_periodico(self):
        self._sincroniza()
        return True

    def _repinta(self):
        vivos = []
        for c in self.cartoes:
            if c.get_parent() is None:
                continue
            c.repinta(self.instalados)
            vivos.append(c)
        self.cartoes = vivos
        if self.destaques:
            self._pinta_hero(self.hero_i)
        if self.modal is not None:
            pai = self.modal_selos.get_parent()
            if pai is not None:
                pai.remove(self.modal_selos)
                self.modal_selos = visual.caixa_de_selos(self.modal_item,
                                                         self.instalados)
                pai.pack_start(self.modal_selos, False, False, 0)
                pai.reorder_child(self.modal_selos, 3)
                pai.show_all()
            self._configura_botao(self.modal_btn, self.modal_item)
            self._atualiza_status_modal()

    # --------------------------------------------------------- auxiliares
    def _copiar(self, item, forcado=None):
        cmd = forcado or dados.comando_de(item)
        try:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(cmd, -1)
        except Exception:
            pass
        self.diz("Comando copiado: " + cmd)

    @staticmethod
    def _abrir_site(url):
        try:
            Gtk.show_uri_on_window(None, url, Gdk.CURRENT_TIME)
        except Exception:
            pass

    def diz(self, msg):
        self.toast.set_text(msg)
        self.toast.show()
        if self.toast_timer:
            GLib.source_remove(self.toast_timer)
        self.toast_timer = GLib.timeout_add(TOAST_MS, self._apaga_toast)

    def _apaga_toast(self):
        self.toast.hide()
        self.toast_timer = None
        return False


def main():
    GLib.set_application_name("Tarsila Store")
    try:
        Gdk.set_program_class("tarsila-store")   # WM_CLASS para a polybar
    except Exception:
        pass
    janela = Loja()
    janela.show_all()
    janela.toast.hide()
    Gtk.main()


if __name__ == "__main__":
    main()
