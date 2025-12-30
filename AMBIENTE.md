# 🖥️ Guia de Configuração por Ambiente

Este guia mostra como configurar os volumes do Docker corretamente em diferentes ambientes.

## 🐧 Linux (Atual - Recomendado)

### Configuração Atual

O arquivo `docker-compose.yml` já está configurado para Linux:

```yaml
volumes:
  - ./ProjetosVS:/opt/airflow/ProjetosVS
```

### Onde colocar seus arquivos

```bash
# No mesmo diretório do docker-compose.yml
/workspace/
├── docker-compose.yml
└── ProjetosVS/
    └── Melnick-Code/
        └── Projetos/
            └── AutoBackoffice/
                └── AutoBackoffice.py
```

### Como configurar

```bash
# Opção A: Copiar arquivos
cp -r /caminho/original/Melnick-Code/* ./ProjetosVS/Melnick-Code/

# Opção B: Link simbólico (recomendado)
ln -s /caminho/original/Melnick-Code ./ProjetosVS/Melnick-Code

# Opção C: Caminho absoluto no docker-compose.yml
# Edite docker-compose.yml:
# - /home/usuario/Projetos:/opt/airflow/ProjetosVS
```

---

## 🪟 Windows com Docker Desktop

### Configuração

No Windows, use caminhos completos com `/` (não `\`):

```yaml
volumes:
  - C:/Users/SeuNome/Projetos/VS_Code:/opt/airflow/ProjetosVS
```

### Estrutura

```
C:\Users\SeuNome\Projetos\VS_Code\
└── Melnick-Code\
    └── Projetos\
        └── AutoBackoffice\
            └── AutoBackoffice.py
```

### Exemplo docker-compose.yml

```yaml
volumes:
  - ./dags:/opt/airflow/dags
  - ./logs:/opt/airflow/logs
  - C:/Users/SeuNome/Projetos/VS_Code:/opt/airflow/ProjetosVS
```

### ⚠️ Importante

1. Use `/` não `\` nas barras
2. ❌ Errado: `E:\Projetos\VS_Code`
3. ✅ Certo: `E:/Projetos/VS_Code`
4. Certifique-se que o Docker Desktop tem acesso ao drive (Configurações > Resources > File Sharing)

---

## 🔧 WSL (Windows Subsystem for Linux)

### Configuração

No WSL, os drives do Windows são montados em `/mnt/`:

- `E:` → `/mnt/e`
- `C:` → `/mnt/c`
- `D:` → `/mnt/d`

```yaml
volumes:
  - /mnt/e/Projetos/VS_Code:/opt/airflow/ProjetosVS
```

### Como verificar

```bash
# Ver seus drives
ls /mnt/

# Navegar para seu projeto
cd /mnt/e/Projetos/VS_Code/Melnick-Code

# Verificar estrutura
ls -la
```

### Exemplo docker-compose.yml

```yaml
volumes:
  - ./dags:/opt/airflow/dags
  - ./logs:/opt/airflow/logs
  - /mnt/e/Projetos/VS_Code:/opt/airflow/ProjetosVS
```

### 💡 Dica para WSL

Se você está usando WSL, é melhor copiar os arquivos para dentro do WSL:

```bash
# Copiar para sistema de arquivos do WSL (mais rápido)
cp -r /mnt/e/Projetos/VS_Code/Melnick-Code ~/projetos/

# Usar caminho WSL no docker-compose
# - /home/usuario/projetos/Melnick-Code:/opt/airflow/Melnick-Code
```

**Por quê?** Acessar arquivos do Windows pelo WSL é mais lento. Copiar para o sistema de arquivos do WSL melhora a performance.

---

## 🍎 macOS

### Configuração

Similar ao Linux:

```yaml
volumes:
  - ./ProjetosVS:/opt/airflow/ProjetosVS
  # OU
  - /Users/usuario/Projetos:/opt/airflow/ProjetosVS
```

### Estrutura

```
/Users/SeuNome/Projetos/
└── Melnick-Code/
    └── Projetos/
        └── AutoBackoffice/
            └── AutoBackoffice.py
```

### Permissões

```bash
# Dar permissões
chmod -R 755 ~/Projetos/Melnick-Code

# Verificar
ls -la ~/Projetos/
```

---

## 🔍 Como Identificar Seu Ambiente

### Você está no Linux se:

```bash
uname -a
# Linux hostname 5.x.x-xxx-generic #xxx-Ubuntu
```

### Você está no WSL se:

```bash
uname -a
# Linux hostname 5.x.x-xxxxx-Microsoft #xxx-Microsoft
```

```bash
# Ou veja se tem /mnt/c
ls /mnt/
# c  e  d
```

### Você está no Windows se:

- Você está usando PowerShell ou CMD
- Caminhos usam `C:\` ou `E:\`

### Você está no macOS se:

```bash
uname -a
# Darwin MacBook-Pro 21.x.x Darwin Kernel
```

---

## ⚙️ Configuração Recomendada por Ambiente

### Linux / macOS

```yaml
# Opção 1: Relativo (portável)
volumes:
  - ./ProjetosVS:/opt/airflow/ProjetosVS

# Opção 2: Absoluto
volumes:
  - /home/usuario/Projetos:/opt/airflow/ProjetosVS
```

### Windows com Docker Desktop

```yaml
volumes:
  - C:/Users/SeuNome/Projetos:/opt/airflow/ProjetosVS
```

### WSL

```yaml
# Opção 1: Acessar arquivos Windows (mais lento)
volumes:
  - /mnt/e/Projetos/VS_Code:/opt/airflow/ProjetosVS

# Opção 2: Arquivos no WSL (mais rápido)
volumes:
  - /home/usuario/projetos:/opt/airflow/ProjetosVS
```

---

## 🧪 Testar Configuração

### 1. Verificar volumes no host

```bash
# Linux/macOS/WSL
ls -la ./ProjetosVS/Melnick-Code/

# Windows PowerShell
dir C:\Users\SeuNome\Projetos\Melnick-Code
```

### 2. Iniciar container

```bash
docker-compose up -d
```

### 3. Verificar dentro do container

```bash
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/
```

### 4. Executar DAG de teste

1. Acesse http://localhost:8081
2. Execute `test_volumes`
3. Veja os logs

---

## 🐛 Problemas Comuns

### Erro: "Volume not found" no Windows

**Causa:** Docker Desktop não tem permissão para acessar o drive.

**Solução:**
1. Docker Desktop → Settings → Resources → File Sharing
2. Adicione o drive (ex: `E:\`)
3. Apply & Restart

### Erro: "Permission denied" no Linux/macOS

**Solução:**
```bash
chmod -R 755 ./ProjetosVS
chown -R $USER:$USER ./ProjetosVS
```

### Erro: Caminho não encontrado no WSL

**Verifique:**
```bash
# Ver seus drives
ls /mnt/

# Navegar
cd /mnt/e/Projetos
ls -la
```

### Performance ruim no WSL

**Solução:** Copie os arquivos para o sistema de arquivos WSL:
```bash
cp -r /mnt/e/Projetos ~/projetos
# Depois use ~/projetos no docker-compose.yml
```

---

## 📝 Resumo

| Ambiente | Caminho de Exemplo | Notas |
|----------|-------------------|-------|
| **Linux** | `./ProjetosVS` ou `/home/user/...` | Caminho relativo preferível |
| **macOS** | `./ProjetosVS` ou `/Users/user/...` | Similar ao Linux |
| **Windows** | `C:/Users/Nome/Projetos` | Use `/` não `\` |
| **WSL** | `/mnt/e/Projetos` | Melhor copiar para WSL |

---

## ✅ Checklist de Configuração

- [ ] Identifiquei meu ambiente (Linux/Windows/WSL/macOS)
- [ ] Ajustei o `docker-compose.yml` com o caminho correto
- [ ] Verifiquei que os arquivos existem no caminho configurado
- [ ] Dei as permissões necessárias (Linux/macOS)
- [ ] Testei com `./verify.sh`
- [ ] Container iniciou sem erros
- [ ] DAG `test_volumes` passou
- [ ] Consegui acessar meus arquivos no container

---

## 🆘 Ainda com problemas?

Execute o diagnóstico completo:

```bash
# Verificar ambiente
./verify.sh

# Ver logs detalhados
docker-compose logs -f

# Entrar no container
docker exec -it airflow3-standalone bash

# Verificar volumes dentro do container
ls -la /opt/airflow/
find /opt/airflow -name "AutoBackoffice.py"
```
