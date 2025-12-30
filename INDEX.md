# 📚 Índice de Documentação - Airflow 3

## 🚀 Por Onde Começar?

### 1️⃣ Primeira Vez? Comece Aqui!

- **[INICIO_RAPIDO.md](./INICIO_RAPIDO.md)** ⭐
  - Guia de 3 passos para resolver o problema
  - Solução rápida e direta
  - **Comece por aqui se você tem pressa!**

### 2️⃣ Quer Entender o Problema?

- **[SOLUCAO.md](./SOLUCAO.md)**
  - Explicação detalhada do problema
  - Por que aconteceu
  - Como foi resolvido
  - Opções de configuração

### 3️⃣ Configurar Seu Ambiente

- **[AMBIENTE.md](./AMBIENTE.md)**
  - Guia específico por sistema operacional
  - Linux, Windows, WSL, macOS
  - Como identificar seu ambiente
  - Exemplos de configuração

---

## 🛠️ Ferramentas e Scripts

### Scripts de Configuração

| Script | Descrição | Quando Usar |
|--------|-----------|-------------|
| **[setup.sh](./setup.sh)** | Configuração automática completa | Primeira instalação |
| **[verify.sh](./verify.sh)** | Verifica se tudo está correto | Diagnóstico rápido |
| **[migrate.sh](./migrate.sh)** | Migra de Windows para Linux | Mudando de ambiente |

### Como Usar

```bash
# Configuração inicial
./setup.sh

# Verificar se está tudo OK
./verify.sh

# Migrar ambiente antigo
./migrate.sh
```

---

## 📖 Documentação Completa

### [README.md](./README.md) - Documentação Principal

- Visão geral do projeto
- Estrutura completa
- Configurações
- DAGs disponíveis
- Troubleshooting

### [COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md) - Referência Rápida

- Comandos Docker Compose
- Diagnóstico e debug
- Gerenciamento de DAGs
- Permissões e segurança
- Backup e restore
- Troubleshooting

---

## 📂 Arquivos de Configuração

### Arquivos Principais

| Arquivo | Descrição |
|---------|-----------|
| `docker-compose.yml` | Configuração principal do Docker (LINUX) ✓ |
| `docker-compose.windows.yml.example` | Exemplo para outros ambientes |
| `requirements.txt` | Dependências Python |
| `.gitignore` | Arquivos ignorados pelo Git |

### Diretórios

| Diretório | Conteúdo |
|-----------|----------|
| `dags/` | DAGs do Airflow (seus workflows) |
| `logs/` | Logs de execução |
| `plugins/` | Plugins personalizados |
| `ProjetosVS/` | Seus projetos (volume montado) |

---

## 🎯 Guias por Objetivo

### "Quero Resolver o Problema Agora!"
1. **[INICIO_RAPIDO.md](./INICIO_RAPIDO.md)** - 3 passos para solução
2. Execute `./setup.sh`
3. Pronto!

### "Quero Entender o Que Aconteceu"
1. **[SOLUCAO.md](./SOLUCAO.md)** - Explicação completa
2. **[AMBIENTE.md](./AMBIENTE.md)** - Configuração por OS

### "Estou Migrando de Windows"
1. **[migrate.sh](./migrate.sh)** - Script de migração
2. **[AMBIENTE.md](./AMBIENTE.md)** - Seção WSL

### "Quero Aprender a Usar"
1. **[README.md](./README.md)** - Documentação completa
2. **[COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md)** - Referência
3. Execute DAG `test_volumes` para testar

### "Estou com Problemas"
1. Execute `./verify.sh` para diagnóstico
2. **[COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md)** - Seção Troubleshooting
3. **[README.md](./README.md)** - Seção Troubleshooting

---

## 🔍 Guias por Sistema Operacional

### 🐧 Linux (Seu Sistema Atual)
- ✅ Já configurado em `docker-compose.yml`
- Leia: [AMBIENTE.md - Seção Linux](./AMBIENTE.md#-linux-atual---recomendado)
- Execute: `./setup.sh`

### 🪟 Windows com Docker Desktop
- Leia: [AMBIENTE.md - Seção Windows](./AMBIENTE.md#-windows-com-docker-desktop)
- Veja: `docker-compose.windows.yml.example`

### 🔧 WSL (Windows Subsystem for Linux)
- Leia: [AMBIENTE.md - Seção WSL](./AMBIENTE.md#-wsl-windows-subsystem-for-linux)
- Use: `./migrate.sh`

### 🍎 macOS
- Leia: [AMBIENTE.md - Seção macOS](./AMBIENTE.md#-macos)
- Similar ao Linux

---

## 📋 DAGs Disponíveis

### [AtualizaBackOffice.py](./dags/AtualizaBackOffice.py)
- **Função:** Executa script de atualização do BackOffice
- **Schedule:** 5 minutos após cada hora, das 8h às 18h, seg-sáb
- **Status:** Produção

### [test_volumes.py](./dags/test_volumes.py)
- **Função:** Diagnostica montagem de volumes
- **Schedule:** Manual
- **Status:** Diagnóstico
- **Use:** Execute esta primeiro para verificar se está tudo OK!

---

## 🆘 Troubleshooting Rápido

| Problema | Solução | Documento |
|----------|---------|-----------|
| Volume não montado | `./verify.sh` e `./setup.sh` | [INICIO_RAPIDO.md](./INICIO_RAPIDO.md) |
| Container não inicia | `docker-compose logs -f` | [COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md) |
| DAG não aparece | Verificar sintaxe Python | [README.md](./README.md) |
| Permissão negada | `chmod -R 755 ./ProjetosVS` | [COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md) |
| Porta em uso | `sudo lsof -i :8081` | [COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md) |

---

## ⚡ Comandos Mais Usados

```bash
# Configuração inicial
./setup.sh

# Verificar ambiente
./verify.sh

# Iniciar Airflow
docker-compose up -d

# Ver logs
docker-compose logs -f

# Entrar no container
docker exec -it airflow3-standalone bash

# Parar Airflow
docker-compose down

# Verificar volumes
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/
```

---

## 📞 Acesso Rápido

- **URL:** http://localhost:8081
- **Usuário:** admin
- **Senha:** admin

---

## 🎓 Fluxo de Aprendizado Recomendado

### Nível Iniciante
1. ✅ **[INICIO_RAPIDO.md](./INICIO_RAPIDO.md)** - Comece aqui
2. Execute `./setup.sh`
3. Acesse http://localhost:8081
4. Execute DAG `test_volumes`

### Nível Intermediário
1. ✅ **[README.md](./README.md)** - Documentação completa
2. ✅ **[AMBIENTE.md](./AMBIENTE.md)** - Entenda configurações
3. Execute `./verify.sh` regularmente
4. Crie suas próprias DAGs

### Nível Avançado
1. ✅ **[COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md)** - Referência completa
2. ✅ **[SOLUCAO.md](./SOLUCAO.md)** - Entenda internamente
3. Customize `docker-compose.yml`
4. Configure banco de dados PostgreSQL
5. Adicione autenticação LDAP/OAuth

---

## 🔗 Links Úteis

### Documentação Oficial
- [Apache Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/)
- [Docker Compose](https://docs.docker.com/compose/)
- [Docker Volumes](https://docs.docker.com/storage/volumes/)

### Dentro deste Repositório
- [README principal](./README.md)
- [Guia rápido](./INICIO_RAPIDO.md)
- [Solução detalhada](./SOLUCAO.md)
- [Configuração por ambiente](./AMBIENTE.md)
- [Comandos úteis](./COMANDOS_UTEIS.md)

---

## 📝 Estrutura do Projeto

```
/workspace/
├── 📘 INDEX.md (você está aqui)
│
├── 🚀 Guias de Início
│   ├── INICIO_RAPIDO.md       ⭐ Comece aqui!
│   ├── SOLUCAO.md            📖 Explicação detalhada
│   └── AMBIENTE.md           🖥️ Por sistema operacional
│
├── 📚 Documentação
│   ├── README.md              📖 Documentação completa
│   └── COMANDOS_UTEIS.md     🔧 Referência de comandos
│
├── 🛠️ Scripts
│   ├── setup.sh               ⚙️ Configuração automática
│   ├── verify.sh             ✅ Verificação
│   └── migrate.sh            🔄 Migração
│
├── ⚙️ Configuração
│   ├── docker-compose.yml                    (LINUX - atual)
│   ├── docker-compose.windows.yml.example    (exemplo)
│   ├── requirements.txt                      (dependências)
│   └── .gitignore
│
└── 📂 Diretórios de Trabalho
    ├── dags/                  (DAGs do Airflow)
    ├── logs/                  (Logs de execução)
    ├── plugins/               (Plugins)
    └── ProjetosVS/           (Seus projetos)
```

---

## ✅ Checklist de Início

- [ ] Li [INICIO_RAPIDO.md](./INICIO_RAPIDO.md)
- [ ] Executei `./setup.sh`
- [ ] Executei `./verify.sh` (tudo OK)
- [ ] Acessei http://localhost:8081
- [ ] Executei DAG `test_volumes` (passou)
- [ ] Executei DAG `Atualiza_BackOffice` (funcionou)
- [ ] Li [README.md](./README.md) completo
- [ ] Salvei bookmark de [COMANDOS_UTEIS.md](./COMANDOS_UTEIS.md)

---

## 🎉 Parabéns!

Se você chegou até aqui e completou o checklist, seu ambiente Airflow está **100% configurado e funcionando**!

### Próximos Passos:
1. ⭐ Marque este repositório
2. 📚 Explore os outros documentos conforme necessário
3. 🚀 Crie suas próprias DAGs
4. 💡 Compartilhe com sua equipe

---

**Dúvidas?** Consulte os documentos linkados acima ou execute `./verify.sh` para diagnóstico.

**Tudo funcionando?** Ótimo! Agora você pode focar em criar suas automações! 🎯
