-- Projeto 7 - IA Para Previsão de Demanda e Otimização do Estoque de Produtos Sazonais
-- SQL - Criação do Banco de Dados

-- Deleta o schema se já existir
DROP SCHEMA IF EXISTS projeto7 CASCADE;

-- Cria o schema
CREATE SCHEMA projeto7 AUTHORIZATION dsa;

-- Cria as tabelas

CREATE TABLE projeto7.fornecedores (
    id_fornecedor SERIAL PRIMARY KEY,
    nome_fornecedor VARCHAR(255) NOT NULL,
    nome_contato VARCHAR(255),
    email_contato VARCHAR(255)
);

CREATE TABLE projeto7.categorias (
    id_categoria SERIAL PRIMARY KEY,
    nome_categoria VARCHAR(255) NOT NULL
);

CREATE TABLE projeto7.produtos (
    id_produto SERIAL PRIMARY KEY,
    nome_produto VARCHAR(255) NOT NULL,
    id_categoria INT,
    id_fornecedor INT,
    preco_unitario DECIMAL(10, 2),
    CONSTRAINT fk_categoria
        FOREIGN KEY(id_categoria) 
        REFERENCES projeto7.categorias(id_categoria),
    CONSTRAINT fk_fornecedor
        FOREIGN KEY(id_fornecedor) 
        REFERENCES projeto7.fornecedores(id_fornecedor)
);

CREATE TABLE projeto7.clientes (
    id_cliente SERIAL PRIMARY KEY,
    nome_cliente VARCHAR(255) NOT NULL,
    email VARCHAR(255)
);

CREATE TABLE projeto7.vendas (
    id_venda SERIAL PRIMARY KEY,
    id_produto INT NOT NULL,
    id_cliente INT,
    data_venda DATE NOT NULL,
    quantidade_vendida INT NOT NULL,
    total_venda DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_produto
        FOREIGN KEY(id_produto) 
        REFERENCES projeto7.produtos(id_produto),
    CONSTRAINT fk_cliente
        FOREIGN KEY(id_cliente) 
        REFERENCES projeto7.clientes(id_cliente)
);

CREATE TABLE projeto7.estoque (
    id_estoque SERIAL PRIMARY KEY,
    id_produto INT NOT NULL,
    quantidade_em_estoque INT NOT NULL,
    data_ultimo_reabastecimento DATE,
    CONSTRAINT fk_produto
        FOREIGN KEY(id_produto) 
        REFERENCES projeto7.produtos(id_produto)
);

CREATE TABLE projeto7.sazonalidade (
    id_sazonalidade SERIAL PRIMARY KEY,
    id_produto INT NOT NULL,
    nome_temporada VARCHAR(255) NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE NOT NULL,
    CONSTRAINT fk_produto
        FOREIGN KEY(id_produto) 
        REFERENCES projeto7.produtos(id_produto)
);

CREATE TABLE projeto7.forecast (
    id_forecast SERIAL PRIMARY KEY,
    id_produto INT NOT NULL,
    data_forecast DATE NOT NULL,
    quantidade_forecast INT NOT NULL,
    CONSTRAINT fk_produto
        FOREIGN KEY(id_produto) 
        REFERENCES projeto7.produtos(id_produto)
);

CREATE TABLE projeto7.reabastecimento (
    id_reabastecimento SERIAL PRIMARY KEY,
    id_produto INT NOT NULL,
    data_reabastecimento DATE NOT NULL,
    quantidade INT NOT NULL,
    CONSTRAINT fk_produto
        FOREIGN KEY(id_produto) 
        REFERENCES projeto7.produtos(id_produto)
);

CREATE TABLE projeto7.pedidos (
    id_pedido SERIAL PRIMARY KEY,
    id_fornecedor INT NOT NULL,
    data_pedido DATE NOT NULL,
    id_produto INT NOT NULL,
    quantidade INT NOT NULL,
    CONSTRAINT fk_fornecedor
        FOREIGN KEY(id_fornecedor) 
        REFERENCES projeto7.fornecedores(id_fornecedor),
    CONSTRAINT fk_produto
        FOREIGN KEY(id_produto) 
        REFERENCES projeto7.produtos(id_produto)
);



