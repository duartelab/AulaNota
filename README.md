# AulaNota

Notas de estudo automáticas a partir das **legendas (CC) de aulas no YouTube**, processadas **100% no seu computador**.

Sem gravar áudio, sem gravar tela, sem baixar vídeo, sem conta, sem nuvem e sem custo.

```
extensão no navegador
        ↓  (apenas o ID do vídeo + metadados da página, via 127.0.0.1)
daemon local em Python
        ↓  (baixa somente a legenda já disponível no vídeo)
Ollama transforma a transcrição em uma nota estruturada
        ↓
Markdown salvo no seu vault, com índice e busca local
```

## O que ele faz

- Detecta o vídeo do YouTube em aulas abertas diretamente ou incorporadas em ambientes virtuais de aprendizagem, Moodle, Udemy, Alura, Hotmart e players que usam proxy/embed.
- Usa a legenda **que já existe** no vídeo, manual ou automática. Se o navegador não entregar o texto, o daemon baixa apenas o arquivo de legenda com `yt-dlp` — nunca o vídeo.
- Gera uma nota com resumo, conceitos-chave, desenvolvimento com timestamps, fórmulas, exemplos, dúvidas, tarefas/prazos e perguntas de revisão.
- Salva em `~/Estudos/<ID_DA_DISCIPLINA>/<AAAA-MM-DD>_<id_da_aula>.md`, com cabeçalho YAML e índice por disciplina.
- Indexa tudo em SQLite FTS5 para busca local.
- Mantém uma fila persistente: se o daemon reiniciar, o trabalho continua.

## O que ele não faz

- Não grava a tela, o áudio nem o vídeo da aula.
- Não envia o conteúdo da aula para a internet. O único tráfego é até o YouTube (para ler a legenda) e da extensão para `127.0.0.1`.
- Não funciona em vídeo **sem** CC. Nesse caso, avisa e não inventa conteúdo.
- Não contorna paywall, DRM ou controle de acesso. Use apenas em conteúdo ao qual você tem acesso legítimo.

## Compatibilidade com navegadores

| Navegador | Suporte | Observação |
| --- | --- | --- |
| **Google Chrome** | **Recomendado** | Caminho mais testado para detecção e leitura de legendas. |
| **Brave** | Compatível | Baseado em Chromium; usa a mesma extensão e o mesmo instalador do Chrome. |
| **Microsoft Edge** | Compatível | Mesmo procedimento do Chrome. |
| **Vivaldi** | Compatível | Mesmo procedimento do Chrome. |
| **Chromium** | Compatível | Mesmo procedimento do Chrome. |
| **Firefox 128+** | Suportado com ressalvas | Usa `manifest.firefox.json`; carregamento temporário (veja abaixo). |
| **Safari** | Não suportado | — |
| **Opera** | Não testado | Pode funcionar por ser Chromium, mas não há validação. |

### Por que o Chrome é recomendado

O fluxo de captura de legendas foi validado no Chrome. Como Brave, Edge, Vivaldi e Chromium usam o mesmo motor, a extensão Manifest V3 deve funcionar neles sem alterações. O instalador já aceita esses nomes:

```bash
./instalar.sh chrome    # Chrome, Chromium, Edge ou Vivaldi
./instalar.sh brave     # Brave
./instalar.sh firefox   # Firefox
```

No Brave, se o popup não conseguir falar com o daemon ou a página da aula se comportar de forma estranha, verifique as proteções do **Brave Shields** para o site da aula e permita o acesso a `127.0.0.1`. Isso não costuma ser necessário, mas é o primeiro ajuste a testar.

## Requisitos

- Linux com `systemd` de usuário (o instalador atual usa esse formato).
- Python 3.11 ou superior.
- [Ollama](https://ollama.com/) rodando localmente.
- Um modelo local, por exemplo:
  ```bash
  ollama pull qwen3:4b-instruct
  ```
  Alternativa mais rápida e enxuta: `qwen2.5:3b-instruct`.
- Um navegador compatível (de preferência Chrome ou outro Chromium).
- Opcional: Obsidian ou qualquer editor que leia Markdown.
- Opcional: `curl` para rodar os testes de ponta a ponta.

O `yt-dlp` é instalado automaticamente em `.venv` pelo instalador e é usado apenas para baixar legendas quando necessário.

## Instalação

```bash
git clone <URL_DO_REPOSITORIO> aulanota
cd aulanota
./instalar.sh chrome
```

O instalador:

1. cria o vault em `~/Estudos`;
2. instala `yt-dlp` em `.venv` (opcional);
3. escolhe o manifesto correto da extensão;
4. instala e inicia o serviço `aulanota.service` no systemd de usuário;
5. cria o comando `aulanota` em `~/.local/bin`.

Depois, carregue a extensão:

### Chrome, Brave, Edge, Vivaldi ou Chromium

1. Abra a página de extensões:
   - Chrome/Chromium: `chrome://extensions`
   - Brave: `brave://extensions`
   - Edge: `edge://extensions`
   - Vivaldi: `vivaldi://extensions`
2. Ative o **Modo do desenvolvedor**.
3. Clique em **Carregar sem compactação**.
4. Escolha a pasta `~/aulanota/extension`.

### Firefox

1. Rode `./instalar.sh firefox`.
2. Abra `about:debugging#/runtime/this-firefox`.
3. Clique em **Carregar extensão temporária**.
4. Escolha `~/aulanota/extension/manifest.json`.

No Firefox, a extensão carregada dessa forma é temporária e precisa ser carregada novamente após reiniciar o navegador.

### Conferir a instalação

```bash
aulanota doctor
```

O comando mostra o estado do Python, SQLite, Ollama, modelo, `yt-dlp`, daemon e índice.

> Abas abertas **antes** de instalar ou atualizar a extensão precisam ser recarregadas com `F5`. Depois de editar arquivos da extensão, clique em **Reload** na página de extensões.

## Uso

1. Abra a aula e dê play por alguns segundos para o player carregar as legendas.
2. Clique no ícone do **AulaNota**.
3. Confira o vídeo e o CC detectados.
4. Clique em **Gerar notas desta aula**.
5. Em alguns minutos, a nota aparece em `~/Estudos/<DISCIPLINA>/` e no índice da disciplina.

O popup mostra as três últimas notas; clicar em uma delas copia o caminho do arquivo.

### Opções do popup

- **Automático nas aulas**: gera a nota quando uma aula com legenda é detectada.
- **Também no YouTube**: inclui páginas do próprio YouTube no modo automático.
- **Gerar de todas as abas de aula abertas**: envia várias aulas de uma vez.
- **Gerar a partir do link**: último recurso quando a página não é reconhecida.

### Já assisti às aulas: como gerar as notas depois

Não é preciso reassistir. A legenda é lida quando a página da aula é aberta.

1. Abra a página da aula (ou o link do vídeo) e espere o player carregar.
2. Clique no ícone do AulaNota.
3. Clique em **Gerar notas desta aula**.

Para várias aulas:

- abra cada aula em uma aba e use **Gerar de todas as abas de aula abertas**; ou
- use a linha de comando com `aulanota lote`.

### Identificação de disciplina e data

- A **data** é a do dia em que a nota foi gerada.
- A **disciplina** vem de `regras.toml` (expressões regulares sobre URL + título). Exemplo genérico:

```toml
[[disciplina]]
id = "CALC1"
nome = "Cálculo I"
padroes = ["moodle\\.exemplo\\.edu\\.br/course/view\\.php\\?id=123", "C[áa]lculo\\s*I"]
```

- Sem regra, o AulaNota identifica pelo domínio/URL: `UD-<curso>` (Udemy), `AL-<curso>` (Alura), `M<id>` (Moodle), `HM-<produto>` (Hotmart) e, no restante, `G-<título>-<hash>`.
- Se não gostar do identificador, renomeie a pasta e a linha `id_disciplina` na nota.

## Linha de comando

```bash
aulanota doctor                     # diagnóstico do ambiente
aulanota serve                      # inicia o daemon (o systemd já cuida)
aulanota add "https://youtu.be/..." --pagina "https://ava.exemplo/course/view.php?id=123" --disciplina CALC1
aulanota add "https://youtu.be/..." --legenda aula.vtt --titulo "Aula 7"
aulanota lote aulas.txt             # uma aula por linha
aulanota listar
aulanota buscar "derivada implícita"
aulanota indice
```

Formato do `aulas.txt` (linhas com `#` são ignoradas):

```
https://www.youtube.com/watch?v=abc123 https://ava.exemplo/course/view.php?id=123 CALC1
https://www.youtube.com/watch?v=def456 https://ava.exemplo/course/view.php?id=123 CALC1
```

Se todas forem da mesma disciplina:

```bash
aulanota lote aulas.txt --disciplina CALC1
```

Vídeos restritos podem exigir `--cookies-from-browser firefox` (ou `chrome`, `brave`). A extensão também usa a sessão do navegador.

## Estrutura

```
aulanota/
  aulanota/                 daemon e CLI (Python stdlib)
  extension/                extensão Chrome/Firefox
  exemplos/                 legendas e nota fictícias para teste
  systemd/                  unidade do systemd
  instalar.sh               instalador
  testar.sh                 teste de ponta a ponta
  regras.toml               disciplinas e configuração
  README.md
~/Estudos/                  vault (fora do repositório)
  CALC1/
    _indice.md
    2026-10-25_aula-07.md
  .aulanota/notas.db        índice FTS5
  .aulanota/fila/           fila persistente
```

## Nota gerada

Cabeçalho YAML: `id_disciplina`, `disciplina`, `id_aula`, `video_id`, `data`, `hora`, `titulo`, `canal`, `idioma_legenda`, `legenda_automatica`, `pagina`, `duracao`, `modelo`, `tags`.

Seções: Resumo · Conceitos-chave · Desenvolvimento (com `hh:mm:ss`) · Fórmulas · Exemplos · Pontos de dúvida · Tarefas e prazos · Perguntas de revisão.

Prazos nunca são convertidos em data: fica o que o professor disse (por exemplo, `"na próxima sexta-feira"`), com o timestamp e a evidência. O modelo é instruído a não inventar; timestamps fora dos marcadores reais da legenda são descartados.

## Configuração (`regras.toml`)

```toml
[geral]
vault = "~/Estudos"
idioma = "pt-BR"

[notas]
incluir_transcricao = false   # true = anexa a transcrição em texto no fim da nota
max_palavras_chunk = 900
sobreposicao_palavras = 100

[modelo]
nome = "qwen3:4b-instruct"
url = "http://127.0.0.1:11434"
num_ctx = 4096
temperatura = 0.2

[legendas]
# Vazio para vídeos públicos/não listados. Para vídeos privados:
# cookies = "firefox"   # ou "chrome", "chromium", "brave"
cookies = ""

[servidor]
host = "127.0.0.1"
porta = 8790
```

O vault padrão fica em `~/Estudos`, mas pode ser alterado em `[geral]`.

## Privacidade

- O daemon escuta apenas em `127.0.0.1`.
- O Ollama roda localmente; nenhum texto de aula é enviado para serviços externos.
- A extensão não tem telemetria.
- A extensão lê a URL, o título, iframes e o HTML da página da aula para localizar IDs de vídeos do YouTube. Esses dados não são enviados para fora; apenas o ID do vídeo e metadados da página vão para o daemon local.
- Cookies, quando configurados, ficam na sua máquina e são usados somente para acessar vídeos aos quais você já tem acesso.
- O repositório não contém notas, credenciais, cookies, histórico de navegação ou dados pessoais. As legendas e notas de exemplo são fictícias.
- O áudio da aula nunca é capturado; o vídeo nunca é baixado para gerar a nota.

## Uso responsável e direitos autorais

Este é um projeto de **estudo e uso pessoal**.

- As aulas, transcrições e demais materiais pertencem aos seus autores e instituições.
- As notas geradas são um resumo para revisão pessoal. Não redistribua, publique ou venda o conteúdo das aulas sem autorização.
- Respeite os termos de uso das plataformas, as regras da instituição e a legislação de direitos autorais.
- Não use a ferramenta para contornar paywall, DRM, controle de acesso ou restrições de segurança.
- O AulaNota não é afiliado ao YouTube, ao Ollama, ao Obsidian ou a qualquer instituição de ensino.
- Notas geradas por IA podem conter erros. Revise fórmulas, datas e prazos antes de usar.

## Verificar se o salvamento está funcionando

```bash
cd ~/aulanota
./testar.sh              # gera uma nota de teste e confere arquivo + índice + banco
./testar.sh reinicio     # derruba o daemon no meio e confirma a retomada
```

O resultado esperado termina com `SALVAMENTO OK` e mostra o caminho do arquivo.

A nota de teste fica em `~/Estudos/TESTE/`; apague essa pasta quando quiser.

Para acompanhar em tempo real:

```bash
journalctl --user -u aulanota -f
```

Você deve ver `trabalho <id> na fila` quando a extensão envia e `<id> ok -> /caminho/nota.md` ao salvar.

## Solução de problemas

| Sintoma | Causa / solução |
| --- | --- |
| Popup diz "daemon offline" | `systemctl --user status aulanota`; `journalctl --user -u aulanota -n 50` |
| Popup mostra "CC ainda não detectado" | A aba foi aberta antes da extensão: recarregue com `F5`. Se persistir, use o campo "cole o link do vídeo" no popup |
| AVA que usa proxy do YouTube | Já suportado: a extensão extrai o ID e o daemon baixa a legenda |
| Vídeo privado da instituição | Defina `[legendas] cookies = "firefox"` (ou `"chrome"`, `"brave"`) em `regras.toml`; o `yt-dlp` lê os cookies locais |
| Clicou em Gerar e nada aconteceu | Veja o log do daemon. Se não houver `POST /notas`, recarregue a extensão na página de extensões e a página da aula (`F5`) |
| Nota não aparece no vault | Rode `./testar.sh` para isolar: se o teste passa, o problema é a captura do CC naquela página |
| "Sem legendas" / badge × | O vídeo não tem CC. Não há como gerar nota sem texto; ative o CC no player ou use um vídeo com legenda |
| Legenda vazia em vídeo restrito | A extensão usa sua sessão; confirme que está logado e que o vídeo toca. Se persistir, recarregue a página |
| Brave não se comunica com o daemon | Verifique o Brave Shields para o site da aula e permita `127.0.0.1`; confirme `aulanota doctor` |
| Nota demora | O tempo depende do modelo e do hardware. Uma aula de 18 min pode levar alguns minutos; o processamento é em segundo plano, você pode continuar assistindo. Para mais velocidade, use `qwen2.5:3b-instruct` |
| Timestamps aproximados | O modelo só pode usar marcadores reais; ele escolhe o mais próximo. Confira no vídeo |
| "yt-dlp não encontrado" no `add` | Rode `./instalar.sh` ou use a extensão (não precisa de `yt-dlp`) |
| yt-dlp pede login | Use `--cookies-from-browser firefox` (veja `aulanota add --help`) ou a extensão |

## Limites conhecidos

- Sem CC, não há nota.
- Um vídeo por nota; playlists geram uma nota por aula processada.
- O modelo 4B é bom para resumir, mas revise fórmulas e prazos (a nota traz a evidência e o timestamp).
- Gravar aulas ao vivo e redistribuir conteúdo não faz parte do escopo; o uso é pessoal e local.
- O projeto é voltado a Linux com systemd. Outros sistemas exigem adaptação do instalador.

## Desinstalar

```bash
systemctl --user disable --now aulanota
rm ~/.config/systemd/user/aulanota.service
rm -f ~/.local/bin/aulanota
# depois remova a extensão no navegador e, se quiser, ~/aulanota
```
