# Sistema de Avaliações Online

Sistema para cadastrar **provas, testes e simulados** por **escola, turma e disciplina**, com questões
**objetivas e dissertativas**, gabarito, **correção automática** e **feedback questão a questão** para o aluno.

- **Frontend:** Vue 3 + Vite (sem bibliotecas pesadas, funciona bem no celular)
- **Backend:** Python (FastAPI + SQLAlchemy)
- **Banco:** SQLite (padrão, zero configuração) ou PostgreSQL (para hospedar na nuvem)

## Funcionalidades

- **QR code de acesso** (v18): o aluno escaneia com o celular, entra com RM e senha e cai direto nas provas dele. Aparece na janela do `iniciar.bat`, no botão **📱 QR code para os alunos** do painel e na página `/qrcode` (para projetar ou imprimir). Usa automaticamente o endereço da rede (ou o endereço da internet, quando publicado).

- **Imagens nas questões** (v17): no enunciado, nas alternativas, na resposta esperada e na explicação. Botão 🖼 Imagem, colar print (Ctrl+V) ou arrastar o arquivo; as figuras de um .docx importado entram automaticamente. O aluno clica para ampliar sem sair da prova. As imagens são reduzidas (máx. 1600 px) e guardadas no próprio banco, então vão junto ao copiar a pasta ou fazer backup.

**Perfis e visibilidade**
- **Professor:** cria a própria conta na tela de login ("Criar conta de professor") e tem uma **área
  particular**: cadastra as suas escolas, disciplinas, turmas e alunos e as suas avaliações. Nenhum outro
  professor vê nada disso. Um guia de "primeiros passos" aparece até ele completar o básico.
- **Administrador:** vê tudo. Pode fechar o autocadastro ou exigir um **código de convite** (Cadastros →
  Professores), criar professores, trocar perfis, redefinir senhas e, se quiser, cadastrar escolas/disciplinas
  da instituição e liberá-las a professores por **vínculos**.
- **Aluno:** não se cadastra; o professor importa a lista. Um mesmo RM pode estar em turmas de professores
  diferentes (uma conta, várias matrículas) e vê as avaliações de todas as suas turmas.

**Professor / administrador**
- Cadastro de escolas, turmas, disciplinas, alunos e professores
- **Importação de alunos** de planilha (.xlsx/.xls), .csv, .txt, .json ou texto colado, em qualquer layout.
  O sistema reconhece as colunas RM, nome e senha pelo cabeçalho (RM, RA, matrícula, nome do aluno…) ou pelo
  conteúdo, e mostra uma prévia para você confirmar. Senha vazia = senha padrão ou a própria RM.
  Modelos em Cadastros → Alunos
- **Exclusão em lote:** excluir os alunos selecionados, todos da turma (digitando o nome da turma para
  confirmar) ou **desfazer uma importação** inteira
- **Importação de avaliação** de Word (.docx), PDF com texto, .txt ou texto colado, com prévia editável.
  Reconhece questões numeradas, alternativas com letra e o gabarito marcado com `*`, `(X)`, negrito,
  `Resposta: C` ou uma tabela `GABARITO 1-A 2-C` no final. Questão sem alternativas vira dissertativa
  (`Resposta esperada:`, `Palavras-chave:`, `Peso:` / `(2 pontos)`, `Explicação:`). Há um modelo .docx para baixar.
  PDF escaneado (imagem) não tem texto: use o .docx original ou cole o texto
- Avaliações com período (abertura/encerramento), tempo limite em minutos, tipo (prova/simulado/teste)
- Questões objetivas (2 a 10 alternativas, uma correta) e dissertativas (gabarito + palavras-chave)
- **Nota total e pesos:** o professor informa a nota total da avaliação (ex.: 10) e o peso de cada questão;
  o sistema reparte a nota proporcionalmente. Pesos padrão sugeridos: objetiva 1, dissertativa 2 (ajustáveis).
  Uma tabela mostra quanto vale cada questão e avisa se alguma dissertativa ficou com peso menor ou igual ao de uma objetiva
- **Monitoramento da prova** (pode ser desligado por avaliação): registra IP, navegador, dispositivo e tela,
  horários de início e envio, tempo gasto, cada troca de aba ou saída da janela (com duração), fechamento ou
  recarga da página e abertura em outro navegador ou dispositivo. O professor acompanha ao vivo e vê a linha do tempo
- Opções para embaralhar a ordem das questões e das alternativas (cada aluno recebe uma ordem diferente)
- Escolha de quando o aluno vê o feedback: **após o encerramento** (padrão), logo após enviar, ou manualmente
- Resultados em tempo real: quem está respondendo, quem enviou, notas, média, maior e menor nota
- Estatística por questão: % de acerto e quantos alunos marcaram cada alternativa
- Revisão das dissertativas: ajustar a nota automática e deixar um comentário para o aluno
- Botões para encerrar a avaliação na hora, reabrir a prova de um aluno (queda de energia, por exemplo) e duplicar uma avaliação para outra turma
- Exportar as notas em CSV (abre no Excel), incluindo tempo gasto, saídas, tempo fora, fechamentos, IP e navegador

**Painel de análises (menu "Análises")**
- Filtros por escola, turma, disciplina, período e corte de aprovação (50/60/70/75% da nota)
- Indicadores: média geral, aprovação, participação e alunos em atenção
- Evolução da média por avaliação (uma linha por turma) e comparativo entre turmas
- Distribuição das notas por faixa e aproveitamento de objetivas × dissertativas
- "Conteúdos para retomar": as 10 questões com pior aproveitamento e o erro mais comum (distrator)
- Mapa de notas aluno × avaliação e lista de alunos em atenção (média baixa, queda forte, faltas, saídas da prova)
- Exporta a planilha dos alunos e imprime o painel

**Aluno**
- Lista das avaliações da sua turma (disponível, agendada, enviada)
- Uma questão por vez, com mapa de navegação e cronômetro
- **Salvamento automático** de cada resposta. Se a internet cair, o sistema tenta de novo sozinho, e dá para fechar o navegador e continuar depois
- Envio automático quando o tempo acaba (controlado pelo servidor, então o aluno não consegue burlar)
- Aviso de monitoramento antes de começar (o aluno precisa marcar "estou ciente"), faixa fixa durante a prova e
  alerta na tela sempre que volta depois de sair da aba ou da janela
- Feedback: nota, acertos e erros, o próprio relatório de monitoramento, a resposta marcada, a correta, a explicação do professor e o comentário da revisão

### Distribuição da nota
Valor da questão = nota total × peso da questão ÷ soma dos pesos. Exemplo: nota 10, quatro objetivas de peso 1
e uma dissertativa de peso 2 → soma 6 → cada objetiva vale 1,67 e a dissertativa 3,32 (o arredondamento é
ajustado para a soma fechar em 10). Numa dissertativa com acerto parcial, o aluno recebe a fração correspondente
do valor dela. Depois que algum aluno inicia a prova, pesos e nota total ficam travados.

### O que o monitoramento detecta (e o que não detecta)
O navegador informa quando a página da prova **deixa de ser visível** (troca de aba, minimizar, bloquear o
celular, trocar de app) e quando a **janela perde o foco** (clicar em outro programa ou janela ao lado).
Saídas com menos de 1 segundo são ignoradas. O fechamento ou recarga da página é enviado no momento em que
acontece, e uma nova abertura com outro navegador, dispositivo ou IP é marcada como "outro dispositivo".
Por segurança, **nenhum site consegue ver o que o aluno abriu ou pesquisou** em outras abas ou programas, nem
detectar um segundo aparelho que ele use sem abrir a prova (um celular ao lado, por exemplo). Os registros
indicam que houve saída e por quanto tempo; cabe ao professor avaliar.

### Como funciona a correção automática
- **Objetivas:** compara a resposta com o gabarito.
- **Dissertativas:** o professor cadastra palavras-chave (uma por linha; sinônimos separados por `|`,
  ex.: `gás carbônico|CO2`). Cada palavra-chave vale uma fração igual da nota. A comparação ignora acentos
  e maiúsculas e tolera pequenos erros de digitação. O aluno recebe "Pontos abordados: … / Faltou abordar: …".
  A nota é uma **sugestão**: o professor pode revisá-la (a lista de resultados marca "revisar").

## Rodar no computador da escola (jeito mais fácil)

O pacote já vem com as telas compiladas, então **só é preciso o Python** (3.10 ou mais novo).

1. Instale o Python em python.org. No Windows, marque **"Add python.exe to PATH"** na instalação.
2. **Windows:** dê dois cliques em `iniciar.bat`. **Linux/Mac:** rode `./iniciar.sh`.
3. Na primeira vez ele instala as dependências (1 a 2 minutos, precisa de internet). Depois abre na hora.
4. A janela mostra dois endereços: `http://localhost:8000` para você e `http://IP-DO-COMPUTADOR:8000`
   para os alunos, que precisam estar **na mesma rede ou Wi-Fi**. Se o Windows perguntar sobre o Firewall,
   clique em **Permitir**.
   Se no próprio computador abre, mas nos outros não: rode **uma vez** o `liberar-firewall.bat` (aceite a pergunta
   de administrador) e confira se todos estão na mesma rede. Redes Wi-Fi de "convidados" costumam bloquear a
   comunicação entre aparelhos.
5. Os dados ficam no arquivo `backend/avaliacoes.db`. Para fazer backup, copie esse arquivo com o sistema fechado.
6. **Levar para outro computador:** feche o sistema, copie a pasta inteira e rode o `iniciar` no computador novo
   (que também precisa ter o Python instalado). Todos os dados vão junto. O script refaz sozinho o ambiente
   do Python (`backend/.venv`), que não funciona se for copiado de outra máquina.

Dicas: deixe o computador ligado na tomada e com a suspensão desativada durante a prova, e prefira ligá-lo
ao roteador por cabo. Para 60 alunos no mesmo Wi-Fi, o gargalo costuma ser o roteador, não o sistema.

## Quando a rede da escola bloqueia: link pela internet

Se os outros computadores dão `ERR_CONNECTION_TIMED_OUT` mesmo com o Firewall liberado, a rede provavelmente
isola os aparelhos. Use o **`iniciar-internet.bat`** (Linux/Mac: `./iniciar-internet.sh`): ele liga o sistema
e cria um link público gratuito (`https://....trycloudflare.com`) pelo serviço Quick Tunnel da Cloudflare, sem
cadastro. Os alunos acessam esse link de qualquer rede, inclusive pelo 4G do celular. Os dados continuam no seu
computador.

- Deixe as duas janelas abertas durante a prova. O link muda cada vez que o túnel é reiniciado e fica salvo em `link-internet.txt`.
- Limite do serviço gratuito: 200 requisições simultâneas, o que é suficiente para uma turma de 60. Ele não tem
  garantia de disponibilidade, então teste antes da aula.
- Precisa de internet no computador do professor.

## Rodar no computador (modo desenvolvimento)

Pré-requisitos: Python 3.10+ e Node.js 18+.

```bash
# 1) Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed            # (opcional) cria dados de demonstração
uvicorn app.main:app --reload --port 8000

# 2) Frontend (em outro terminal)
cd frontend
npm install
npm run dev                   # abre em http://localhost:5173
```

Para usar na rede da escola (os alunos acessam pelo IP do seu computador):

```bash
cd frontend && npm run build              # gera frontend/dist
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
# alunos acessam http://IP-DO-COMPUTADOR:8000
```

**Acessos da demonstração:** `admin` / `admin123` · `professor` / `prof123` · alunos `aluno1` a `aluno5` / `1234`.
Sem a demonstração, só o administrador é criado (login `admin`, senha `admin123`, ou os valores das
variáveis `ADMIN_LOGIN`/`ADMIN_SENHA`). **Troque a senha no primeiro acesso** (link "Trocar senha" no topo).

Atualizando de uma versão anterior: basta substituir os arquivos. As colunas novas são criadas sozinhas no
banco na próxima inicialização, sem perder dados.

Testes automáticos: `cd backend && pip install pytest httpx && pytest`

## Variáveis de ambiente

| Variável | Padrão | Para que serve |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./avaliacoes.db` | Banco. Para a nuvem use PostgreSQL: `postgresql://usuario:senha@host/banco` |
| `SECRET_KEY` | (fixa) | **Obrigatório trocar em produção.** Assina os tokens de login |
| `ADMIN_LOGIN` / `ADMIN_SENHA` | `admin` / `admin123` | Administrador criado na primeira execução |
| `BCRYPT_ROUNDS` | `10` | Custo do hash de senha. Use `8` em servidores com pouca CPU |
| `SEED_DEMO` | — | `1` cria os dados de demonstração ao iniciar |
| `WEB_CONCURRENCY` | `1` | Número de processos (workers) no Docker |

## Online de graça e SEM cartão: Render + Neon
Passo a passo completo em **[GUIA-RENDER.md](GUIA-RENDER.md)**. Resumo:
1. **Neon** (banco PostgreSQL gratuito, sem cartão): crie o projeto na região *AWS US East (N. Virginia)* e copie a *connection string*.
2. **`migrar-para-internet.bat`**: copia alunos, provas, respostas e imagens do seu computador para o Neon (logins e senhas iguais).
3. **GitHub** (repositório privado) + **Render → New → Blueprint**: informe `DATABASE_URL` e `ADMIN_SENHA`.
4. Abra uns 5 minutos antes da aula (o plano gratuito dorme após 15 min sem uso) ou use um monitor gratuito para mantê-lo acordado.

## Online 24h de graça: Oracle Cloud Always Free (exige cartão)
Uma máquina virtual só sua, sempre ligada, com o mesmo SQLite do seu computador, HTTPS automático e backup diário.
Passo a passo completo em **[GUIA-ORACLE.md](GUIA-ORACLE.md)**. Resumo:
1. Crie a conta (região São Paulo ou Vinhedo) e uma VM **Ubuntu, VM.Standard.A1.Flex, 2 OCPU / 12 GB**; baixe a chave `.key`.
2. Libere as portas TCP **80 e 443** na *Security List* da rede da VM.
3. No Windows, rode **`publicar-oracle.bat`** (IP + chave). Ele envia o sistema e o seu banco e instala tudo
   (`deploy/oracle/instalar.sh`: Python, serviço systemd, Caddy com HTTPS, firewall, backup diário).
4. Acesse `https://IP-COM-TRACOS.sslip.io`. Para atualizar depois, rode o mesmo `.bat`: os dados do servidor são mantidos.

## Detalhes do Render + Neon

O app vira **um único serviço**: o backend Python serve a API e também as telas do Vue já compiladas.

1. **Banco (Neon, gratuito):** crie uma conta em neon.com, crie um projeto e copie a *connection string*
   (`postgresql://...`). O plano gratuito tem 0,5 GB, o que dá para dezenas de milhares de respostas.
2. **Código:** suba esta pasta para um repositório no GitHub.
3. **Render (gratuito):** em render.com vá em **New → Blueprint** e escolha o repositório. O arquivo `render.yaml`
   já configura tudo. Preencha `DATABASE_URL` (a string do Neon) e `ADMIN_SENHA`.
4. Abra o endereço `https://sistema-avaliacoes-xxxx.onrender.com` e entre como `admin`.

**Cuidados no plano gratuito do Render**
- O serviço "dorme" após 15 minutos sem uso e leva cerca de 1 minuto para acordar. **Abra o sistema uns
  5 minutos antes da aula.** Depois que acorda, fica ativo enquanto houver alunos usando.
- A CPU é pequena (0,1 vCPU). O momento mais pesado é quando os 40 alunos fazem login juntos, porque a
  verificação de senha usa CPU. Por isso o `render.yaml` já define `BCRYPT_ROUNDS=8`. Responder e salvar
  as questões pesa pouco.
- Não use SQLite no Render gratuito: o disco é apagado a cada reinício. Por isso o banco fica no Neon.

**Outras opções gratuitas**
- **Google Cloud Run + Neon:** usa o mesmo `Dockerfile`, tem 1 vCPU inteira e uma cota mensal gratuita
  generosa. Exige cadastrar uma conta de faturamento (cartão).
- **Oracle Cloud "Always Free":** uma máquina virtual ARM própria (hoje com 2 OCPU e 12 GB). É a opção mais
  robusta e pode usar SQLite no disco, mas exige cartão para verificação e mais conhecimento para configurar
  (rodar `docker build -t avaliacoes . && docker run -d -p 80:8000 -v dados:/app/backend avaliacoes`).

## Capacidade

Teste de carga feito neste projeto: **60 alunos simultâneos** fazendo login, iniciando a prova, alterando
respostas várias vezes e enviando, num total de 1.140 requisições em 15 segundos, **sem nenhuma falha**
(servidor com 1 processo e SQLite em modo WAL). Numa prova real a carga é bem menor, porque cada aluno salva
uma resposta a cada vários segundos.

## Estrutura

```
backend/
  app/main.py            inicialização, serve o frontend compilado
  app/models.py          tabelas (escolas, turmas, disciplinas, usuários, avaliações, questões, tentativas, respostas)
  app/correcao.py        correção automática (objetivas e dissertativas)
  app/servicos.py        distribuição da nota pelos pesos, metadados e monitoramento
  app/routers/cadastros.py   login e cadastros
  app/routers/avaliacoes.py  área do professor (avaliações, questões, resultados, revisão)
  app/routers/aluno.py       área do aluno (responder, embaralhamento, envio, feedback)
  tests/                 testes automáticos
frontend/src/
  views/prof/            Painel, Cadastros, Editor de avaliação, Resultados
  views/aluno/           Minhas avaliações, Responder, Resultado
  components/Feedback.vue    relatório de correção (usado pelo aluno e pelo professor)
  components/Monitoramento.vue  metadados e linha do tempo da prova
Dockerfile, render.yaml  implantação
```
