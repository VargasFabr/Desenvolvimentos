#!/usr/bin/env python3
"""
Script para gerar nuvem de palavras a partir de um arquivo Excel.
O arquivo Excel deve conter apenas uma coluna com cabeçalho.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from wordcloud import WordCloud
import matplotlib.pyplot as plt


def select_excel_file():
    """Abre um diálogo para selecionar o arquivo Excel."""
    root = tk.Tk()
    root.withdraw()  # Esconde a janela principal
    
    file_path = filedialog.askopenfilename(
        title="Selecione o arquivo Excel",
        filetypes=[
            ("Arquivos Excel", "*.xlsx *.xls"),
            ("Todos os arquivos", "*.*")
        ]
    )
    
    root.destroy()
    return file_path


def read_excel_column(file_path):
    """Lê o arquivo Excel e retorna o texto da primeira coluna."""
    try:
        df = pd.read_excel(file_path)
        
        if df.empty:
            raise ValueError("O arquivo Excel está vazio.")
        
        # Pega a primeira coluna
        first_column = df.iloc[:, 0]
        
        # Converte todos os valores para string e junta com espaços
        text = ' '.join(first_column.dropna().astype(str).tolist())
        
        if not text.strip():
            raise ValueError("A coluna não contém dados válidos.")
        
        return text, df.columns[0]
        
    except Exception as e:
        raise Exception(f"Erro ao ler o arquivo: {str(e)}")


def generate_word_cloud(text, column_name):
    """Gera e exibe a nuvem de palavras."""
    # Configurações da nuvem de palavras
    wordcloud = WordCloud(
        width=1200,
        height=800,
        background_color='white',
        colormap='viridis',
        max_words=200,
        min_font_size=10,
        max_font_size=150,
        random_state=42,
        collocations=False  # Evita repetição de pares de palavras
    ).generate(text)
    
    # Cria a figura
    plt.figure(figsize=(14, 10))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title(f'Nuvem de Palavras - {column_name}', fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout(pad=2)
    
    # Exibe o gráfico
    plt.show()


def main():
    """Função principal do script."""
    print("=" * 50)
    print("  Gerador de Nuvem de Palavras a partir de Excel")
    print("=" * 50)
    print("\nSelecione um arquivo Excel na janela que será aberta...")
    
    # Seleciona o arquivo
    file_path = select_excel_file()
    
    if not file_path:
        print("\nNenhum arquivo selecionado. Encerrando.")
        return
    
    print(f"\nArquivo selecionado: {file_path}")
    print("Processando...")
    
    try:
        # Lê os dados do Excel
        text, column_name = read_excel_column(file_path)
        print(f"Coluna encontrada: '{column_name}'")
        
        # Conta palavras
        word_count = len(text.split())
        print(f"Total de palavras encontradas: {word_count}")
        
        # Gera a nuvem de palavras
        print("\nGerando nuvem de palavras...")
        generate_word_cloud(text, column_name)
        
        print("\nConcluído com sucesso!")
        
    except Exception as e:
        print(f"\nErro: {str(e)}")
        
        # Mostra mensagem de erro em uma janela
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Erro", str(e))
        root.destroy()


if __name__ == "__main__":
    main()
