# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico (SemVer)](https://semver.org/lang/pt-BR/).

---

## [1.0.0] - 2026-11-09

### Adicionado
- **Interface Mobile Dark (Material Design 3)** construída em Python com **Flet 1.1.2+**:
  - Tela inicial `/login` com identidade visual em `ft.Stack`, botão estilo pílula *"Entrar com Google"* e informações de backup em nuvem.
  - Tela principal `/home` com seletor horizontal de veículos (carrossel) e card pontilhado *"+ Adicionar novo veículo"*.
  - Barra rápida de atualização de odômetro (KM Atual) com recálculo instantâneo de todas as manutenções.
  - **Central de Alertas Global (Estilo Slim)**: monitora simultaneamente todos os veículos cadastrados, destacando manutenções vencidas (`#EF5350`) ou nos últimos 15% da vida útil (`#FFCA28`), com barra de progresso e botão rápido *"Concluir"*.
  - **Bottom Navigation Bar** com 3 abas: *Home*, *Histórico* e *Ficha Técnica*.
- **Banco de Dados Local SQLite (`database.py`)**:
  - Tabelas `veiculos`, `preventivas` e `historico` com seed inicial automático (*Civic LXS 1.8* e *Yamaha MT-03*) e planos preventivos completos por categoria (Carro e Moto).
- **Autenticação Google OAuth 2.0 Real + Backup no Google Drive (`auth_google.py`)**:
  - Fluxo OAuth 2.0 Desktop com PKCE (`S256`) e callback local automático.
  - Persistência e renovação automática de sessão (`token.json`).
  - Backup automático em segundo plano e restauração do banco SQLite diretamente na pasta `Garagem App - Backup` no Google Drive do próprio usuário (`drive.file`).
- **Documentação e Políticas**:
  - Adicionados `README.md`, `PRIVACY.md`, páginas HTML em `docs/` compatíveis com GitHub Pages e `credentials.example.json`.
