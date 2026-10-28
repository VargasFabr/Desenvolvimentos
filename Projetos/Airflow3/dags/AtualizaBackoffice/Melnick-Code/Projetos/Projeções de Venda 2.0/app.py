# App pricipal para rodar o projeto de projeção de vendas

import streamlit as st

#=== Lógica e dados ===#
from typing import Type, Any, List
from dataclasses import is_dataclass, fields
from typing import get_type_hints
from data_manager import Torre, Empreendimento, Projecao, Serie, ItemSerie

if "toasts" not in st.session_state:
    st.session_state["toasts"] = []

if "empreendimentos" not in st.session_state:
    st.session_state["empreendimentos"] = []
if "indice_empreendimento_selecionado" not in st.session_state:
    st.session_state["indice_empreendimento_selecionado"] = None

#=== Componentes de interface ===#

# Gerais

def _reset_selectbox(key: str | None, new_index: int | None) -> None:
    if key is None:
        return
    try:
        st.session_state[key] = new_index  # Reseta o selectbox para o índice especificado (ex: None para desmarcar qualquer opção selecionada) para evitar que fique selecionada uma opção que não foi cadastrada devido ao cancelamento ou erro no formulário
        #st.rerun()  # Recarrega a página para refletir a mudança
    except KeyError:
        st.warning(f"Chave '{key}' não encontrada no session_state. Nenhuma ação realizada.")

def _on_form_dismiss() -> None:
    raise Exception("Formulário fechado") # Lança uma exceção para interromper a execução do formulário e evitar que o código abaixo seja executado, já que o formulário foi fechado sem submissão
    form_state = st.session_state.pop("form_state", {}) # Remove as informações do estado do formulário

    if not form_state:
        st.warning("Estado do formulário não encontrado. Nenhuma ação realizada.")
        return
    
    if form_state.get("from_selectbox") is None:
        return # Se o formulário não foi chamado a partir de um selectbox, não é necessário resetar nenhum selectbox de origem, então apenas retorna sem fazer nada
    
    _reset_selectbox(form_state.get("from_selectbox"), form_state.get("new_selectbox_index")) # Reseta o selectbox de origem para evitar que fique selecionada uma opção que não foi cadastrada devido ao cancelamento ou erro no formulário

    # if submited and not error: # Se o formulário foi submetido com sucesso, seleciona a nova opção no selectbox de origem usando o índice da nova instância criada
    #     st.session_state[from_selectbox_key] = st.session_state[from_selectbox_key][new_selectbox_index]  # Seleciona a nova opção no selectbox de origem usando o índice da nova instância criada
    # if not submited or error: # Se o formulário não foi submetido ou ocorreu um erro
    #     st.toast("Formulário cancelado ou ocorreu um erro. Nenhuma alteração foi salva.", icon="⚠️")
    #     _reset_selectbox(form_state.get("from_selectbox"), new_selectbox_index) # Reseta o selectbox de origem para evitar que fique selecionada uma opção que não foi cadastrada devido ao cancelamento ou erro no formulário
    #st.rerun()  # Recarrega a página para refletir a mudança

# Formulário para cadastro de qualquer dataclass (em um modal)
@st.dialog(title="Fomulário", on_dismiss="rerun", dismissible=False)
def _form(header: str, class_to_create: Type[Any], default_fields: dict, append_to_list: List, from_selectbox: str | None = None) -> None:
    """
    Função para criar um formulário de cadastro genérico para qualquer dataclass, usando introspecção
    para criar os inputs dinamicamente com base nos campos da dataclass e seus tipos, e adicionando a
    instância criada a uma lista de destino (ex: ao cadastrar uma nova torre, a instância da torre
    criada é adicionada à lista de torres do empreendimento correspondente) para facilitar o gerenciamento
    dos dados e evitar a necessidade de criar formulários específicos para cada tipo de dado (ex: um
    formulário específico para cadastrar empreendimentos e outro formulário específico para cadastrar torres),
    além de permitir que o formulário seja chamado a partir de um selectbox para cadastrar novas opções diretamente
    a partir do selectbox (ex: ao selecionar a opção "Adicionar novo empreendimento" no selectbox de empreendimento,
    o formulário é aberto para cadastrar um novo empreendimento e, ao finalizar o cadastro, a nova opção é
    automaticamente selecionada no selectbox de empreendimento) e garantindo que os dados sejam validados antes
    de serem adicionados à lista de destino (ex: verificar se o campo "total_unidades" é um número inteiro
    positivo antes de criar a instância da torre) para evitar inconsistências nos dados e erros na aplicação.
    Args:
        header (str): O título do formulário que será exibido no modal.
        class_to_create (Type[Any]): A classe da dataclass para a qual o formulário será criado. A função usa introspecção para criar os inputs dinamicamente com base nos campos e tipos dessa dataclass.
        default_fields (dict): Um dicionário com os valores padrão para os campos do formulário
        append_to_list (List): A lista de destino à qual a instância criada será adicionada. Por exemplo, ao cadastrar uma nova torre,
            a instância da torre criada é adicionada à lista de torres do empreendimento correspondente.
            Importante passar a referência à própria lista e não uma cópia da lista para garantir que a instância criada seja adicionada à
            lista original e as mudanças sejam refletidas em toda a aplicação, já que o gerenciamento dos dados é feito usando listas
            de objetos em memória.
        from_selectbox (str | None): A chave do selectbox de origem a partir do qual o formulário foi chamado, se aplicável.
            Se o formulário foi chamado a partir de um selectbox para cadastrar uma nova opção diretamente a partir do selectbox
            (ex: ao selecionar a opção "Adicionar novo empreendimento" no selectbox de empreendimento), é importante passar
            a chave desse selectbox para que, ao finalizar o cadastro, a nova opção seja automaticamente selecionada no selectbox
            de origem. Caso o formulário não tenha sido chamado a partir de um selectbox, esse parâmetro pode ser None.
    Returns:
        None: A função não retorna nenhum valor, mas cria uma instância da dataclass especificada com os valores do formulário e adiciona essa instância à lista de destino fornecida, além de atualizar o selectbox de origem caso o formulário tenha sido chamado a partir de um selectbox.
    Examples:
        # Exemplo de uso para cadastrar um novo empreendimento a partir do selectbox de empreendimento
        _form(
            header="Cadastrar empreendimento",
            class_to_create=Empreendimento,
            default_fields={"nome": st.session_state["selectbox_empreendimento"]},
            append_to_list=st.session_state["empreendimentos"],
            from_selectbox="selectbox_empreendimento"
        )
        # Exemplo de uso para cadastrar uma nova torre a partir do selectbox de torres
        _form(
            header="Cadastrar torre",
            class_to_create=Torre,
            default_fields={"nome": st.session_state["selectbox_torres"][-1]} if st.session_state["selectbox_torres"] else {},
            append_to_list=st.session_state["empreendimentos"][st.session_state["indice_empreendimento_selecionado"]].torres,
            from_selectbox="selectbox_torres"
        )
    """

    # Apenas aceita dataclasses para garantir a estrutura dos dados
    if not is_dataclass(class_to_create):
        raise ValueError("A classe fornecida deve ser um dataclass.")

    # Cria o formulário
    with st.form("form_" + class_to_create.__name__.lower()):
        st.header(header)
        hints = get_type_hints(class_to_create) # Busca os tipos dos campos da dataclass para criar os inputs adequados no formulário
        st.write(hints)
        field_values = {} # Dicionário para armazenar os valores dos campos do formulário, que serão usados para criar a instância da dataclass

        # Itera sobre os campos da dataclass para criar os inputs do formulário dinamicamente
        for field in fields(class_to_create):

            field_type = hints.get(field.name, str)  # Pega o tipo do campo, ou assume str se não encontrado
            label = field.name.replace("_", " ").title() # Formata o nome do campo a partir do nome do atributo da dataclass (ex: "nome_produto" -> "Nome Produto")

            if "typing.List" in str(field_type): # Se o campo usar o typing.Lista
                field_values[field.name] = [] # Inicializa o campo como uma lista vazia, já que o formulário não suporta inputs para listas e a criação de instâncias de dataclasses aninhadas (ex: uma lista de torres dentro de um empreendimento) deve ser feita em etapas separadas usando formulários separados para cada nível da hierarquia de dados (ex: primeiro cadastrar o empreendimento e depois as torres correspondentes a esse empreendimento usando um formulário separado para cada torre)
                continue # Pula a criação de um input para esse campo, já que o formulário não suporta inputs para listas e a criação de instâncias de dataclasses aninhadas deve ser feita em etapas separadas usando formulários separados para cada nível da hierarquia de dados
            
            # Caso algum campo tenha um valor padrão definido, preenche o input do formulário com esse valor para facilitar o cadastro (ex: ao cadastrar uma nova torre, já preencher o campo "total_unidades" com o valor do empreendimento pai)
            default_value = default_fields.get(field.name) if default_fields else None

            if field_type == int:
                field_values[field.name] = st.number_input(label, min_value=0, step=1, value=default_value if default_value is not None else 0)
            elif field_type == float:
                field_values[field.name] = st.number_input(label, min_value=0.0, step=1, value=default_value if default_value is not None else 0.0)
            elif field_type == str:
                field_values[field.name] = st.text_input(label, value=default_value if default_value is not None else "")
            elif field_type == bool:
                field_values[field.name] = st.checkbox(label, value=default_value if default_value is not None else False)
            else:
                st.warning(f"Tipo de campo '{field_type}' não suportado. O campo '{field.name}' será ignorado.")
                field_values[field.name] = None  # Define como None para evitar erros na criação da instância

        # Botão de submissão do formulário
        with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="right"):
            submitted = st.form_submit_button("Salvar")
            cancelled = st.form_submit_button("Cancelar", type="tertiary")
            
        # Ao apertar o botão de salvar
        if submitted:
            try: # Tenta criar a instância da dataclass com os valores do formulário para validar os dados antes de adicionar à lista (ex: verificar se o campo "total_unidades" é um número inteiro positivo)
                created_instance = class_to_create(**field_values)  # Tenta criar a instância para validar os dados
                append_to_list.append(created_instance) # Adiciona a instância criada à lista correspondente de destino
                # Adicionao o toast de sucesso ao session_state para ser exibido após o reload da página, já que o formulário está dentro de um modal e não é possível mostrar o toast imediatamente
                st.session_state["toasts"].append({
                    "success": True,
                    "message": f"{class_to_create.__name__} cadastrado com sucesso!"
                })
                if from_selectbox:
                    current_value = st.session_state.get(from_selectbox) # Busca o valor atual do selectbox de origem
                    if isinstance(current_value, list):
                        pass
                        #st.session_state[from_selectbox] = current_value + [created_instance]  # Adiciona a nova instância à lista de opções do selectbox de origem, caso o selectbox seja do tipo multiselect
                    else:
                        st.session_state[from_selectbox] = created_instance # Atualiza a opção selecionada no selectbox de empreendimento para a nova instância criada, caso a nova instância seja um empreendimento e o formulário tenha sido chamado a partir do selectbox de empreendimento
                st.rerun()  # Recarrega a página para refletir as mudanças (ex: mostrar o toast de sucesso e selecionar a nova opção no selectbox de origem caso o formulário tenha sido chamado a partir de um selectbox)
            except Exception as e: # Caso a criação da instância falhe (ex: devido a um valor inválido no formulário), mostra o erro e mantém o formulário aberto para correção
                st.error(f"Erro ao criar a instância: {e}") # Mostra um erro na interface para o usuário
                # Adiciona o toast de erro ao session_state para ser exibido após o reload
                st.session_state["toasts"].append({
                    "success": False,
                    "message": f"Erro ao cadastrar {class_to_create.__name__}: {e}"
                })
                if from_selectbox:
                    current_value = st.session_state.get(from_selectbox) # Busca o valor atual do selectbox de origem
                    if isinstance(current_value, list):
                        pass
                    else:
                        st.session_state[from_selectbox] = None # Reseta a opção selecionada no selectbox de empreendimento para evitar que fique selecionada uma opção que não foi cadastrada devido ao erro no formulário, caso a nova instância seja um empreendimento e o formulário tenha sido chamado a partir do selectbox de empreendimento
                st.rerun()
        
        if cancelled:
            st.session_state["toasts"].append({
                "success": None,
                "message": f"Formulário de cadastro de {class_to_create.__name__} cancelado. Nenhuma alteração foi salva."
            })
            if from_selectbox:
                current_value = st.session_state.get(from_selectbox) # Busca o valor atual do selectbox de origem
                if isinstance(current_value, list):
                    pass
                else:
                    st.session_state[from_selectbox] = None # Reseta a opção selecionada no selectbox de empreendimento para evitar que fique selecionada uma opção que não foi cadastrada devido ao cancelamento do formulário, caso o formulário tenha sido chamado a partir do selectbox de empreendimento
            st.rerun()  # Recarrega a página para refletir o cancelamento do formulário (ex: mostrar o toast de cancelamento e resetar o selectbox de origem caso o formulário tenha sido chamado a partir de um selectbox)


def _call_toasts() -> None:
    if st.session_state.get("toasts", []) != []:
        toasts = st.session_state.pop("toasts")  # Remove os toasts do session_state para evitar repetição
        for toast in toasts:
            if toast["success"]:
                st.toast(body=toast["message"], icon="✅")
            elif not toast["success"]:
                st.toast(body=toast["message"], icon="❌")
            else:
                st.toast(body=toast["message"])
        # Reinicializa a lista de toasts no session_state para evitar que toasts antigos sejam exibidos novamente em reloads futuros
        st.session_state["toasts"] = []



#=== Renderização da página ===#

# Configurações da página
st.set_page_config(
    page_title="Projeção de Vendas 2.0",
    page_icon="📈",
    layout="wide",
)

_call_toasts()

with st.container(horizontal=True, vertical_alignment="bottom"):
    st.header("Projeções de Venda")

    available_buildings = st.session_state["empreendimentos"]
    st.selectbox(
        key="selectbox_empreendimento",
        label="Empreendimento",
        placeholder="Selecione um empreendimento",     
        options=available_buildings,
        format_func=lambda e: e.nome if e else "Nenhum empreendimento cadastrado",
        accept_new_options=True
    )
    if st.session_state["selectbox_empreendimento"] is not None and st.session_state["selectbox_empreendimento"] not in st.session_state["empreendimentos"]:
        _form(
            header="Cadastrar empreendimento",
            class_to_create=Empreendimento,
            default_fields={"nome": st.session_state["selectbox_empreendimento"]},
            append_to_list=st.session_state["empreendimentos"],
            from_selectbox="selectbox_empreendimento"
        )
    elif st.session_state["selectbox_empreendimento"] is not None and st.session_state["selectbox_empreendimento"] in st.session_state["empreendimentos"]:
        st.session_state["indice_empreendimento_selecionado"] = st.session_state["empreendimentos"].index(st.session_state["selectbox_empreendimento"]) # Atualiza o índice do empreendimento selecionado no session_state para ser usado como referência para outros componentes (ex: selectbox de torres) e evitar inconsistências caso o usuário selecione um empreendimento diferente do que estava selecionado anteriormente, já que o selectbox de torres depende do empreendimento selecionado para mostrar as torres correspondentes a esse empreendimento

    try:
        available_towers = st.session_state["empreendimentos"][st.session_state["indice_empreendimento_selecionado"]].torres if st.session_state["indice_empreendimento_selecionado"] is not None else []
    except IndexError:
        available_towers = []
        st.warning("Índice de empreendimento selecionado é inválido. Nenhuma torre disponível para seleção.")
        
    selected_towers_list = st.multiselect(
        key="selectbox_torres",
        label="Torres",
        options=available_towers,
        format_func=lambda t: t.nome,
        placeholder="Selecione as torres",
        accept_new_options=True
    )
    if st.session_state["selectbox_torres"] is not None and any(tower for tower in st.session_state["selectbox_torres"] if tower not in available_towers):
        if selected_towers_list and any(tower for tower in selected_towers_list if tower not in st.session_state["selectbox_empreendimento"].torres):
            _form(
                header="Cadastrar torre",
                class_to_create=Torre,
                default_fields={"nome": selected_towers_list[-1]} if selected_towers_list else {},
                append_to_list=st.session_state["empreendimentos"][st.session_state["indice_empreendimento_selecionado"]].torres,
                from_selectbox="selectbox_torres"
            )

st.write("Índice empreendimento selecionado")
st.session_state["indice_empreendimento_selecionado"]
st.write("Opção selecionada no selectbox de empreendimento")
st.session_state["selectbox_empreendimento"]
st.write("Tipo do selectbox de empreendimento")
st.write(type(st.session_state["selectbox_empreendimento"]))
st.write("Torres disponíveis para o empreendimento selecionado")
st.session_state["empreendimentos"][st.session_state["indice_empreendimento_selecionado"]].torres if st.session_state["indice_empreendimento_selecionado"] is not None else []
st.write("Opções selecionadas no multiselect de torres")
available_towers
st.write("Opções selecionadas no multiselect de torres")
st.session_state["selectbox_torres"]

st.button("Formulário", on_click=lambda: _form(
    header="Cadastrar torre",
    class_to_create=Torre,
    default_fields={},
    append_to_list=st.session_state["empreendimentos"][st.session_state["indice_empreendimento_selecionado"]].torres if st.session_state["indice_empreendimento_selecionado"] is not None else [],
    #from_selectbox="selectbox_torres"
))

st.session_state["empreendimentos"]