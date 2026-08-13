import json, os, re, subprocess, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

RAIZ      = Path(os.environ.get("TARSILA_DIR", "/opt/tarsila-store"))
LOJA      = RAIZ / "loja"
WHITELIST = RAIZ / "whitelist.txt"
HELPER    = RAIZ / "bin" / "tarsila-pkg"
PORTA     = int(os.environ.get("TARSILA_PORTA", "8474"))
RE_PKG    = re.compile(r"^[a-z0-9][a-z0-9+._-]*$")

tarefas = {}                 # pkg -> {"estado": fila|executando|ok|erro, "acao": ..., "msg": ...}
trava = threading.Lock()

def whitelist():
    try:
        return set(WHITELIST.read_text().split())
    except FileNotFoundError:
        return set()

def instalados():
    """Consulta o dpkg de verdade — a fonte da verdade do sistema."""
    wl = whitelist()
    if not wl:
        return []
    try:
        saida = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Package}\t${db:Status-Status}\n", *sorted(wl)],
            capture_output=True, text=True).stdout
    except FileNotFoundError:
        return []
    return [l.split("\t")[0] for l in saida.splitlines()
            if l.endswith("\tinstalled")]

def notificar(titulo, corpo):
    """Notificação de sistema: a confirmação chega ao usuário mesmo que a
    loja esteja minimizada/fechada (o toast da página só aparece com ela
    aberta e com o store.js atual carregado)."""
    try:
        subprocess.run(["notify-send", "-a", "Tarsila Store",
                        "-i", "system-software-install", titulo, corpo],
                       timeout=5)
    except Exception:
        pass

def executar(pkg, acao):
    with trava:
        tarefas[pkg] = {"estado": "executando", "acao": acao, "msg": ""}
    # tarsila-pkg roda como root (sudo NOPASSWD) e cuida de tudo: apt
    # install/remove E os atalhos curados em /usr/share/tarsila/{games,
    # applications} + ícone em /usr/share/tarsila/icons — o backend, que
    # roda como usuário comum, não tem escrita nesses diretórios.
    r = subprocess.run(["sudo", "-n", str(HELPER),
                        "install" if acao == "instalar" else "remove", pkg],
                       capture_output=True, text=True)
    ok_dpkg = pkg in instalados()
    sucesso = (acao == "instalar" and ok_dpkg) or (acao == "remover" and not ok_dpkg)
    if sucesso:
        with trava:
            tarefas[pkg] = {"estado": "ok", "acao": acao, "msg": ""}
        if acao == "instalar":
            notificar("Instalação concluída",
                      f"'{pkg}' foi instalado — o atalho já está na área de trabalho.")
        else:
            notificar("Remoção concluída", f"'{pkg}' foi removido do computador.")
    else:
        with trava:
            tarefas[pkg] = {"estado": "erro", "acao": acao,
                            "msg": (r.stderr or r.stdout or "").strip()[-400:]}
        notificar("Não foi possível concluir",
                  f"Falha ao {'instalar' if acao == 'instalar' else 'remover'} '{pkg}'. "
                  "Verifique a internet e tente de novo.")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(LOJA), **kw)

    def log_message(self, *a):  # silencioso
        pass

    def end_headers(self):
        # html/js/css/catálogo sempre frescos: sem isto o Chromium usa
        # cache heurístico e pode rodar um store.js VELHO por dias (foi
        # o que escondia a confirmação de instalação - o polling de
        # /api/tarefas nem existia na cópia em cache). As capas
        # (imagens) podem continuar cacheáveis.
        if not self.path.startswith("/capas/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=200):
        corpo = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/instalados":
            return self._json({"instalados": instalados()})
        if self.path == "/api/tarefas":
            with trava:
                return self._json({"tarefas": tarefas})
        return super().do_GET()

    def do_POST(self):
        m = re.match(r"^/api/(instalar|desinstalar)/([a-z0-9][a-z0-9+._-]*)$", self.path)
        if not m:
            return self._json({"erro": "rota inválida"}, 404)
        acao = "instalar" if m.group(1) == "instalar" else "remover"
        pkg = m.group(2)
        if not RE_PKG.match(pkg) or pkg not in whitelist():
            return self._json({"erro": "pacote fora do catálogo"}, 403)
        with trava:
            if tarefas.get(pkg, {}).get("estado") == "executando":
                return self._json({"erro": "já em andamento"}, 409)
            tarefas[pkg] = {"estado": "fila", "acao": acao, "msg": ""}
        threading.Thread(target=executar, args=(pkg, acao), daemon=True).start()
        return self._json({"ok": True, "pkg": pkg, "acao": acao})

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    print(f"Tarsila Store backend em http://127.0.0.1:{PORTA}")
    srv.serve_forever()
