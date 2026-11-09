# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico (SemVer)](https://semver.org/lang/pt-BR/).

---

## [2.0.0] - 2026-11-09

### Adicionado
- **Fase 1 (CRUD Completo de Veículos e Ficha Técnica Interativa)**:
  - Edição e exclusão de veículos diretamente pelo menu de 3 pontos nos cards do carrossel.
  - Ações diretas nos cards da *Ficha Técnica*: botões **Concluir** (dar baixa antes do alerta) e **Editar/Excluir** item preventivo.
- **Fase 2 (Controle Financeiro `R$`, Oficina e Manutenções Corretivas/Avulsas)**:
  - Campos de **Valor (`R$`)** e **Oficina/Local** ao dar baixa em manutenções.
  - Botão **+ Avulsa** na aba *Histórico* para lançar serviços corretivos imprevistos.
  - Painel de resumo financeiro no topo do *Histórico*, busca por texto, filtro **Todos vs Só Veículo Ativo** e botão de exclusão de registros.
- **Fase 3 (Alertas Híbridos por KM + Prazo em Meses)**:
  - Suporte a `intervalo_meses` nas preventivas, alertando pelo critério que vencer primeiro (quilometragem ou tempo).
- **Fase 4 (Abastecimento e Consumo Médio `km/L`)**:
  - Nova 4ª aba **Abastecer** + botão rápido de posto ao lado do campo de KM na *Home*.
  - Cálculo automático de **Média Geral (`km/L`)**, **Último Consumo (`km/L`)**, **Preço Médio por Litro** e sincronização automática do odômetro.
- **Fase 5 (Dossiê de Manutenção para Revenda)**:
  - Botão **Dossiê** na *Ficha Técnica* com resumo formatado para WhatsApp e gerador de relatório HTML/PDF pronto para impressão.

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
