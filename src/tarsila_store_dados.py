#!/usr/bin/env python3
"""Catalogo, estado de instalacao e acoes da Tarsila Store -- sem navegador.

Esta parte substitui, junta, duas coisas da versao WebKit:

  * o catalogo, que era lido pelo JavaScript da pagina;
  * o tarsila-backend.py, um servidor HTTP em processo separado que existia
    so para o JavaScript conseguir falar com o dpkg e com o tarsila-pkg.

Como agora a interface e GTK, ela chama o sistema direto: o servidor deixa de
fazer sentido e o processo dele deixa de existir. O tarsila-pkg (que roda com
sudo NOPASSWD e cuida do apt e dos atalhos) continua sendo o unico caminho
para instalar -- nada de privilegio novo aqui.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import unicodedata

RAIZ = os.environ.get("TARSILA_DIR", "/opt/tarsila-store")
LOJA = os.path.join(RAIZ, "loja")
CAPAS = os.path.join(LOJA, "capas")
ICONES = os.path.join(LOJA, "icons")
HELPER = os.path.join(RAIZ, "bin", "tarsila-pkg")

CONFIG = os.path.expanduser("~/.config/tarsila")
ARQ_TEMA = os.path.join(CONFIG, "store-tema")


# --------------------------------------------------------------- catalogo
def _le_catalogo(nome, variavel):
    """Le os catalogos que a versao web usava, sem alterar os arquivos.

    Eles sao .js ("window.CATALOGO_APPS = [ ... ];") mas o conteudo entre os
    colchetes e JSON puro. Recortar e usar o parser de JSON evita manter uma
    segunda copia dos dados -- catalogo duplicado seria catalogo divergente.
    """
    caminho = os.path.join(LOJA, "catalog", nome)
    try:
        with open(caminho, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return []
    ini = texto.find("[", texto.find(variavel))
    if ini < 0:
        return []
    fim = texto.rfind("]")
    if fim <= ini:
        return []
    bruto = texto[ini:fim + 1]
    try:
        return json.loads(bruto)
    except ValueError:
        pass
    # Virgula sobrando antes do fecha-colchete: o JavaScript aceita, o JSON
    # nao. O catalog-jogos.js real tem exatamente isso -- sem tolerar aqui, a
    # loja abriria com 123 apps e ZERO jogos, e o defeito passaria batido
    # porque nada quebra, so falta metade do conteudo.
    try:
        return json.loads(re.sub(r",(\s*[\]\}])", r"\1", bruto))
    except ValueError:
        return []


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


class Item:
    """Um app ou jogo do catalogo. Mesmos campos da versao web."""

    __slots__ = ("tipo", "name", "cat", "cat_label", "pkg", "apt",
                 "instalacao", "desc", "url", "ram", "ptbr", "gamepad",
                 "gpu3d", "licenca", "destaque", "trilho", "ico", "id",
                 "_busca")

    def __init__(self, **kw):
        for c in self.__slots__:
            setattr(self, c, kw.get(c))
        self._busca = " ".join(_sem_acento(x) for x in
                               (self.name, self.desc, self.pkg or "",
                                self.cat_label or ""))

    def casa(self, termo):
        return termo in self._busca


def _app(a):
    cat = a.get("category") or ""
    pkg = a.get("pkg")
    return Item(
        tipo="app", name=a.get("name", ""), cat=cat,
        cat_label=re.sub(r"^\S+\s", "", cat),
        pkg=pkg, apt=bool(pkg),
        instalacao=("apt install " + pkg) if pkg else "",
        desc=a.get("description", ""), url=a.get("url", ""),
        ram=a.get("ram", 0) or 0,
        ptbr=None, gamepad=None, gpu3d=None,
        licenca=a.get("licenca", ""), destaque=a.get("destaque", ""),
        trilho=None, ico=a.get("ico") or pkg,
        id="app:" + (pkg or a.get("name", "")))


def _jogo(j):
    pkg = j.get("pkg")
    return Item(
        tipo="jogo", name=j.get("name", ""), cat="🎮 Jogos",
        cat_label=j.get("genero") or "Jogos",
        pkg=pkg, apt=bool(j.get("apt")),
        instalacao=j.get("instalacao", ""),
        desc=j.get("description", ""), url="",
        ram=j.get("ram", 0) or 0,
        ptbr=j.get("ptbr"), gamepad=j.get("gamepad"), gpu3d=j.get("gpu3d"),
        licenca=j.get("licenca", ""), destaque=j.get("destaque", ""),
        trilho=j.get("trilho"), ico=j.get("ico"),
        id="jogo:" + (pkg or j.get("name", "")))


APPS = [_app(a) for a in _le_catalogo("catalog-apps.js", "CATALOGO_APPS")]
JOGOS = [_jogo(j) for j in _le_catalogo("catalog-jogos.js", "CATALOGO_JOGOS")]
TUDO = APPS + JOGOS

CATEGORIAS_APP = ["🌐 Internet", "💼 Escritório", "🎬 Multimídia", "🎨 Gráficos",
                  "🎓 Educação", "🎮 Games", "💻 Programação", "🛡️ Utilitários"]
TRILHOS_JOGO = ["Corrida", "Plataforma", "Estratégia", "RPG & Aventura",
                "Tiro & Ação", "Gestão & Simulação", "Arcade & Casual",
                "Educativo"]
FILTROS_APP = ["Internet", "Escritório", "Multimídia", "Gráficos",
               "Educação", "Games", "Programação", "Utilitários"]


def busca(termo):
    t = _sem_acento(termo.strip())
    if not t:
        return []
    return [x for x in TUDO if x.casa(t)]


def capa_de(item):
    """Caminho da capa, .png ou .jpg. None se nao houver (aí vai o desenho)."""
    if not item.ico:
        return None
    for ext in (".png", ".jpg"):
        p = os.path.join(CAPAS, item.ico + ext)
        if os.path.exists(p):
            return p
    return None


def iniciais(nome):
    limpo = re.sub(r"[^\w ]", "", nome or "", flags=re.UNICODE)
    partes = [p for p in limpo.split(" ") if p]
    if len(partes) > 1:
        return (partes[0][0] + partes[1][0]).upper()
    return (nome or "")[:2].upper()


# Mesmas cores da versao web, para a capa gerada sair igual.
CORES_CAPA = {
    "Internet": ("#3E7CB1", "#27567e"), "Escritório": ("#F2B705", "#b3860a"),
    "Multimídia": ("#D9593D", "#9c3a26"), "Gráficos": ("#C86B85", "#8f4359"),
    "Games": ("#1FA97A", "#136c4e"), "Jogos": ("#1FA97A", "#136c4e"),
    "Educação": ("#E88D3C", "#a95e1e"),
}


def cor_de(item):
    for chave, par in CORES_CAPA.items():
        if chave in (item.cat or ""):
            return par
    return CORES_CAPA["Internet"]


def hash_nome(s):
    """O MESMO hash da versao web, para a capa gerada ficar identica.

    Em JavaScript e (h*31 + code) >>> 0, ou seja, 32 bits sem sinal -- por
    isso a mascara aqui. Sem ela, cada app ganharia um desenho diferente do
    que o usuario ja conhece.
    """
    h = 0
    for ch in s or "":
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


# ------------------------------------------------------- estado do sistema
_lock = threading.Lock()
_tarefas = {}          # pkg -> {"acao": "instalar"|"desinstalar", "estado": ...}


def instalados():
    """Pacotes instalados segundo o dpkg. Mesma consulta que o backend fazia."""
    pkgs = [i.pkg for i in TUDO if i.pkg]
    if not pkgs:
        return set()
    try:
        saida = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package} ${Status}\n"] + pkgs,
            capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return set()
    achados = set()
    for linha in saida.splitlines():
        partes = linha.split(None, 1)
        if len(partes) == 2 and "install ok installed" in partes[1]:
            achados.add(partes[0])
    return achados


def tarefa_de(pkg):
    with _lock:
        return dict(_tarefas.get(pkg, {}))


def ocupado(pkg):
    with _lock:
        return pkg in _tarefas and _tarefas[pkg].get("estado") == "rodando"


def executar(item, acao, quando_terminar):
    """Instala ou remove em segundo plano. acao = "instalar" | "desinstalar".

    quando_terminar(pkg, ok, mensagem) e chamado ao fim, de dentro da thread
    -- quem chama e responsavel por voltar para a linha da interface antes de
    mexer em widget (a interface usa GLib.idle_add para isso).
    """
    pkg = item.pkg
    if not pkg:
        return
    with _lock:
        if pkg in _tarefas and _tarefas[pkg].get("estado") == "rodando":
            return
        _tarefas[pkg] = {"acao": acao, "estado": "rodando"}

    def trabalho():
        alvo = "install" if acao == "instalar" else "remove"
        ok = False
        msg = ""
        try:
            r = subprocess.run(["sudo", "-n", HELPER, alvo, pkg],
                               capture_output=True, text=True, timeout=1800)
            ok = (r.returncode == 0)
            msg = (r.stderr or r.stdout or "").strip().splitlines()[-1] if not ok else ""
        except subprocess.TimeoutExpired:
            msg = "demorou demais"
        except Exception as e:
            msg = str(e)
        # Confere no dpkg: o helper pode devolver 0 e mesmo assim o pacote
        # nao estar como esperado (espelho fora do ar, dependencia quebrada).
        presente = pkg in instalados()
        if acao == "instalar":
            ok = ok and presente
        else:
            ok = ok and not presente
        with _lock:
            _tarefas[pkg] = {"acao": acao, "estado": "ok" if ok else "erro"}
        quando_terminar(pkg, ok, msg)

    threading.Thread(target=trabalho, daemon=True).start()


def comando_de(item):
    if item.apt and item.pkg:
        return "sudo apt install " + item.pkg
    return item.instalacao or ""


# ------------------------------------------------------------------- tema
def le_tema():
    try:
        with open(ARQ_TEMA, encoding="utf-8") as f:
            t = f.read().strip()
            if t in ("claro", "escuro"):
                return t
    except OSError:
        pass
    return "claro"


def grava_tema(t):
    try:
        os.makedirs(CONFIG, exist_ok=True)
        with open(ARQ_TEMA, "w", encoding="utf-8") as f:
            f.write(t)
    except OSError:
        pass
