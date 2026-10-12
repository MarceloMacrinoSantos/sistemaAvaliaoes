# Colocar o sistema online na Oracle Cloud (Always Free)

Resultado: um endereço **https://** fixo, sempre ligado, que os alunos acessam de qualquer lugar (celular,
casa ou escola), sem precisar deixar o seu computador ligado. Tempo total: de 30 a 60 minutos na primeira vez.

> O plano Always Free é gratuito de verdade, mas a Oracle **pede um cartão de crédito** no cadastro (só para
> verificação). Enquanto você usar apenas recursos marcados como *Always Free*, nada é cobrado.

---

## 1. Criar a conta
1. Acesse **oracle.com/cloud/free** e clique em *Start for free*.
2. Preencha os dados e o cartão.
3. **Região inicial (Home Region):** escolha **Brazil East (São Paulo)** ou **Brazil Southeast (Vinhedo)**.
   Essa escolha **não pode ser mudada depois**, e servidores no Brasil deixam o sistema mais rápido para os alunos.
4. Aguarde o e-mail de conta ativada (pode levar alguns minutos).

## 2. Criar a máquina virtual (VM)
1. No painel: **☰ → Compute → Instances → Create instance**.
2. **Name:** `avaliacoes`.
3. **Image and shape → Edit:**
   - *Image*: **Canonical Ubuntu 24.04** (ou 22.04).
   - *Shape*: **Ampere → VM.Standard.A1.Flex**, com **2 OCPUs e 12 GB de memória**. Precisa aparecer o selo *Always Free-eligible*.
4. **Networking:** deixe criar a rede padrão e marque **Assign a public IPv4 address**.
5. **Add SSH keys:** escolha *Generate a key pair for me* e clique em **Save private key**. Guarde o arquivo
   `.key` num lugar seguro: sem ele você não entra no servidor.
6. Clique em **Create**. Quando ficar verde (*Running*), anote o **Public IP address**.

> **"Out of capacity"?** É comum com a máquina Ampere gratuita. Tente outro *Availability Domain* na mesma
> tela, tente mais tarde ou comece com 1 OCPU e 6 GB (dá conta de uma turma de 60 alunos).

## 3. Liberar o acesso pela internet (portas 80 e 443)
1. Na página da VM, clique no nome da **Virtual cloud network** → **Security Lists** → *Default Security List*.
2. **Add Ingress Rules** e crie **uma regra** com:
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: `TCP`
   - Destination Port Range: `80,443`
3. Salve. (O firewall interno do Ubuntu é liberado automaticamente pelo instalador.)

## 4. Publicar o sistema (Windows, com um clique)
1. **Feche o sistema** no seu computador, se estiver aberto. Assim o banco é enviado completo.
2. Na pasta do sistema, dê dois cliques em **`publicar-oracle.bat`**.
3. Informe o **IP público** da VM e o caminho do arquivo **`.key`**. Você pode arrastar o arquivo para a janela.
   O script guarda essas duas informações para as próximas vezes.
4. Se perguntar *"Are you sure you want to continue connecting?"*, digite `yes`.
5. Aguarde. Na primeira vez leva de 3 a 8 minutos. No final aparece:
   ```
   Sistema: rodando ✔
   Endereço: https://129-146-10-20.sslip.io
   Administrador: login admin  senha XXXXXXXX
   ```
6. Abra o endereço no navegador. O certificado HTTPS é emitido no primeiro acesso e pode levar até 1 minuto.

**Seus dados vão junto:** o banco do seu computador (`backend\avaliacoes.db`) é enviado e importado **na primeira
publicação**. A partir daí, o banco oficial é o do servidor. Com o banco importado, os logins e senhas continuam
os mesmos do seu computador (inclusive o admin); a senha de admin exibida só vale quando o banco é novo.

> O endereço `…sslip.io` é gratuito e funciona na hora. Para usar um domínio próprio (ex.: `provas.suaescola.com.br`),
> crie no DNS um registro **A** apontando para o IP da VM e rode no servidor:
> `sudo bash ~/sistema-avaliacoes/deploy/oracle/instalar.sh provas.suaescola.com.br`

### Sem Windows ou fazendo à mão
```bash
# no seu computador
scp -i chave.key sistema-avaliacoes.zip ubuntu@IP_DA_VM:~
scp -i chave.key backend/avaliacoes.db ubuntu@IP_DA_VM:~     # opcional: seus dados atuais
ssh -i chave.key ubuntu@IP_DA_VM
# já dentro do servidor
sudo apt install -y unzip && unzip sistema-avaliacoes.zip
cd sistema-avaliacoes && sudo bash deploy/oracle/instalar.sh
```

## 5. Atualizar para uma versão nova
Extraia a nova versão numa pasta, copie para ela o `publicar-oracle.cfg` da pasta antiga (ou informe IP e chave de
novo) e rode **`publicar-oracle.bat`**. Antes de trocar o código, o instalador faz uma cópia do banco. **Nenhum dado
do servidor é apagado.**

## 6. Backups
- O servidor faz um **backup automático todo dia** e guarda os últimos 30, em `/var/backups/avaliacoes/`.
- Para baixar o mais recente para o seu computador:
  ```
  scp -i chave.key "ubuntu@IP_DA_VM:/var/backups/avaliacoes/*.db" .
  ```

## 7. Cuidados
- **Troque a senha do admin** no primeiro acesso e ative o **código de convite** para o cadastro de professores
  (Cadastros → Professores). Assim nenhum desconhecido cria conta.
- **Máquinas ociosas podem ser recuperadas:** pela política da Oracle, uma VM Always Free com uso muito baixo por
  7 dias seguidos pode ser desligada. Para evitar isso, você pode mudar a conta para *Pay As You Go*
  (Billing → Upgrade). Continua sem cobrança enquanto usar só recursos Always Free, mas **configure um alerta de
  orçamento** (Billing → Budgets) de, por exemplo, R$ 1.
- Comandos úteis no servidor (entre com `ssh -i chave.key ubuntu@IP_DA_VM`):
  | Para… | Comando |
  |---|---|
  | reiniciar o sistema | `sudo systemctl restart avaliacoes` |
  | ver erros | `sudo journalctl -u avaliacoes -n 100` |
  | ver a senha inicial do admin | `sudo grep ADMIN_SENHA /etc/avaliacoes.env` |
  | tornar um usuário administrador | `cd /opt/avaliacoes/backend && sudo -u avaliacoes env $(sudo cat /etc/avaliacoes.env) ../venv/bin/python tornar_admin.py LOGIN` |
