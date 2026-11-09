# <img src="assets/icon.png" width="44" align="center" alt="Garagem Icon"> Garagem — Gestão de Manutenção Preventiva Veicular

![Versão](https://img.shields.io/badge/version-1.0.0-64B5F6)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Flet](https://img.shields.io/badge/Flet-1.1.2%2B-02569B)
![License](https://img.shields.io/badge/license-MIT-green)

**Garagem** é um aplicativo com visual moderno em **Material Design 3 (Dark Mode `#121212`)**, desenvolvido em Python e **Flet**, para controle de quilometragem, alertas de revisão e histórico de manutenções preventivas de **carros e motos**, com **login Google (OAuth 2.0)** e **backup automático no próprio Google Drive do usuário**.

---

## Principais Funcionalidades

- **Multi-Veículos (Carros e Motos):** Carrossel horizontal para alternar rapidamente entre seus veículos ou cadastrar novos com plano preventivo padrão automático.
- **Atualização Rápida de Odômetro (KM):** Atualize o KM atual com um toque e recalcule instantaneamente o desgaste de todos os componentes.
- **Central de Alertas Global (Estilo Slim):** Exibe em uma única lista compacta os itens de **todos os seus veículos** que estão:
  - **Vencidos (`#EF5350`):** Ultrapassaram o KM limite de troca.
  - **Próximos do vencimento (`#FFCA28`):** Entraram nos últimos **15%** da vida útil.
- **Baixa Rápida de Manutenção:** Botão *"Concluir"* direto no card de alerta para registrar a realização do serviço, salvar no histórico e reiniciar o ciclo da peça.
- **Ficha Técnica e Histórico Completo:** Consulte especificações técnicas (ex: viscosidade do óleo, fluido, correia, relação) e adicione novos itens personalizados.
- **Login com Google & Backup no Google Drive do Usuário:**
  - Autenticação OAuth 2.0 com PKCE (`S256`).
  - Cria automaticamente a pasta **`Garagem App - Backup`** no Google Drive da pessoa logada e mantém o arquivo `garagem_backup.db` sincronizado a cada alteração.
  - Restaura automaticamente os veículos e o histórico ao fazer login em um novo dispositivo.

---

## Estrutura do Projeto

```text
garagem/
├── main.py                    # Interface gráfica Flet (Rotas /login e /home, Abas e Modais)
├── database.py                # Camada de persistência SQLite, cálculo de alertas e seed inicial
├── auth_google.py             # Módulo OAuth 2.0 Google + Backup/Restauração no Google Drive
├── requirements.txt           # Dependências do projeto (flet e flet-desktop)
├── credentials.example.json   # Exemplo de configuração de credenciais OAuth 2.0
├── PRIVACY.md                 # Política de Privacidade oficial do aplicativo
├── CHANGELOG.md               # Histórico de versões (SemVer)
├── VERSION                    # Versão atual do aplicativo (1.0.0)
└── docs/                      # Páginas HTML (Home e Política de Privacidade para GitHub Pages)
```

---

## Como Executar Localmente

### 1. Instalar as dependências

```powershell
pip install -r requirements.txt
```

### 2. Configurar o Login Google (Opcional para Modo Local)

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e ative a **Google Drive API**.
2. Em **Credenciais**, crie um **ID do cliente OAuth** do tipo **App para computador** (*Desktop app*).
3. Baixe o JSON e salve na raiz do projeto como `credentials.json` (veja o modelo em [`credentials.example.json`](credentials.example.json)), **ou** cole o `Client ID` e o `Client Secret` diretamente no modal exibido pelo aplicativo ao clicar em **"Entrar com Google"**.

### 3. Iniciar o aplicativo

```powershell
python main.py
```

---

## Política de Privacidade

Consulte nossa [Política de Privacidade completa em `PRIVACY.md`](PRIVACY.md).  
O aplicativo utiliza exclusivamente o escopo `drive.file`, acessando apenas o próprio arquivo de backup criado por ele no Google Drive do usuário autenticado.
