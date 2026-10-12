# Colocar o sistema na internet de graça, sem cartão (Render + Neon)

Resultado: um endereço fixo `https://sistema-avaliacoes-xxxx.onrender.com` que os alunos abrem de qualquer
lugar (celular, casa ou laboratório), sem depender da rede da faculdade e sem deixar seu computador ligado.

| Parte | Serviço gratuito | Para quê |
|---|---|---|
| Sistema (telas + servidor) | **Render** (plano Free, sem cartão) | roda o programa |
| Banco de dados | **Neon** (plano Free, sem cartão, 0,5 GB) | guarda alunos, provas, respostas e imagens |
| Código | **GitHub** (conta gratuita) | o Render busca o programa de lá |

Tempo: de 30 a 45 minutos na primeira vez.

---

## 1. Criar o banco no Neon
1. Acesse **neon.com**, clique em *Sign up* e entre com sua conta Google ou GitHub.
2. Crie um projeto: nome `avaliacoes`, Postgres na versão sugerida e **região AWS US East (N. Virginia)**.
   Precisa ser a mesma região do Render.
3. Na tela do projeto, clique em **Connect** e copie a *connection string*. É um texto parecido com
   `postgresql://neondb_owner:XXXX@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require`.
   **Guarde-o bem: é a "chave" do seu banco.**

## 2. Levar os dados do seu computador para o Neon
Pule este passo se quiser começar com o banco vazio.
1. **Feche o sistema** no seu computador.
2. Dê dois cliques em **`migrar-para-internet.bat`** e cole a *connection string* do Neon.
3. No final aparece algo como *"Pronto! 1520 registros copiados. 65 usuários, 4 avaliações, 12 imagens."*
   Todos os logins e senhas continuam iguais.

## 3. Colocar o código no GitHub
1. Crie uma conta em **github.com** (gratuita).
2. Clique em **+ → New repository**, dê o nome `sistema-avaliacoes`, marque **Private** e clique em *Create repository*.
3. Na página do repositório, clique em **uploading an existing file**. Arraste para lá **todo o conteúdo da pasta
   do sistema** (as pastas `backend`, `frontend`, `deploy` e os arquivos soltos, como `Dockerfile` e `render.yaml`)
   e clique em *Commit changes*.
   - O seu banco (`avaliacoes.db`) **não** deve ir para o GitHub. Ele já está no Neon.
   - Não envie as pastas `node_modules` e `.venv`, se existirem.

## 4. Criar o serviço no Render
1. Acesse **render.com** e clique em *Get Started* → entre com a **conta do GitHub**.
2. Clique em **New → Blueprint**, autorize o Render a ver o repositório `sistema-avaliacoes` e selecione-o.
3. O Render lê o arquivo `render.yaml` e pede dois valores:
   - **DATABASE_URL**: cole a *connection string* do Neon;
   - **ADMIN_SENHA**: uma senha para o usuário `admin`. Ela só é usada se o banco estiver vazio.
4. Clique em **Apply** e aguarde de 5 a 10 minutos, até aparecer **Live**.
5. Abra o endereço `https://sistema-avaliacoes-xxxx.onrender.com`. Ele também aparece no QR code do painel.

## 5. No dia da prova
- O plano gratuito **"dorme" depois de 15 minutos sem acesso**, e o primeiro acesso leva cerca de 1 minuto para acordar.
  **Abra o sistema uns 5 minutos antes da aula.** Depois de acordado, ele não dorme enquanto houver alunos usando.
- Para que ele nunca durma, cadastre o endereço `https://SEU-ENDERECO.onrender.com/api/saude` num serviço gratuito de
  monitoramento, como **UptimeRobot** ou **cron-job.org** (também sem cartão), para ser acessado **a cada 10 minutos**.
  As 750 horas mensais do plano gratuito cobrem um serviço ligado o mês inteiro.
- O processador do plano gratuito é pequeno. O momento mais pesado é quando todos fazem login ao mesmo tempo.
  O sistema já vem ajustado para isso: no 1º login de cada aluno a senha é convertida para um formato mais leve.
  Se notar lentidão logo no início, peça que entrem em duas levas, com 1 minuto de diferença. Responder e salvar pesa pouco.

## 6. Atualizar para uma versão nova
No GitHub, envie os arquivos novos da mesma forma (*Add file → Upload files*, substituindo os antigos).
O Render percebe a mudança e atualiza sozinho em alguns minutos. **Os dados ficam no Neon e não são apagados.**

## 7. Cuidados
- **Backup:** no Neon, em *Branches*, dá para criar uma cópia do banco. O plano gratuito também permite voltar o banco a
  um momento das últimas horas. Antes de uma prova importante, crie uma *branch* como cópia de segurança.
- **Limites do Neon gratuito:** 0,5 GB, suficiente para milhares de alunos, provas e imagens, e 100 horas de
  processamento por mês. O banco "dorme" sozinho quando ninguém usa e só gasta enquanto há acesso.
- **Segurança:** troque a senha do `admin` no primeiro acesso e ative o **código de convite** para cadastro de professores.
- Os planos gratuitos podem mudar. Se um dia o Render deixar de servir, o mesmo banco do Neon funciona com outra
  hospedagem, ou você volta a rodar no seu computador com o `iniciar.bat`.
