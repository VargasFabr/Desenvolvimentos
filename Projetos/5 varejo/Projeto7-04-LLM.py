# Projeto 7 - IA Para Previsão de Demanda e Otimização do Estoque de Produtos Sazonais
# Python - Pipeline de Extração de Insights com LLM

# Imports
import csv
import psycopg2
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.llms.ollama import Ollama

# Instanciação do LLM Llama3 através do Ollama
llm = Ollama(model = "llama3")

# Criação do parser para a saída do modelo de linguagem
output_parser = StrOutputParser()

# Função para gerar texto baseado nos dados do PostgreSQL
def dsa_gera_insights():

    # Conecta ao banco de dados PostgreSQL com as credenciais fornecidas
    conn = psycopg2.connect(
        dbname="dsadb",
        user="dsa",
        password="dsa1010",
        host="localhost",
        port="5551"
    )

    # Cria um cursor para executar comandos SQL
    cursor = conn.cursor()
    
    # Define a consulta SQL para obter dados dos clientes, compras e produtos
    query = """
        SELECT
            p.id_produto AS id_produto,
            p.nome_produto AS nome_produto,
            c.nome_categoria AS nome_categoria,
            f.nome_fornecedor AS nome_fornecedor,
            COALESCE(SUM(v.quantidade_vendida), 0) AS total_vendido,
            COALESCE(e.quantidade_em_estoque, 0) AS quantidade_em_estoque,
            COALESCE(s.nome_temporada, 'Nenhuma') AS temporada,
            COALESCE(fore.quantidade_forecast, 0) AS quantidade_forecast,
            COALESCE(re.quantidade, 0) AS quantidade_reabastecida
        FROM
            projeto7.produtos p
        LEFT JOIN
            projeto7.categorias c ON p.id_categoria = c.id_categoria
        LEFT JOIN
            projeto7.fornecedores f ON p.id_fornecedor = f.id_fornecedor
        LEFT JOIN
            projeto7.vendas v ON p.id_produto = v.id_produto
        LEFT JOIN
            projeto7.estoque e ON p.id_produto = e.id_produto
        LEFT JOIN
            projeto7.sazonalidade s ON p.id_produto = s.id_produto
        LEFT JOIN
            projeto7.forecast fore ON p.id_produto = fore.id_produto
        LEFT JOIN
            projeto7.reabastecimento re ON p.id_produto = re.id_produto
        WHERE
            c.nome_categoria IN ('Eletrônicos', 'Roupas')
        GROUP BY
            p.id_produto, p.nome_produto, c.nome_categoria, f.nome_fornecedor,
            e.quantidade_em_estoque, e.data_ultimo_reabastecimento,
            s.nome_temporada, s.data_inicio, s.data_fim,
            fore.quantidade_forecast, re.quantidade, re.data_reabastecimento
        ORDER BY
            p.id_produto;
    """
    
    # Executa a consulta SQL
    cursor.execute(query)

    # Obtém todos os resultados da consulta
    rows = cursor.fetchall()
    
    # Inicializa uma lista para armazenar os insights
    insights = []

    # Criação do template de prompt para o chatbot 
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Você é um cientista de dados especializado. Analise os dados e forneça feedback em português do Brasil sobre previsão de demanda e otimização do estoque de produtos sazonais."),
            ("user", "question: {question}")
        ]
    )

    # Definição da cadeia de execução: prompt -> LLM -> output_parser
    chain = prompt | llm | output_parser

    # Itera sobre as linhas de resultados
    for row in rows:
        
        # Desempacota os valores de cada linha
        id_produto, nome_produto, nome_categoria, nome_fornecedor, total_vendido, quantidade_em_estoque, temporada, quantidade_forecast, quantidade_reabastecida = row
        
        # Cria o prompt para o LLM com base nos dados do cliente
        consulta = f"ID_Produto {id_produto} Nome_Produto {nome_produto} Nome_Categoria {nome_categoria} Nome_Fornecedor {nome_fornecedor} Total_Vendido ${total_vendido:.2f} quantidade_em_estoque {quantidade_em_estoque:.2f} temporada {temporada} quantidade_forecast {quantidade_forecast} quantidade_reabastecida {quantidade_reabastecida}."
        
        # Gera o texto de insight usando o LLM
        response = chain.invoke({'question': consulta})
        
        # Adiciona o texto gerado à lista de insights
        insights.append(response)
    
    # Fecha a conexão com o banco de dados
    conn.close()

    # Salva os insights em um arquivo CSV
    with open('projeto7-analise.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Insight"])
        for insight in insights:
            writer.writerow([insight])

    # Retorna a lista de insights
    return insights

# Gera insights chamando a função definida
insights = dsa_gera_insights()

# Imprime cada insight gerado
for insight in insights:
    print(insight)
