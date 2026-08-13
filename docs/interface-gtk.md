# tarsila-store-gtk — a loja sem navegador embutido

> **PRONTA E MEDIDA EM VM (2026-08-03).** Falta ver na TV.
> Na box nada mudou: a v3 (WebKit) continua instalada e funcionando.

A Tarsila Store v3 era uma página HTML dentro de um WebKit, mais um servidor HTTP em processo separado só para o JavaScript conseguir falar com o `dpkg`. Esta versão desenha a mesma loja em GTK3 — mesmas cores, mesmos cartões, mesmas seções, mesmo catálogo.

## O ganho, medido lado a lado

| | v3 (WebKit) | v4 (GTK) |
|---|---|---|
| Processos | **4** | **1** |
| RAM (PSS) | **327,9 MB** | **49,2 MB** |
| RAM (soma RSS) | 526,6 MB | 70,3 MB |

Os 4 processos da v3: o shell Python (200,9 MB), o backend HTTP (18,7 MB), o `WebKitWebProcess` (229,9 MB) e o `WebKitNetworkProcess` (77,6 MB).

**Sobre as duas métricas:** a soma de RSS conta a memória compartilhada em cada processo, então superestima. O **PSS** divide o compartilhado proporcionalmente e é o número honesto — é o que vale citar. Pelos dois critérios a redução é de cerca de **85%**.

Medido na VM (`kombi@kombitech`), que é mais lenta que a TV; o valor absoluto na box será outro, mas a **proporção** vale, porque as duas versões foram medidas no mesmo lugar.

## Por que o backend some junto

O `tarsila-backend.py` existia só porque JavaScript numa página não consegue chamar `dpkg` nem `sudo`. Ele fazia três coisas: consultar o `dpkg`, chamar o `tarsila-pkg` e rastrear tarefas. Um app GTK faz isso direto, então o servidor HTTP deixa de ter função — e some junto o processo dele e a porta 8474.

**Nenhum privilégio novo:** a instalação continua passando pelo `tarsila-pkg` (sudo NOPASSWD, whitelist, criação de atalhos), exatamente como antes.

## Fidelidade

O GTK3 tem motor CSS próprio, então os tokens do `store.css` atravessaram quase 1:1 — as cores dos dois temas, `--nav-h: 40px`, `--radius: 10px`, os selos, a mesma pilha de fontes.

| Peça | Situação |
|---|---|
| Navbar (marca, 4 seções, busca, tema) | ✅ |
| Hero com carrossel, pontos e troca a cada 9 s | ✅ |
| Trilhos horizontais com setas | ✅ |
| Grade com chips de filtro | ✅ |
| Modal de detalhes | ✅ |
| Toast, rodapé com contagem | ✅ |
| Capa: blob gerado + foto por cima | ✅ mesmo hash e mesmas cores da web |
| Selos (RAM, PT-BR, controle, 3D, licença, instalado) | ✅ |
| Busca sem acento, atalhos `/` e `Esc` | ✅ |
| Tema claro/escuro persistido | ✅ |

**Diferenças assumidas:**

- **Emoji aparecem como caixinhas** nas categorias (🌐 Internet). Não é regressão: a golden **não traz** fonte de emoji colorido, e a pilha de fontes do `store.css` (`system-ui, DejaVu Sans, Liberation Sans`) também não inclui nenhuma. Afeta as duas versões igualmente. Se quiser resolver, é instalar `fonts-noto-color-emoji` — e aí melhora nas duas.
- O modal é uma **janela** GTK, não uma camada sobre a página. Comporta-se igual (modal, fecha no `Esc`), mas o WM desenha a moldura dele.
- Sem `backdrop-filter` (desfoque atrás da barra): o GTK não tem equivalente. A barra usa cor sólida do tema.

## Erro que cometi e o teste pegou

Na primeira versão eu desenhava **ou** a foto **ou** o blob. A web desenha os **dois**: blob de fundo e foto por cima com respiro (`object-fit: contain` mais `padding` de 4% no cartão e 8% no hero). O resultado era cartão branco, sem a cor da categoria. Só apareceu ao **capturar a tela e comparar** — por isso instalei o ImageMagick na VM em vez de confiar no código.

## Arquivos

| Arquivo | Papel |
|---|---|
| `tarsila-store-gtk.py` | Telas e navegação |
| `tarsila_store_visual.py` | Cores, capas, cartões, selos |
| `tarsila_store_dados.py` | Catálogo, `dpkg`, instalar/remover |
| `build-deb.sh` | Monta o `.deb` 4.0.0 **no alvo** |

O catálogo é lido dos **mesmos** `loja/catalog/*.js` da versão web — recortando o JSON de dentro do `.js`. Manter uma segunda cópia dos dados seria garantir que um dia divergissem.

**Cuidado encontrado:** o `catalog-jogos.js` tem uma **vírgula sobrando** antes do `]`. O JavaScript aceita; o JSON não. Sem tolerar isso, a loja abria com 123 apps e **zero jogos** — e o defeito passaria batido, porque nada quebra, só falta metade do conteúdo.

## Implantar

O `.deb` é montado **no alvo**, aproveitando a loja já instalada (capas, ícones, catálogo, whitelist e o `tarsila-pkg`):

```bash
scp -r tarsila-store-gtk alan@<IP>:/tmp/
ssh alan@<IP> 'sudo bash /tmp/tarsila-store-gtk/build-deb.sh /tmp && sudo dpkg -i /tmp/tarsila-store_4.0.0_all.deb'
```

O `postinst` encerra qualquer `tarsila-backend.py` que tenha ficado de uma sessão anterior — sem função na v4, ele só ocuparia memória.

**Para voltar à v3:** `sudo dpkg -i` no `tarsila-store-deb/dist/tarsila-store_3.0.0_all.deb`.

## Verificado na VM

| Teste | Resultado |
|---|---|
| Catálogo | 123 apps + 50 jogos, 173 capas encontradas |
| Home (hero + trilhos) | ✅ com as capas reais |
| Grade de Jogos + chips | ✅ 50 jogos, 8 filtros |
| Busca "tux" | ✅ 7 títulos |
| Modal | ✅ capa, selos, botões, comando |
| `WM_CLASS` | `tarsila-store` — integra com a polybar |
| Erros no log | nenhum |

## Falta ver na TV

- [ ] Aparência com a fonte e o DPI reais da TV
- [ ] Rolagem dos trilhos com o controle remoto / mouse da TV
- [ ] Instalar e desinstalar um app de verdade (na VM não testei o `tarsila-pkg`, que exige a whitelist e o sudoers instalados)
- [ ] RAM na box (o número da VM serve de proporção, não de valor absoluto)
