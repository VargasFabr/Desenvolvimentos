Option Explicit

Sub ProcessarPlanilhaDinamica()

    Dim wsCtrl As Worksheet
    Dim ultimaLinha As Long
    Dim ultimaColuna As Long
    Dim i As Long
    Dim j As Long

    Dim listaPlanilhas As Collection
    Dim dictResultados As Object
    Dim colDestino As Variant
    Dim chave As Variant

    Call limpar

    If check() = True Then Exit Sub

    Set wsCtrl = ThisWorkbook.Worksheets("Controle")
    ultimaLinha = wsCtrl.Cells(wsCtrl.Rows.Count, "B").End(xlUp).Row

    For i = 6 To ultimaLinha
        If wsCtrl.Cells(i, 3).Value = True And Len(Trim$(CStr(wsCtrl.Cells(i, 2).Value))) >= 5 Then

            Set listaPlanilhas = New Collection
            ultimaColuna = wsCtrl.Cells(5, wsCtrl.Columns.Count).End(xlToLeft).Column

            For j = 6 To ultimaColuna
                If Len(Trim$(CStr(wsCtrl.Cells(5, j).Value))) > 0 Then
                    listaPlanilhas.Add CStr(wsCtrl.Cells(5, j).Value)
                End If
            Next j

            Set dictResultados = ProcessarSelecaoPlanilhas( _
                listaPlanilhas, _
                CStr(wsCtrl.Cells(i, 4).Value), _
                CStr(wsCtrl.Cells(i, 5).Value))

            If dictResultados Is Nothing Then
                MsgBox "Processo cancelado pelo usuário.", vbExclamation
                Exit Sub
            End If

            For Each chave In dictResultados.Keys
                colDestino = Application.Match(chave, wsCtrl.Rows(5), 0)
                If Not IsError(colDestino) Then
                    wsCtrl.Cells(i, CLng(colDestino)).Value = dictResultados(chave)
                End If
            Next chave
        End If
    Next i

    MsgBox "Processamento concluído.", vbInformation
End Sub

Function ProcessarSelecaoPlanilhas(lista As Collection, _
                                   ByVal area As String, _
                                   ByVal nomeItem As String) As Object

    Dim frm As frmSelecaoPlanilhas
    Dim chk As MSForms.CheckBox
    Dim topo As Long
    Dim nomeItens As Variant
    Dim dict As Object
    Dim p As Variant

    Set frm = New frmSelecaoPlanilhas
    frm.fraChecks.Controls.Clear

    frm.TextoContexto = area & " | " & nomeItem
    frm.AtualizarContexto

    topo = 10

    For Each nomeItens In lista
        Set chk = frm.fraChecks.Controls.Add("Forms.CheckBox.1")
        chk.Caption = CStr(nomeItens)
        chk.Left = 10
        chk.Top = topo
        topo = topo + 20
    Next nomeItens

    frm.ScrollHeight = topo + 20
    frm.Show vbModal

    If frm.Tag = "CANCELADO" Then
        Set ProcessarSelecaoPlanilhas = Nothing
        Unload frm
        Set frm = Nothing
        Exit Function
    End If

    Set dict = CreateObject("Scripting.Dictionary")

    ' Valida o contexto (Área > Item > Perfil) apenas uma vez por linha do Controle.
    ' Se não existir, não tenta processar Piso/Rodapé/Paredes para evitar mensagens repetidas.
    If Not ValidarContextoBusca(area, nomeItem, True) Then
        Set ProcessarSelecaoPlanilhas = dict
        Unload frm
        Set frm = Nothing
        Exit Function
    End If

    For Each p In frm.PlanilhasSelecionadas
        dict(p) = ProcessarDadosPlanilha(CStr(p), area, nomeItem)
    Next p

    Set ProcessarSelecaoPlanilhas = dict

    Unload frm
    Set frm = Nothing
End Function

Private Function ValidarContextoBusca(ByVal area As String, _
                                      ByVal nomeItem As String, _
                                      ByVal exibirMensagem As Boolean) As Boolean
    Dim ws As Worksheet
    Dim nomeAbaBusca As String
    Dim perfil As String
    Dim ultimaColuna As Long

    Dim rngArea As Range
    Dim rngItem As Range
    Dim rngPerfil As Range
    Dim faixaArea As Range
    Dim faixaItem As Range
    Dim linhaIniArea As Long
    Dim linhaFimArea As Long
    Dim linhaIniItem As Long
    Dim linhaFimItem As Long

    nomeAbaBusca = Trim$(CStr(Planilha7.Cells(11, 3).Value))
    perfil = Trim$(CStr(Planilha7.Cells(3, 3).Value))

    If Len(nomeAbaBusca) = 0 Then
        If exibirMensagem Then
            MsgBox "A célula C11 da Planilha7 está vazia (nome da aba de busca).", vbExclamation
        End If
        Exit Function
    End If

    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(nomeAbaBusca)
    On Error GoTo 0

    If ws Is Nothing Then
        If exibirMensagem Then
            MsgBox "A aba '" & nomeAbaBusca & "' não foi encontrada.", vbExclamation
        End If
        Exit Function
    End If

    ultimaColuna = ws.Cells(14, ws.Columns.Count).End(xlToLeft).Column
    If ultimaColuna < 1 Then Exit Function

    Set rngArea = EncontrarNoRange(ws.UsedRange, area, False)
    If rngArea Is Nothing Then
        If exibirMensagem Then
            MsgBox "Área não encontrada na aba '" & ws.Name & "': " & area, vbExclamation
        End If
        Exit Function
    End If

    linhaIniArea = rngArea.MergeArea.Row
    linhaFimArea = linhaIniArea + rngArea.MergeArea.Rows.Count - 1
    Set faixaArea = ws.Range(ws.Cells(linhaIniArea, 2), ws.Cells(linhaFimArea, 2))

    Set rngItem = EncontrarNoRange(faixaArea, nomeItem, False)
    If rngItem Is Nothing Then
        If exibirMensagem Then
            MsgBox "Item não encontrado dentro da área '" & area & "': " & nomeItem, vbExclamation
        End If
        Exit Function
    End If

    linhaIniItem = rngItem.MergeArea.Row
    linhaFimItem = linhaIniItem + rngItem.MergeArea.Rows.Count - 1
    Set faixaItem = ws.Range(ws.Cells(linhaIniItem, 3), ws.Cells(linhaFimItem, 3))

    Set rngPerfil = EncontrarNoRange(faixaItem, perfil, False)
    If rngPerfil Is Nothing Then
        If exibirMensagem Then
            MsgBox "Perfil não encontrado no item '" & nomeItem & "': " & perfil, vbExclamation
        End If
        Exit Function
    End If

    ValidarContextoBusca = True
End Function

Function ProcessarDadosPlanilha( _
    ByVal nomeItens As String, _
    ByVal area As String, _
    ByVal nomeItem As String _
) As String

    Dim ws As Worksheet
    Dim nomeAbaBusca As String
    Dim perfil As String

    Dim rngArea As Range
    Dim rngItem As Range
    Dim rngPerfil As Range
    Dim rngCabecalho As Range
    Dim faixaArea As Range
    Dim faixaItem As Range

    Dim linhaIniArea As Long
    Dim linhaFimArea As Long
    Dim linhaIniItem As Long
    Dim linhaFimItem As Long
    Dim linhaIniPerfil As Long
    Dim linhaFimPerfil As Long
    Dim colunaDestino As Long
    Dim ultimaColuna As Long
    Dim linha As Long

    Dim dictOpcoes As Object
    Dim valorCelula As String
    Dim item As Variant
    Dim resultado As String

    Dim frm As frmSelecaoItens
    Dim chk As MSForms.CheckBox
    Dim topo As Long

    nomeAbaBusca = Trim$(CStr(Planilha7.Cells(11, 3).Value))
    perfil = Trim$(CStr(Planilha7.Cells(3, 3).Value))

    If Len(nomeAbaBusca) = 0 Then
        MsgBox "A célula C11 da Planilha7 está vazia (nome da aba de busca).", vbExclamation
        Exit Function
    End If

    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(nomeAbaBusca)
    On Error GoTo 0

    If ws Is Nothing Then
        MsgBox "A aba '" & nomeAbaBusca & "' não foi encontrada.", vbExclamation
        Exit Function
    End If

    ultimaColuna = ws.Cells(14, ws.Columns.Count).End(xlToLeft).Column
    If ultimaColuna < 1 Then Exit Function

    ' 1) Encontra a área na aba definida em texto2.
    Set rngArea = EncontrarNoRange(ws.UsedRange, area, False)
    If rngArea Is Nothing Then
        MsgBox "Área não encontrada na aba '" & ws.Name & "': " & area, vbExclamation
        Exit Function
    End If

    linhaIniArea = rngArea.MergeArea.Row
    linhaFimArea = linhaIniArea + rngArea.MergeArea.Rows.Count - 1
    Set faixaArea = ws.Range(ws.Cells(linhaIniArea, 2), ws.Cells(linhaFimArea, 2))

    ' 2) Dentro da área, encontra o nome do item (Controle!E).
    Set rngItem = EncontrarNoRange(faixaArea, nomeItem, False)
    If rngItem Is Nothing Then
        MsgBox "Item não encontrado dentro da área '" & area & "': " & nomeItem, vbExclamation
        Exit Function
    End If

    linhaIniItem = rngItem.MergeArea.Row
    linhaFimItem = linhaIniItem + rngItem.MergeArea.Rows.Count - 1
    Set faixaItem = ws.Range(ws.Cells(linhaIniItem, 3), ws.Cells(linhaFimItem, 3))

    ' 3) Dentro do item, encontra o perfil (Executivo/Proprietário).
    Set rngPerfil = EncontrarNoRange(faixaItem, perfil, False)
    If rngPerfil Is Nothing Then
        MsgBox "Perfil não encontrado no item '" & nomeItem & "': " & perfil, vbExclamation
        Exit Function
    End If

    linhaIniPerfil = rngPerfil.MergeArea.Row
    linhaFimPerfil = linhaIniPerfil + rngPerfil.MergeArea.Rows.Count - 1

    ' 4) Resolve a coluna alvo (nomeItens: PISO, RODAPÉ, etc).
    Set rngCabecalho = EncontrarCabecalho(ws, nomeItens, 4, ultimaColuna)
    If rngCabecalho Is Nothing Then
        MsgBox "Coluna '" & nomeItens & "' não encontrada na aba '" & ws.Name & "'.", vbExclamation
        Exit Function
    End If

    colunaDestino = rngCabecalho.Column
    Set dictOpcoes = CreateObject("Scripting.Dictionary")

    For linha = linhaIniPerfil To linhaFimPerfil
        valorCelula = LimparTexto(ws.Cells(linha, colunaDestino).Value)
        If Len(valorCelula) > 0 Then
            If Not dictOpcoes.Exists(valorCelula) Then
                dictOpcoes.Add valorCelula, valorCelula
            End If
        End If
    Next linha

    Select Case dictOpcoes.Count
        Case 0
            ProcessarDadosPlanilha = ""

        Case 1
            ProcessarDadosPlanilha = CStr(dictOpcoes.Items()(0))

        Case Else
            Set frm = New frmSelecaoItens
            frm.fraItens.Controls.Clear

            frm.TextoContexto = area & " | " & nomeItem & " | " & perfil & " | " & nomeItens
            frm.AtualizarContexto

            topo = 10

            For Each item In dictOpcoes.Keys
                Set chk = frm.fraItens.Controls.Add("Forms.CheckBox.1")
                chk.Caption = CStr(item)
                chk.Left = 10
                chk.Top = topo
                chk.WordWrap = True
                chk.Width = frm.fraItens.Width - 20
                topo = topo + chk.Height + 5
            Next item

            frm.ScrollHeight = topo + 20
            frm.Show vbModal

            If frm.Tag = "CANCELADO" Then
                ProcessarDadosPlanilha = ""
                Unload frm
                Set frm = Nothing
                Exit Function
            End If

            For Each item In frm.ItensSelecionados
                If Len(resultado) > 0 Then resultado = resultado & " OU "
                resultado = resultado & CStr(item)
            Next item

            ProcessarDadosPlanilha = resultado

            Unload frm
            Set frm = Nothing
    End Select
End Function

Private Function EncontrarNoRange(ByVal alvo As Range, _
                                  ByVal textoBusca As String, _
                                  ByVal somenteWhole As Boolean) As Range
    Dim achou As Range

    If alvo Is Nothing Then Exit Function

    Set achou = alvo.Find(What:=textoBusca, _
                          LookIn:=xlValues, _
                          LookAt:=xlWhole, _
                          MatchCase:=False)

    If achou Is Nothing And Not somenteWhole Then
        Set achou = alvo.Find(What:=textoBusca, _
                              LookIn:=xlValues, _
                              LookAt:=xlPart, _
                              MatchCase:=False)
    End If

    Set EncontrarNoRange = achou
End Function

Private Function EncontrarContextoBusca(ByVal ws As Worksheet, _
                                        ByVal area As String, _
                                        ByVal nomeItem As String, _
                                        ByVal perfil As String, _
                                        ByVal ultimaColuna As Long, _
                                        ByRef rngArea As Range, _
                                        ByRef rngItem As Range, _
                                        ByRef rngPerfil As Range) As Boolean
    Dim cel As Range
    Dim faixaArea As Range
    Dim faixaItem As Range
    Dim tentativaItem As Range
    Dim tentativaPerfil As Range
    Dim linhaInicial As Long
    Dim linhaFinal As Long
    Dim chaveArea As String
    Dim areasVisitadas As Object

    Set areasVisitadas = CreateObject("Scripting.Dictionary")

    For Each cel In ws.UsedRange.Cells
        If CorrespondeTexto(cel.Value, area, False) Then
            chaveArea = cel.MergeArea.Address

            If Not areasVisitadas.Exists(chaveArea) Then
                areasVisitadas.Add chaveArea, True

                linhaInicial = cel.MergeArea.Row
                linhaFinal = linhaInicial + cel.MergeArea.Rows.Count - 1
                Set faixaArea = ws.Range(ws.Cells(linhaInicial, 1), ws.Cells(linhaFinal, ultimaColuna))

                Set tentativaItem = EncontrarNoRange(faixaArea, nomeItem, False)

                If Not tentativaItem Is Nothing Then
                    linhaInicial = tentativaItem.MergeArea.Row
                    linhaFinal = linhaInicial + tentativaItem.MergeArea.Rows.Count - 1
                    Set faixaItem = ws.Range(ws.Cells(linhaInicial, 1), ws.Cells(linhaFinal, ultimaColuna))

                    Set tentativaPerfil = EncontrarNoRange(faixaItem, perfil, True)

                    If Not tentativaPerfil Is Nothing Then
                        Set rngArea = cel
                        Set rngItem = tentativaItem
                        Set rngPerfil = tentativaPerfil
                        EncontrarContextoBusca = True
                        Exit Function
                    End If
                End If
            End If
        End If
    Next cel
End Function

Private Function CorrespondeTexto(ByVal valorCelula As Variant, _
                                  ByVal textoBusca As String, _
                                  ByVal somenteWhole As Boolean) As Boolean
    Dim textoCelula As String
    Dim textoFiltro As String

    textoCelula = LCase$(Trim$(CStr(valorCelula)))
    textoFiltro = LCase$(Trim$(textoBusca))

    If Len(textoCelula) = 0 Or Len(textoFiltro) = 0 Then Exit Function

    If somenteWhole Then
        CorrespondeTexto = (textoCelula = textoFiltro)
    Else
        CorrespondeTexto = (textoCelula = textoFiltro Or InStr(1, textoCelula, textoFiltro, vbTextCompare) > 0)
    End If
End Function

Private Function EncontrarCabecalho(ByVal ws As Worksheet, _
                                    ByVal textoCabecalho As String, _
                                    ByVal linhaInicio As Long, _
                                    ByVal linhaFim As Long) As Range
    Dim linha As Long
    Dim achou As Range

    For linha = linhaInicio To linhaFim
        Set achou = ws.Rows(linha).Find(What:=textoCabecalho, _
                                        LookIn:=xlValues, _
                                        LookAt:=xlWhole, _
                                        MatchCase:=False)
        If Not achou Is Nothing Then
            Set EncontrarCabecalho = achou
            Exit Function
        End If
    Next linha

    For linha = linhaInicio To linhaFim
        Set achou = ws.Rows(linha).Find(What:=textoCabecalho, _
                                        LookIn:=xlValues, _
                                        LookAt:=xlPart, _
                                        MatchCase:=False)
        If Not achou Is Nothing Then
            Set EncontrarCabecalho = achou
            Exit Function
        End If
    Next linha
End Function

Private Function LimparTexto(ByVal valor As Variant) As String
    LimparTexto = Trim$(Replace(CStr(valor), vbCrLf, " "))
End Function

Function check() As Boolean
    Dim lastRow As Long
    Dim i As Long
    Dim ws As Worksheet

    Set ws = Planilha8
    lastRow = ws.Cells(ws.Rows.Count, "B").End(xlUp).Row

    For i = 6 To lastRow
        If Len(ws.Cells(i, 2).Value) >= 5 Then
            If ws.Cells(i, 3).Value = True Then
                If ws.Cells(i, 4).Value = "" Then
                    MsgBox "A coluna Áreas do item " & ws.Cells(i, 5).Value & " está vazia!"
                    MsgBox "Cheque se todos os itens marcados estão com o item da coluna 'Áreas' preenchido!"
                    check = True
                    Exit Function
                End If
            End If
        End If
    Next i
End Function

Sub limpar_check()

    Dim lastRow As Long
    Dim i As Long
    Dim ws As Worksheet

    Set ws = Planilha8
    lastRow = ws.Cells(ws.Rows.Count, "B").End(xlUp).Row

    For i = 6 To lastRow
        ws.Cells(i, 3).Value = False
    Next i
End Sub

Sub limpar()
    Dim lastRow As Long
    Dim lastCol As Long
    Dim ws As Worksheet

    Set ws = Planilha8
    lastRow = ws.Cells(ws.Rows.Count, "B").End(xlUp).Row
    lastCol = ws.Cells(5, ws.Columns.Count).End(xlToLeft).Column

    ws.Range( _
        ws.Cells(6, 6), _
        ws.Cells(lastRow, lastCol) _
    ).ClearContents
End Sub

Sub capa()
    Application.ScreenUpdating = False
    Planilha7.Activate
    Planilha7.Range("A1").Select
    Application.ScreenUpdating = True
End Sub

Sub controle()
    Application.ScreenUpdating = False
    Planilha8.Activate
    Planilha8.Range("A1").Select
    Application.ScreenUpdating = True
End Sub
