Sub ExemploTextoLongo()
    
    Dim obs As String
    
    ' Método 1: Concatenando com vbCrLf para quebras de linha
    obs = "A Construtora se reserva o direito de usar materiais similares, em função da disponibilidade dos materiais no mercado no momento da aquisição, das oportunidades de comercialização deles ou da melhor adequação ao projeto." & vbCrLf & vbCrLf & _
          "Os padrões de cores dos acabamentos poderão ser alterados de forma a obter-se uma harmonia e bom gosto na caracterização final dos elementos do condomínio." & vbCrLf & vbCrLf & _
          "A Construtora poderá fazer pequenos ajustes no projeto arquitetônico aprovado, uma vez que os projetos complementares ainda não foram finalizados. Estes ajustes serão feitos de forma a resolver problemas técnicos que possam surgir. Tais alterações poderão modificar as áreas totais reais e privativas das unidades, numa variação de até 5% para mais ou menos." & vbCrLf & vbCrLf & _
          "A Construtora não entrega as unidades com chuveiros, acessórios de banheiro (cabideiro, porta papel, assento para bacia sanitária e outros) e carpetes."
    
    ' Exibir o texto (pode truncar em MsgBox devido ao limite de caracteres)
    MsgBox obs
    
    ' Ou colocar em uma célula
    Range("A1").Value = obs
    
End Sub

' ============================================================
' Método 2: Construindo linha por linha (mais legível)
' ============================================================
Sub ExemploTextoLongo2()
    
    Dim obs As String
    
    obs = ""
    obs = obs & "A Construtora se reserva o direito de usar materiais similares, "
    obs = obs & "em função da disponibilidade dos materiais no mercado no momento da aquisição, "
    obs = obs & "das oportunidades de comercialização deles ou da melhor adequação ao projeto."
    obs = obs & vbCrLf & vbCrLf
    
    obs = obs & "Os padrões de cores dos acabamentos poderão ser alterados de forma a obter-se "
    obs = obs & "uma harmonia e bom gosto na caracterização final dos elementos do condomínio."
    obs = obs & vbCrLf & vbCrLf
    
    obs = obs & "A Construtora poderá fazer pequenos ajustes no projeto arquitetônico aprovado, "
    obs = obs & "uma vez que os projetos complementares ainda não foram finalizados. "
    obs = obs & "Estes ajustes serão feitos de forma a resolver problemas técnicos que possam surgir. "
    obs = obs & "Tais alterações poderão modificar as áreas totais reais e privativas das unidades, "
    obs = obs & "numa variação de até 5% para mais ou menos."
    obs = obs & vbCrLf & vbCrLf
    
    obs = obs & "A Construtora não entrega as unidades com chuveiros, acessórios de banheiro "
    obs = obs & "(cabideiro, porta papel, assento para bacia sanitária e outros) e carpetes."
    
    Range("A1").Value = obs
    
End Sub

' ============================================================
' Dicas importantes:
' ============================================================
' 1. Use " _ " (espaço, underscore, espaço) para continuar uma linha longa
' 2. Use vbCrLf para quebra de linha no texto
' 3. Se precisar incluir aspas no texto, use aspas duplas: ""exemplo""
' 4. O limite de uma linha de código no VBA é ~1024 caracteres
' 5. O limite de uma string é ~2 bilhões de caracteres
