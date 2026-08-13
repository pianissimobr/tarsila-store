# Tarsila Store

Loja de aplicativos em **GTK3 puro** para máquina fraca: instala e remove
programas de uma lista curada, com capas e descrições em português, sem
navegador embutido e sem servidor HTTP em processo separado.

Escrita para uma TV box ARM de 2 GB de RAM. A versão anterior era uma página
web dentro de um WebKit; a troca para GTK derrubou o consumo de **4 processos
/ 327,9 MB para 1 processo / 49,2 MB** (medição por PSS, `smaps_rollup`).

## Como instala programas

A loja **não chama o `apt`**. Ela chama `tarsila-pkg`, um ajudante que roda
como root por uma regra `NOPASSWD` restrita e que só aceita:

* as ações `install` e `remove`;
* nomes que casem com `^[a-z0-9][a-z0-9+._-]*$`;
* pacotes que estejam na `whitelist.txt`.

Qualquer outra coisa é recusada e registrada. É o que permite dar "instalar
programas" a um usuário leigo sem dar root a ele. A instalação em si é feita
em terminal headless (`apt-get`), e o `tarsila-pkg` cria o atalho `.desktop`
na pasta servida pelo app-manager (`/usr/share/tarsila/applications`).

## Relação com o tarsila-app-management

A loja precisa da **base do `tarsila-app-management`**: o `tarsila-atalho-criar`
(que gera o atalho curado) e o `tarsila-app-uninstall.sh` (ação "Desinstalar").

No `postinst`, a loja verifica se o app-management está instalado:

* **Instalado** → usa os helpers dele, sem duplicar nada.
* **Ausente** → instala só o **motor headless** (atalho-criar + desinstalador),
  a partir de `motor/`, **sem** a resolução gráfica que o app-management traz
  junto (o `tarsila-appfinder-yad.sh` e o `tarsila-deb-gui.py`).

## Estrutura

| Pasta | O que é |
|---|---|
| `src/` | o aplicativo GTK — janela, catálogo em memória, desenho dos cartões |
| `backend/` | o motor da loja: `tarsila-pkg` (whitelist + apt) e o handler do protocolo `tarsila://` |
| `motor/` | fallback headless (atalho-criar + desinstalador) usado quando o app-management está ausente |
| `loja/` | catálogo (`catalog/*.js`), capas, ícones e CSS |
| `desktop/` | atalhos `.desktop` e o ícone do lançador |
| `etc/sudoers.d/` | regra NOPASSWD do `tarsila-pkg` |
| `legado/` | a versão WebKit (v3) e o backend HTTP que ela usava — referência |
| `docs/` | notas da conversão para GTK |

O catálogo continua sendo lido de `loja/catalog/` **no formato JavaScript da
versão web** — de propósito. Converter para JSON criaria uma segunda cópia dos
dados, e catálogo duplicado é catálogo divergente.

### Dois atalhos, de propósito

`tarsila-store.desktop` chama `/usr/bin/tarsila-store` direto e funciona em
qualquer Debian. `tarsila-store-tarsila.desktop` passa pelos wrappers do
Tarsila OS (`tarsila-abrindo`, `tarsila-uma-janela`), que fora dele não
existem — por isso ele vai só para a grade curada do sistema, nunca para
`/usr/share/applications`.

## Construir o `.deb`

```bash
bash build-deb.sh              # sai em ./dist
bash build-deb.sh /tmp         # ou onde você quiser
```

Precisa apenas de `dpkg-deb` (`apt install dpkg-dev`). O pacote sai com ~2,1 MB,
quase tudo capas.

## Instalar

```bash
sudo dpkg -i dist/tarsila-store_4.0.0_all.deb
```

Depende de `python3`, `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`,
`sudo`.

## Rodar sem instalar

```bash
TARSILA_DIR=$PWD python3 src/tarsila-store-gtk.py
```

`TARSILA_DIR` diz onde está a pasta `loja/`; sem ela, o padrão é
`/opt/tarsila-store`.

## O que ainda não foi verificado na máquina real

Instalar e desinstalar de verdade pela interface: depende da whitelist e do
sudoers da TV, e a VM de teste não tem os dois. A interface, o catálogo
(123 apps + 50 jogos), a busca e o modal foram conferidos.

## Licença

**Ainda não definida.** Antes de publicar, decida uma — sem arquivo de licença,
o padrão legal é "todos os direitos reservados", o que impede qualquer uso por
terceiros. Note que `loja/capas/` e `loja/icons/` trazem imagens de projetos de
terceiros, cada uma com a licença do projeto de origem.
