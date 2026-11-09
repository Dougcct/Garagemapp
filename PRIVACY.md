# Política de Privacidade — Aplicativo Garagem

**Última atualização:** 09 de novembro de 2026  
**Versão:** 1.0.0

O aplicativo **Garagem** respeita a sua privacidade e foi projetado com o princípio de **armazenamento local e na nuvem própria do usuário (Zero-Server Architecture)**. Nós não possuímos servidores intermediários e não coletamos, vendemos ou compartilhamos seus dados pessoais ou informações dos seus veículos com terceiros.

---

## 1. Dados Acessados via Conta Google (OAuth 2.0)

Quando você opta por entrar no aplicativo utilizando o botão **"Entrar com Google"**, o aplicativo solicita permissão apenas para os seguintes escopos mínimos:

1. **Identificação básica do perfil (`openid`, `userinfo.email`, `userinfo.profile`):**
   - Utilizado exclusivamente para exibir seu nome, endereço de e-mail e foto de perfil no cabeçalho do aplicativo.
2. **Acesso restrito aos arquivos criados pelo próprio aplicativo no Google Drive (`https://www.googleapis.com/auth/drive.file`):**
   - Utilizado exclusivamente para criar e atualizar a pasta **`Garagem App - Backup`** e o arquivo de banco de dados **`garagem_backup.db`** dentro do **seu próprio Google Drive**.
   - O aplicativo **não tem permissão** para visualizar, ler, modificar ou excluir nenhum outro arquivo ou pasta existente no seu Google Drive.

---

## 2. Armazenamento e Segurança dos Dados

- **Armazenamento Local:** Todos os dados de veículos, quilometragem (KM) e manutenções preventivas são salvos localmente no seu dispositivo no arquivo SQLite `garagem.db`.
- **Backup no Google Drive do Usuário:** Ao autenticar sua Conta Google, uma cópia sincronizada (`garagem_backup.db`) é armazenada diretamente na sua própria conta do Google Drive, permitindo que você restaure seus dados caso troque de dispositivo.
- **Credenciais Locais:** O token de sessão OAuth (`token.json`) fica armazenado apenas localmente no seu dispositivo e pode ser removido a qualquer momento clicando em **"Trocar Conta / Sair"** dentro do aplicativo.

---

## 3. Compartilhamento de Dados

- **Nenhum dado é enviado para servidores externos:** Toda a comunicação ocorre diretamente entre o aplicativo no seu dispositivo e as APIs oficiais do Google (`googleapis.com`) sob criptografia HTTPS/TLS.
- Não utilizamos rastreadores de publicidade, analytics de terceiros nem comercializamos informações de usuários.

---

## 4. Revogação de Acesso e Exclusão de Dados

Você tem controle total sobre seus dados a qualquer momento:
- **No Aplicativo:** Clique no ícone do seu perfil no canto superior direito e selecione **"Trocar Conta / Sair"** para remover o token local.
- **No Google Drive:** Você pode excluir diretamente a pasta **`Garagem App - Backup`** no seu Google Drive quando desejar.
- **Na Conta Google:** Você pode revogar o acesso do aplicativo a qualquer momento acessando [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

---

## 5. Contato

Em caso de dúvidas sobre esta Política de Privacidade ou sobre o funcionamento do aplicativo **Garagem**, entre em contato através da aba **Issues** deste repositório no GitHub.
