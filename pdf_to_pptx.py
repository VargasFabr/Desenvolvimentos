import os
import fitz  # PyMuPDF
from pptx import Presentation
from pptx.util import Inches
import tkinter as tk
from tkinter import filedialog, messagebox

def pdf_to_pptx():
    # Oculta a janela principal do Tkinter
    root = tk.Tk()
    root.withdraw()

    # Abre a caixa de diálogo para selecionar o arquivo PDF
    pdf_path = filedialog.askopenfilename(
        title="Selecione o arquivo PDF para converter",
        filetypes=[("Arquivos PDF", "*.pdf")]
    )

    if not pdf_path:
        print("Operação cancelada. Nenhum arquivo foi selecionado.")
        return

    print(f"Arquivo selecionado: {pdf_path}")

    # Define o caminho de saída (mesma pasta, mesmo nome, extensão .pptx)
    dir_name = os.path.dirname(pdf_path)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    pptx_path = os.path.join(dir_name, f"{base_name}.pptx")

    # Inicializa a apresentação do PowerPoint
    prs = Presentation()
    # Layout 6 costuma ser o slide em branco (Blank)
    blank_slide_layout = prs.slide_layouts[6]

    try:
        # Abre o documento PDF usando PyMuPDF
        pdf_document = fitz.open(pdf_path)
        
        # Ajusta o tamanho do slide da apresentação baseando-se na primeira página do PDF
        if len(pdf_document) > 0:
            first_page = pdf_document[0]
            rect = first_page.rect
            # Convertendo de pontos (72 pontos por polegada) para polegadas
            width_inches = rect.width / 72.0
            height_inches = rect.height / 72.0
            
            # Limites aceitos pelo python-pptx
            MAX_INCHES = 56.0
            MIN_INCHES = 1.0
            
            # Ajusta para caber nos limites, preservando a proporção sempre que possível
            if width_inches > MAX_INCHES or height_inches > MAX_INCHES or \
               width_inches < MIN_INCHES or height_inches < MIN_INCHES:
               
                scale_w = 1.0
                scale_h = 1.0
                
                if width_inches > MAX_INCHES: scale_w = MAX_INCHES / width_inches
                elif width_inches < MIN_INCHES: scale_w = MIN_INCHES / width_inches
                
                if height_inches > MAX_INCHES: scale_h = MAX_INCHES / height_inches
                elif height_inches < MIN_INCHES: scale_h = MIN_INCHES / height_inches
                
                # Escolhe a escala para caber dentro dos limites
                if scale_w < 1.0 or scale_h < 1.0:
                    scale = min(scale_w, scale_h) # Reduz pelo que estourou mais
                else:
                    scale = max(scale_w, scale_h) # Amplia pelo que estourou mais
                    
                width_inches *= scale
                height_inches *= scale
                
                # Garante os limites absolutos (quebra proporção apenas se a imagem for extremamente desproporcional)
                width_inches = max(MIN_INCHES, min(MAX_INCHES, width_inches))
                height_inches = max(MIN_INCHES, min(MAX_INCHES, height_inches))

            prs.slide_width = Inches(width_inches)
            prs.slide_height = Inches(height_inches)

        print(f"Iniciando a conversão de {len(pdf_document)} página(s)...")
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Aumenta a resolução da imagem renderizada para melhor qualidade
            zoom = 2.0 
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Salva temporariamente a imagem da página
            temp_img = f"temp_page_{page_num}.png"
            pix.save(temp_img)
            
            # Adiciona um slide em branco
            slide = prs.slides.add_slide(blank_slide_layout)
            
            # Adiciona a imagem cobrindo todo o slide
            slide.shapes.add_picture(
                temp_img, 
                0, 0, 
                width=prs.slide_width, 
                height=prs.slide_height
            )
            
            # Remove a imagem temporária
            if os.path.exists(temp_img):
                os.remove(temp_img)
                
            print(f"Página {page_num + 1}/{len(pdf_document)} processada.")

        # Salva o arquivo PPTX
        prs.save(pptx_path)
        print("\nConversão concluída com sucesso!")
        print(f"Arquivo PPTX salvo em: {pptx_path}")
        
        # Exibe mensagem de sucesso
        messagebox.showinfo("Sucesso", f"Conversão concluída!\n\nSalvo em:\n{pptx_path}")

    except Exception as e:
        print(f"Ocorreu um erro durante a conversão: {e}")
        messagebox.showerror("Erro", f"Ocorreu um erro durante a conversão:\n{e}")
    finally:
        if 'pdf_document' in locals() and hasattr(pdf_document, 'close'):
            pdf_document.close()

if __name__ == "__main__":
    pdf_to_pptx()
