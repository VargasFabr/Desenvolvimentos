# 🚀 Guia de Início Rápido

## O Problema

Você está vendo este erro:
```
ERRO: Diretório não encontrado: /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice
Volume ProjetosVS não montado
```

**Causa:** Você está tentando usar caminhos do Windows (`E:/Projetos/...`) em um sistema Linux.

## A Solução em 3 Passos

### Passo 1: Execute o Setup

```bash
cd /workspace
./setup.sh
```

Este script irá:
- ✓ Criar todos os diretórios necessários
- ✓ Buscar automaticamente seus projetos
- ✓ Configurar os volumes corretamente
- ✓ Iniciar o Airflow

### Passo 2: Copie Seus Arquivos

Se o script não encontrou seus arquivos automaticamente:

```bash
# Opção A: Copiar de outro local
cp -r /caminho/para/Melnick-Code/* ./ProjetosVS/Melnick-Code/

# Opção B: Criar link simbólico (recomendado)
ln -s /caminho/real/Melnick-Code ./ProjetosVS/Melnick-Code

# Opção C: Se estiver no WSL
cp -r /mnt/e/Projetos/VS_Code/Melnick-Code/* ./ProjetosVS/Melnick-Code/
```

### Passo 3: Verifique e Acesse

```bash
# Verificar se está tudo OK
./verify.sh

# Acessar o Airflow
# URL: http://localhost:8081
# Usuário: admin
# Senha: admin
```

## 🔍 Diagnóstico Rápido

### Verificar se arquivos existem

```bash
# No host (seu computador)
ls -la ./ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/

# Dentro do container
docker exec airflow3-standalone ls -la /opt/airflow/ProjetosVS/Melnick-Code/Projetos/AutoBackoffice/
```

### Executar DAG de teste

1. Acesse http://localhost:8081
2. Login: `admin` / `admin`
3. Execute a DAG **test_volumes**
4. Veja os logs para confirmar que os volumes estão montados

## 🆘 Problemas Comuns

### "Container não inicia"

```bash
# Ver o que está acontecendo
docker-compose logs -f

# Reiniciar do zero
docker-compose down
docker-compose up -d
```

### "Arquivo não encontrado"

```bash
# Verificar estrutura
tree -L 5 ProjetosVS/

# Ou sem tree
find ProjetosVS -type f -name "*.py"
```

### "Permission denied"

```bash
# Ajustar permissões
sudo chmod -R 755 ./ProjetosVS ./dags ./logs ./plugins
sudo chown -R $USER:$USER ./ProjetosVS ./dags ./logs ./plugins
```

## 📋 Checklist

- [ ] Executei `./setup.sh`
- [ ] Copiei/linkei meus arquivos para `./ProjetosVS/`
- [ ] Executei `./verify.sh` e está tudo ✓
- [ ] Container está rodando (`docker-compose ps`)
- [ ] Consegui acessar http://localhost:8081
- [ ] DAG `test_volumes` passou sem erros
- [ ] DAG `Atualiza_BackOffice` está funcionando

## 💡 Dicas

1. **Use caminhos relativos** sempre que possível
2. **Teste com test_volumes** antes de executar suas DAGs
3. **Veja os logs** se algo der errado: `docker-compose logs -f`
4. **Entre no container** para debugar: `docker exec -it airflow3-standalone bash`

## 📞 Próximos Passos

Depois que tudo estiver funcionando:

1. Ajuste o schedule da DAG se necessário
2. Adicione suas próprias DAGs em `./dags/`
3. Instale dependências Python em `requirements.txt`
4. Configure alertas e notificações

## 📚 Documentação Completa

- [README.md](./README.md) - Documentação completa
- [SOLUCAO.md](./SOLUCAO.md) - Solução detalhada do problema
