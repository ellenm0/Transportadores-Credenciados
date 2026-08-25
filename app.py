import streamlit as st
import requests
import json
import base64
import uuid
from datetime import datetime, date
from io import BytesIO
import streamlit.components.v1 as components


st.set_page_config(
    page_title="Transportadores Licenciados e Credenciados",
    page_icon="🚛",
    layout="wide"
)


MODALIDADES = [
    "COLETA E TRANSPORTE DE RESÍDUOS NÃO PERIGOSOS",
    "COLETA DE RESÍDUOS PERIGOSOS",
    "COLETA DE RESÍDUOS VEGETAIS E DA CONSTRUÇÃO CIVIL COM FORNECIMENTO DE CAÇAMBA ESTACIONÁRIA",
    "COLETA DE RESÍDUOS VEGETAIS E DA CONSTRUÇÃO CIVIL PROVENIENTES DE ESCAVAÇÃO, DE DEMOLIÇÃO E DE SERVIÇOS DE TERRAPLENAGEM, POR MEIO DE CAÇAMBA BASCULANTE",
    "COLETA DE RESÍDUOS DE SERVIÇOS DE SAÚDE (HOSPITALAR E AMBULATORIAL)",
    "COLETA DE RESÍDUOS DE SERVIÇOS DE SAÚDE (AMBULATORIAL)",
    "COLETA DE RESÍDUOS RECICLÁVEIS",
    "COLETA DE PRODUTOS E EMBALAGENS OBJETOS DE LOGÍSTICA REVERSA",
    "COLETA DE EFLUENTES",
]


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def normalizar_cnpj(valor):
    return "".join(
        c for c in str(valor or "")
        if c.isdigit()
    )


def formatar_cnpj(valor):
    numeros = normalizar_cnpj(valor)

    if len(numeros) == 14:
        return (
            f"{numeros[:2]}."
            f"{numeros[2:5]}."
            f"{numeros[5:8]}/"
            f"{numeros[8:12]}-"
            f"{numeros[12:]}"
        )

    return str(valor or "")


# ==========================================================
# CONFIGURAÇÃO DO GITHUB
# ==========================================================

def github_config():

    token = st.secrets.get(
        "GITHUB_TOKEN",
        ""
    ).strip()

    repo = st.secrets.get(
        "GITHUB_REPOSITORY",
        ""
    ).strip()

    branch = st.secrets.get(
        "GITHUB_BRANCH",
        "main"
    ).strip()

    data_dir = st.secrets.get(
        "GITHUB_DATA_DIR",
        "dados"
    ).strip().strip("/")

    return token, repo, branch, data_dir


def github_request(
    method,
    url,
    token,
    **kwargs
):

    headers = kwargs.pop(
        "headers",
        {}
    )

    headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    })

    return requests.request(
        method,
        url,
        headers=headers,
        timeout=30,
        **kwargs
    )


# ==========================================================
# VERIFICAÇÃO DO GITHUB
# ==========================================================

def verificar_github():

    token, repo, branch, data_dir = github_config()

    if not token:
        return False, (
            "GITHUB_TOKEN não foi configurado "
            "nos Secrets do Streamlit."
        )

    if not repo:
        return False, (
            "GITHUB_REPOSITORY não foi configurado "
            "nos Secrets do Streamlit."
        )

    if "/" not in repo:
        return False, (
            "GITHUB_REPOSITORY está incorreto. "
            "Use o formato usuario/repositorio."
        )

    url = f"https://api.github.com/repos/{repo}"

    resposta = github_request(
        "GET",
        url,
        token
    )

    if resposta.status_code == 200:
        dados = resposta.json()

        nome = dados.get(
            "full_name",
            repo
        )

        branch_padrao = dados.get(
            "default_branch",
            branch
        )

        return True, (
            f"GitHub conectado corretamente ao "
            f"repositório {nome}, branch {branch_padrao}."
        )

    if resposta.status_code == 401:
        return False, (
            "O GITHUB_TOKEN foi recusado pelo GitHub. "
            "Verifique se o token está correto e possui "
            "permissão para acessar o repositório."
        )

    if resposta.status_code == 403:
        return False, (
            "O GitHub recusou o acesso. "
            "Verifique as permissões do GITHUB_TOKEN."
        )

    if resposta.status_code == 404:
        return False, (
            f"O GitHub não encontrou o repositório "
            f"'{repo}'. "
            f"Verifique o GITHUB_REPOSITORY nos Secrets."
        )

    return False, (
        f"Erro ao verificar o GitHub "
        f"({resposta.status_code}): "
        f"{resposta.text[:500]}"
    )


# ==========================================================
# CAMINHO DOS ARQUIVOS
# ==========================================================

def caminho_arquivo_github(
    nome_arquivo
):

    token, repo, branch, data_dir = github_config()

    if data_dir:
        return f"{data_dir}/{nome_arquivo}"

    return nome_arquivo


# ==========================================================
# CARREGAR ARQUIVO DO GITHUB
# ==========================================================

def carregar_arquivo_github(
    nome_arquivo,
    padrao
):

    token, repo, branch, data_dir = github_config()

    if not token or not repo:
        return (
            padrao,
            None,
            False,
            "Configure GITHUB_TOKEN e GITHUB_REPOSITORY "
            "nos Secrets do Streamlit."
        )

    caminho = caminho_arquivo_github(
        nome_arquivo
    )

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{caminho}"
    )

    resposta = github_request(
        "GET",
        url,
        token,
        params={
            "ref": branch
        }
    )

    if resposta.status_code == 200:

        dados = resposta.json()

        try:

            conteudo = base64.b64decode(
                dados["content"]
            ).decode("utf-8")

            return (
                json.loads(conteudo),
                dados.get("sha"),
                True,
                ""
            )

        except Exception as erro:

            return (
                padrao,
                None,
                False,
                f"Não foi possível ler "
                f"{caminho}: {erro}"
            )

    if resposta.status_code == 404:

        # Arquivo ainda não existe.
        # Isso é normal na primeira utilização.
        return (
            padrao,
            None,
            True,
            ""
        )

    if resposta.status_code == 401:

        return (
            padrao,
            None,
            False,
            "O GITHUB_TOKEN foi recusado pelo GitHub."
        )

    if resposta.status_code == 403:

        return (
            padrao,
            None,
            False,
            "O GitHub recusou o acesso. "
            "Verifique as permissões do token."
        )

    return (
        padrao,
        None,
        False,
        f"Erro ao acessar o GitHub "
        f"({resposta.status_code}): "
        f"{resposta.text[:500]}"
    )


# ==========================================================
# SALVAR ARQUIVO NO GITHUB
# ==========================================================

def salvar_arquivo_github(
    nome_arquivo,
    dados,
    sha=None,
    mensagem="Atualização dos dados"
):

    token, repo, branch, data_dir = github_config()

    if not token:
        return (
            False,
            "GITHUB_TOKEN não está configurado."
        )

    if not repo:
        return (
            False,
            "GITHUB_REPOSITORY não está configurado."
        )

    caminho = caminho_arquivo_github(
        nome_arquivo
    )

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{caminho}"
    )

    conteudo = json.dumps(
        dados,
        ensure_ascii=False,
        indent=2
    )

    conteudo_base64 = base64.b64encode(
        conteudo.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": mensagem,
        "content": conteudo_base64,
        "branch": branch
    }

    # Se o arquivo já existe, o SHA é obrigatório.
    if sha:
        payload["sha"] = sha

    resposta = github_request(
        "PUT",
        url,
        token,
        json=payload
    )

    if resposta.status_code in (200, 201):
        return True, ""

    if resposta.status_code == 401:
        return (
            False,
            "O GitHub recusou o GITHUB_TOKEN."
        )

    if resposta.status_code == 403:
        return (
            False,
            "O GitHub recusou a gravação. "
            "Verifique as permissões do GITHUB_TOKEN."
        )

    if resposta.status_code == 404:
        return (
            False,
            "O GitHub não encontrou o repositório "
            f"'{repo}' ou o token não possui acesso "
            "a ele. Verifique GITHUB_REPOSITORY e "
            "as permissões do token."
        )

    if resposta.status_code == 409:
        return (
            False,
            "O arquivo foi alterado no GitHub por "
            "outra ação. Atualize o aplicativo e tente "
            "novamente."
        )

    return (
        False,
        f"Erro ao salvar no GitHub "
        f"({resposta.status_code}): "
        f"{resposta.text[:500]}"
    )


# ==========================================================
# CARREGAMENTO DOS DADOS
# ==========================================================

def carregar_dados():

    transportadores, sha_t, ok_t, erro_t = (
        carregar_arquivo_github(
            "transportadores.json",
            []
        )
    )

    historico, sha_h, ok_h, erro_h = (
        carregar_arquivo_github(
            "historico.json",
            []
        )
    )

    relatorios, sha_r, ok_r, erro_r = (
        carregar_arquivo_github(
            "relatorios.json",
            []
        )
    )

    if not ok_t:
        st.error(erro_t)

    if not ok_h:
        st.error(erro_h)

    if not ok_r:
        st.error(erro_r)

    if not isinstance(
        transportadores,
        list
    ):
        transportadores = []

    if not isinstance(
        historico,
        list
    ):
        historico = []

    if not isinstance(
        relatorios,
        list
    ):
        relatorios = []

    return (
        transportadores,
        historico,
        relatorios,
        sha_t,
        sha_h,
        sha_r
    )


# ==========================================================
# CRIAR ARQUIVOS INICIAIS
# ==========================================================

def garantir_dados_no_github(
    transportadores,
    historico,
    relatorios,
    sha_t,
    sha_h,
    sha_r
):

    token, repo, branch, data_dir = github_config()

    if not token or not repo:
        return

    if sha_t is None:

        salvar_arquivo_github(
            "transportadores.json",
            transportadores,
            None,
            "Criar cadastro inicial"
        )

    if sha_h is None:

        salvar_arquivo_github(
            "historico.json",
            historico,
            None,
            "Criar histórico inicial"
        )

    if sha_r is None:

        salvar_arquivo_github(
            "relatorios.json",
            relatorios,
            None,
            "Criar histórico de relatórios"
        )


# ==========================================================
# HISTÓRICO
# ==========================================================

def snapshot_transportador(
    transportador,
    acao
):

    return {
        "data": agora_iso(),
        "acao": acao,
        "transportador": json.loads(
            json.dumps(
                transportador,
                ensure_ascii=False
            )
        )
    }


# ==========================================================
# ENDEREÇO
# ==========================================================

def montar_endereco(
    transportador
):

    partes = []

    logradouro = transportador.get(
        "logradouro",
        ""
    ).strip()

    numero = transportador.get(
        "numero",
        ""
    ).strip()

    complemento = transportador.get(
        "complemento",
        ""
    ).strip()

    bairro = transportador.get(
        "bairro",
        ""
    ).strip()

    municipio = transportador.get(
        "municipio",
        ""
    ).strip()

    uf = transportador.get(
        "uf",
        ""
    ).strip()

    if logradouro:

        endereco = logradouro

        if numero:
            endereco += f", Nº {numero}"

        if complemento:
            endereco += f", {complemento}"

        partes.append(endereco)

    if bairro:
        partes.append(bairro)

    cidade_uf = " - ".join(
        x for x in [
            municipio,
            uf
        ]
        if x
    )

    if cidade_uf:
        partes.append(cidade_uf)

    return ", ".join(partes)


# ==========================================================
# CONTATO
# ==========================================================

def montar_contato(
    transportador
):

    partes = []

    telefone = transportador.get(
        "telefone",
        ""
    ).strip()

    email = transportador.get(
        "email",
        ""
    ).strip()

    if telefone:
        partes.append(
            f"Fone: {telefone}"
        )

    if email:
        partes.append(
            f"E-mail: {email}"
        )

    return " ".join(partes)


# ==========================================================
# BLOCO DO TRANSPORTADOR
# ==========================================================

def gerar_bloco_transportador(
    transportador
):

    linhas = []

    nome = transportador.get(
        "nome",
        ""
    ).strip()

    if nome:
        linhas.append(nome)

    cnpj = formatar_cnpj(
        transportador.get(
            "cnpj",
            ""
        )
    )

    if cnpj:
        linhas.append(
            f"CNPJ: {cnpj}"
        )

    endereco = montar_endereco(
        transportador
    )

    if endereco:
        linhas.append(endereco)

    contato = montar_contato(
        transportador
    )

    if contato:
        linhas.append(contato)

    tipo = transportador.get(
        "tipo_credenciamento",
        ""
    ).strip()

    numero = transportador.get(
        "numero_credenciamento",
        ""
    ).strip()

    validade_credenciamento = (
        transportador.get(
            "validade_credenciamento",
            ""
        ).strip()
    )

    if tipo and numero:

        linhas.append(
            f"{tipo}: {numero}"
        )

    elif numero:

        linhas.append(
            f"Credenciamento: {numero}"
        )

    if validade_credenciamento:

        linhas.append(
            f"VALIDADE: {validade_credenciamento}"
        )

    descricao_licenca = (
        transportador.get(
            "descricao_licenca",
            ""
        ).strip()
    )

    validade_licenca = (
        transportador.get(
            "validade_licenca",
            ""
        ).strip()
    )

    if descricao_licenca:
        linhas.append(
            descricao_licenca
        )

    if validade_licenca:

        linhas.append(
            f"VALIDADE: {validade_licenca}"
        )

    return "\n".join(linhas)


# ==========================================================
# GERAR RELATÓRIO
# ==========================================================

def gerar_relatorio(
    transportadores,
    data_atualizacao
):

    linhas = [
        "RELAÇÃO DE TRANSPORTADORES LICENCIADOS E CREDENCIADOS",
        f"ATUALIZADA EM {data_atualizacao}",
        ""
    ]

    for modalidade in MODALIDADES:

        empresas = []

        for transportador in transportadores:

            if not transportador.get(
                "ativo",
                True
            ):
                continue

            modalidades = transportador.get(
                "modalidades",
                []
            )

            if modalidade in modalidades:
                empresas.append(
                    transportador
                )

        if not empresas:
            continue

        linhas.append(
            f"MODALIDADE: {modalidade}"
        )

        linhas.append("")

        empresas.sort(
            key=lambda x: x.get(
                "nome",
                ""
            ).upper()
        )

        vistos = set()

        for transportador in empresas:

            chave = normalizar_cnpj(
                transportador.get(
                    "cnpj",
                    ""
                )
            )

            if not chave:

                chave = transportador.get(
                    "id",
                    ""
                )

            if chave in vistos:
                continue

            vistos.add(chave)

            linhas.append(
                gerar_bloco_transportador(
                    transportador
                )
            )

            linhas.append("")

    while linhas and linhas[-1] == "":
        linhas.pop()

    return "\n".join(linhas)


# ==========================================================
# CRIAR WORD
# ==========================================================

def criar_docx(texto):

    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    documento = Document()

    secao = documento.sections[0]

    secao.top_margin = Pt(50)
    secao.bottom_margin = Pt(50)
    secao.left_margin = Pt(60)
    secao.right_margin = Pt(60)

    for linha in texto.splitlines():

        paragrafo = documento.add_paragraph()

        paragrafo.paragraph_format.space_after = Pt(4)

        if linha.startswith(
            "RELAÇÃO DE TRANSPORTADORES"
        ):

            paragrafo.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER
            )

            run = paragrafo.add_run(linha)
            run.bold = True
            run.font.size = Pt(14)

        elif linha.startswith(
            "ATUALIZADA EM"
        ):

            paragrafo.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER
            )

            run = paragrafo.add_run(linha)
            run.bold = True
            run.font.size = Pt(11)

        elif linha.startswith(
            "MODALIDADE:"
        ):

            paragrafo.paragraph_format.space_before = Pt(12)

            run = paragrafo.add_run(linha)
            run.bold = True
            run.font.size = Pt(11)

        elif linha.strip():

            run = paragrafo.add_run(linha)
            run.font.size = Pt(10)

    arquivo = BytesIO()

    documento.save(arquivo)

    arquivo.seek(0)

    return arquivo


# ==========================================================
# COPIAR RELATÓRIO
# ==========================================================

def copiar_texto_componente(
    texto,
    identificador
):

    texto_js = json.dumps(
        texto,
        ensure_ascii=False
    )

    html = f"""
    <div style="
        display:flex;
        align-items:center;
        gap:10px;
        font-family:Arial,sans-serif;
        margin:4px 0 8px 0;
    ">

        <button
            id="btn_{identificador}"
            style="
                background:#ff4b4b;
                color:white;
                border:none;
                border-radius:6px;
                padding:10px 18px;
                cursor:pointer;
                font-size:14px;
                font-weight:600;
            "
        >
            Copiar relatório
        </button>

        <span
            id="msg_{identificador}"
            style="
                font-size:14px;
                color:#228b22;
            "
        ></span>

    </div>

    <script>

        const texto = {texto_js};

        document
            .getElementById("btn_{identificador}")
            .addEventListener("click", async function() {{

                try {{

                    await navigator.clipboard.writeText(texto);

                    document.getElementById(
                        "msg_{identificador}"
                    ).innerText = "Relatório copiado!";

                }} catch (erro) {{

                    const area = document.createElement("textarea");

                    area.value = texto;

                    document.body.appendChild(area);

                    area.select();

                    document.execCommand("copy");

                    document.body.removeChild(area);

                    document.getElementById(
                        "msg_{identificador}"
                    ).innerText = "Relatório copiado!";

                }}

            }});

    </script>
    """

    components.html(
        html,
        height=55
    )


# ==========================================================
# VALIDAR TRANSPORTADOR
# ==========================================================

def validar_transportador(
    transportador,
    transportadores,
    id_atual=None
):

    erros = []

    if not transportador[
        "nome"
    ].strip():

        erros.append(
            "Informe o Nome/Razão Social."
        )

    cnpj = normalizar_cnpj(
        transportador["cnpj"]
    )

    if len(cnpj) != 14:

        erros.append(
            "Informe um CNPJ com 14 dígitos."
        )

    if not transportador[
        "logradouro"
    ].strip():

        erros.append(
            "Informe a Rua/Logradouro."
        )

    if not transportador[
        "numero"
    ].strip():

        erros.append(
            "Informe o Número."
        )

    if not transportador[
        "bairro"
    ].strip():

        erros.append(
            "Informe o Bairro."
        )

    if not transportador[
        "municipio"
    ].strip():

        erros.append(
            "Informe o Município."
        )

    if not transportador[
        "uf"
    ].strip():

        erros.append(
            "Informe a UF."
        )

    if not transportador[
        "modalidades"
    ]:

        erros.append(
            "Selecione pelo menos uma modalidade."
        )

    for existente in transportadores:

        if existente.get(
            "id"
        ) == id_atual:

            continue

        cnpj_existente = normalizar_cnpj(
            existente.get(
                "cnpj",
                ""
            )
        )

        if cnpj_existente == cnpj:

            erros.append(
                "Já existe um transportador "
                "cadastrado com este CNPJ."
            )

            break

    transportador[
        "modalidades"
    ] = list(
        dict.fromkeys(
            transportador[
                "modalidades"
            ]
        )
    )

    return erros


# ==========================================================
# CARREGAR FORMULÁRIO
# ==========================================================

def carregar_formulario(
    transportador
):

    st.session_state[
        "form_nome"
    ] = transportador.get(
        "nome",
        ""
    )

    st.session_state[
        "form_cnpj"
    ] = transportador.get(
        "cnpj",
        ""
    )

    st.session_state[
        "form_logradouro"
    ] = transportador.get(
        "logradouro",
        ""
    )

    st.session_state[
        "form_numero"
    ] = transportador.get(
        "numero",
        ""
    )

    st.session_state[
        "form_complemento"
    ] = transportador.get(
        "complemento",
        ""
    )

    st.session_state[
        "form_bairro"
    ] = transportador.get(
        "bairro",
        ""
    )

    st.session_state[
        "form_municipio"
    ] = transportador.get(
        "municipio",
        ""
    )

    st.session_state[
        "form_uf"
    ] = transportador.get(
        "uf",
        "CE"
    )

    st.session_state[
        "form_telefone"
    ] = transportador.get(
        "telefone",
        ""
    )

    st.session_state[
        "form_email"
    ] = transportador.get(
        "email",
        ""
    )

    st.session_state[
        "form_tipo_credenciamento"
    ] = transportador.get(
        "tipo_credenciamento",
        "Processo de Credenciamento"
    )

    st.session_state[
        "form_numero_credenciamento"
    ] = transportador.get(
        "numero_credenciamento",
        ""
    )

    st.session_state[
        "form_validade_credenciamento"
    ] = transportador.get(
        "validade_credenciamento",
        ""
    )

    st.session_state[
        "form_descricao_licenca"
    ] = transportador.get(
        "descricao_licenca",
        ""
    )

    st.session_state[
        "form_validade_licenca"
    ] = transportador.get(
        "validade_licenca",
        ""
    )

    st.session_state[
        "form_modalidades"
    ] = transportador.get(
        "modalidades",
        []
    )

    st.session_state[
        "editando_id"
    ] = transportador.get(
        "id",
        ""
    )


# ==========================================================
# LIMPAR FORMULÁRIO
# ==========================================================

def limpar_formulario():

    chaves = [
        "form_nome",
        "form_cnpj",
        "form_logradouro",
        "form_numero",
        "form_complemento",
        "form_bairro",
        "form_municipio",
        "form_uf",
        "form_telefone",
        "form_email",
        "form_numero_credenciamento",
        "form_validade_credenciamento",
        "form_descricao_licenca",
        "form_validade_licenca",
        "form_modalidades"
    ]

    for chave in chaves:

        st.session_state.pop(
            chave,
            None
        )

    st.session_state[
        "form_tipo_credenciamento"
    ] = "Processo de Credenciamento"

    st.session_state[
        "editando_id"
    ] = None


# ==========================================================
# TELA DE FORMULÁRIO
# ==========================================================

def tela_formulario(
    transportadores,
    historico,
    sha_t,
    sha_h
):

    editando_id = st.session_state.get(
        "editando_id"
    )

    existente = None

    for transportador in transportadores:

        if transportador.get(
            "id"
        ) == editando_id:

            existente = transportador

            break

    if existente:

        st.title(
            "Editar Transportador"
        )

        st.info(
            f"Editando: "
            f"{existente.get('nome', '')} "
            f"— CNPJ "
            f"{formatar_cnpj(existente.get('cnpj', ''))}"
        )

    else:

        st.title(
            "Novo Transportador"
        )

    with st.form(
        "form_transportador",
        clear_on_submit=False
    ):

        st.subheader(
            "Dados cadastrais"
        )

        coluna1, coluna2 = st.columns(2)

        with coluna1:

            nome = st.text_input(
                "Nome/Razão Social *",
                value=st.session_state.get(
                    "form_nome",
                    existente.get(
                        "nome",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            cnpj = st.text_input(
                "CNPJ *",
                value=st.session_state.get(
                    "form_cnpj",
                    existente.get(
                        "cnpj",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            logradouro = st.text_input(
                "Rua/Logradouro *",
                value=st.session_state.get(
                    "form_logradouro",
                    existente.get(
                        "logradouro",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            numero = st.text_input(
                "Número *",
                value=st.session_state.get(
                    "form_numero",
                    existente.get(
                        "numero",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            complemento = st.text_input(
                "Complemento",
                value=st.session_state.get(
                    "form_complemento",
                    existente.get(
                        "complemento",
                        ""
                    )
                    if existente
                    else ""
                )
            )

        with coluna2:

            bairro = st.text_input(
                "Bairro *",
                value=st.session_state.get(
                    "form_bairro",
                    existente.get(
                        "bairro",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            municipio = st.text_input(
                "Município *",
                value=st.session_state.get(
                    "form_municipio",
                    existente.get(
                        "municipio",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            uf = st.text_input(
                "UF *",
                value=st.session_state.get(
                    "form_uf",
                    existente.get(
                        "uf",
                        "CE"
                    )
                    if existente
                    else "CE"
                )
            )

            telefone = st.text_input(
                "Telefone",
                value=st.session_state.get(
                    "form_telefone",
                    existente.get(
                        "telefone",
                        ""
                    )
                    if existente
                    else ""
                )
            )

            email = st.text_input(
                "E-mail",
                value=st.session_state.get(
                    "form_email",
                    existente.get(
                        "email",
                        ""
                    )
                    if existente
                    else ""
                )
            )

        st.subheader(
            "Credenciamento"
        )

        tipo_atual = st.session_state.get(
            "form_tipo_credenciamento",
            existente.get(
                "tipo_credenciamento",
                "Processo de Credenciamento"
            )
            if existente
            else "Processo de Credenciamento"
        )

        opcoes_credenciamento = [
            "Processo de Credenciamento",
            "Número de Credenciamento"
        ]

        if tipo_atual not in opcoes_credenciamento:

            tipo_atual = (
                opcoes_credenciamento[0]
            )

        tipo_credenciamento = st.selectbox(
            "Tipo",
            opcoes_credenciamento,
            index=opcoes_credenciamento.index(
                tipo_atual
            )
        )

        numero_credenciamento = st.text_input(
            "Número do processo/credenciamento",
            value=st.session_state.get(
                "form_numero_credenciamento",
                existente.get(
                    "numero_credenciamento",
                    ""
                )
                if existente
                else ""
            )
        )

        validade_credenciamento = st.text_input(
            "Validade do credenciamento",
            value=st.session_state.get(
                "form_validade_credenciamento",
                existente.get(
                    "validade_credenciamento",
                    ""
                )
                if existente
                else ""
            ),
            placeholder=(
                "Ex.: 24/05/2026, "
                "EM RENOVAÇÃO ou INDETERMINADA"
            )
        )

        st.subheader(
            "Licenciamento"
        )

        descricao_licenca = st.text_area(
            "Descrição da licença",
            value=st.session_state.get(
                "form_descricao_licenca",
                existente.get(
                    "descricao_licenca",
                    ""
                )
                if existente
                else ""
            ),
            height=100,
            placeholder=(
                "Digite livremente a descrição da licença."
            )
        )

        validade_licenca = st.text_input(
            "Validade da licença",
            value=st.session_state.get(
                "form_validade_licenca",
                existente.get(
                    "validade_licenca",
                    ""
                )
                if existente
                else ""
            ),
            placeholder=(
                "Ex.: 20/12/2027, "
                "EM RENOVAÇÃO ou INDETERMINADA"
            )
        )

        st.subheader(
            "Modalidades"
        )

        modalidades = st.multiselect(
            "Selecione uma ou várias modalidades *",
            MODALIDADES,
            default=st.session_state.get(
                "form_modalidades",
                existente.get(
                    "modalidades",
                    []
                )
                if existente
                else []
            )
        )

        coluna_salvar, coluna_cancelar = (
            st.columns(2)
        )

        with coluna_salvar:

            salvar = st.form_submit_button(
                "Salvar transportador",
                type="primary",
                use_container_width=True
            )

        with coluna_cancelar:

            cancelar = st.form_submit_button(
                "Cancelar",
                use_container_width=True
            )

    if cancelar:

        limpar_formulario()

        st.session_state[
            "pagina"
        ] = "Transportadores"

        st.rerun()

    if salvar:

        novo = {

            "id": (
                existente.get("id")
                if existente
                else str(uuid.uuid4())
            ),

            "nome": nome.strip(),

            "cnpj": normalizar_cnpj(
                cnpj
            ),

            "logradouro": logradouro.strip(),

            "numero": numero.strip(),

            "complemento": complemento.strip(),

            "bairro": bairro.strip(),

            "municipio": municipio.strip(),

            "uf": uf.strip().upper(),

            "telefone": telefone.strip(),

            "email": email.strip(),

            "tipo_credenciamento": (
                tipo_credenciamento
            ),

            "numero_credenciamento": (
                numero_credenciamento.strip()
            ),

            "validade_credenciamento": (
                validade_credenciamento.strip()
            ),

            "descricao_licenca": (
                descricao_licenca.strip()
            ),

            "validade_licenca": (
                validade_licenca.strip()
            ),

            "modalidades": list(
                dict.fromkeys(
                    modalidades
                )
            ),

            "ativo": (
                existente.get(
                    "ativo",
                    True
                )
                if existente
                else True
            ),

            "criado_em": (
                existente.get(
                    "criado_em",
                    agora_iso()
                )
                if existente
                else agora_iso()
            ),

            "atualizado_em": agora_iso()
        }

        erros = validar_transportador(
            novo,
            transportadores,
            existente.get(
                "id"
            )
            if existente
            else None
        )

        if erros:

            for erro in erros:

                st.error(erro)

        else:

            if existente:

                historico.append(
                    snapshot_transportador(
                        existente,
                        "ANTES DA EDIÇÃO"
                    )
                )

                transportadores[:] = [

                    novo
                    if x.get(
                        "id"
                    ) == existente.get(
                        "id"
                    )
                    else x

                    for x in transportadores
                ]

                mensagem = (
                    f"Editar transportador "
                    f"{novo['nome']}"
                )

            else:

                transportadores.append(
                    novo
                )

                mensagem = (
                    f"Cadastrar transportador "
                    f"{novo['nome']}"
                )

            ok1, erro1 = (
                salvar_arquivo_github(
                    "transportadores.json",
                    transportadores,
                    sha_t,
                    mensagem
                )
            )

            if not ok1:

                st.error(erro1)

            else:

                ok2, erro2 = (
                    salvar_arquivo_github(
                        "historico.json",
                        historico,
                        sha_h,
                        f"Registrar histórico - "
                        f"{novo['nome']}"
                    )
                )

                if not ok2:

                    st.warning(
                        "Cadastro salvo, mas o histórico "
                        "não pôde ser atualizado: "
                        f"{erro2}"
                    )

                st.success(
                    "Transportador salvo com sucesso."
                )

                limpar_formulario()

                st.session_state[
                    "pagina"
                ] = "Transportadores"

                st.rerun()


# ==========================================================
# TELA DE TRANSPORTADORES
# ==========================================================

def tela_transportadores(
    transportadores,
    historico,
    sha_t,
    sha_h
):

    st.title(
        "Transportadores Cadastrados"
    )

    busca = st.text_input(
        "Pesquisar por Nome ou CNPJ",
        placeholder=(
            "Digite parte do nome ou CNPJ"
        )
    )

    mostrar_inativos = st.checkbox(
        "Mostrar também os inativos",
        value=False
    )

    termo = busca.strip().lower()

    filtrados = []

    for transportador in transportadores:

        if (
            not mostrar_inativos
            and not transportador.get(
                "ativo",
                True
            )
        ):
            continue

        texto = (
            f"{transportador.get('nome', '')} "
            f"{formatar_cnpj(transportador.get('cnpj', ''))} "
            f"{normalizar_cnpj(transportador.get('cnpj', ''))}"
        ).lower()

        if not termo or termo in texto:

            filtrados.append(
                transportador
            )

    filtrados.sort(
        key=lambda x: x.get(
            "nome",
            ""
        ).upper()
    )

    st.caption(
        f"{len(filtrados)} "
        f"transportador(es) encontrado(s)."
    )

    if not filtrados:

        st.info(
            "Nenhum transportador encontrado."
        )

        return

    for transportador in filtrados:

        status = (
            "ATIVO"
            if transportador.get(
                "ativo",
                True
            )
            else "INATIVO"
        )

        with st.container(
            border=True
        ):

            coluna_info, coluna_acoes = (
                st.columns(
                    [5, 2]
                )
            )

            with coluna_info:

                st.markdown(
                    f"### "
                    f"{transportador.get('nome', '')}"
                )

                st.write(
                    f"**CNPJ:** "
                    f"{formatar_cnpj(transportador.get('cnpj', ''))}"
                )

                st.write(
                    f"**Município:** "
                    f"{transportador.get('municipio', '')} "
                    f"— **Status:** {status}"
                )

                modalidades_texto = "; ".join(
                    transportador.get(
                        "modalidades",
                        []
                    )
                )

                st.write(
                    f"**Modalidades:** "
                    f"{modalidades_texto}"
                )

            with coluna_acoes:

                if st.button(
                    "Editar",
                    key=(
                        f"editar_"
                        f"{transportador['id']}"
                    ),
                    use_container_width=True
                ):

                    carregar_formulario(
                        transportador
                    )

                    st.session_state[
                        "pagina"
                    ] = "Novo Transportador"

                    st.rerun()

                if transportador.get(
                    "ativo",
                    True
                ):

                    if st.button(
                        "Desativar",
                        key=(
                            f"desativar_"
                            f"{transportador['id']}"
                        ),
                        use_container_width=True
                    ):

                        historico.append(
                            snapshot_transportador(
                                transportador,
                                "ANTES DA DESATIVAÇÃO"
                            )
                        )

                        transportador[
                            "ativo"
                        ] = False

                        transportador[
                            "atualizado_em"
                        ] = agora_iso()

                        ok1, erro1 = (
                            salvar_arquivo_github(
                                "transportadores.json",
                                transportadores,
                                sha_t,
                                (
                                    "Desativar transportador "
                                    f"{transportador['nome']}"
                                )
                            )
                        )

                        if ok1:

                            ok2, erro2 = (
                                salvar_arquivo_github(
                                    "historico.json",
                                    historico,
                                    sha_h,
                                    (
                                        "Registrar desativação - "
                                        f"{transportador['nome']}"
                                    )
                                )
                            )

                            if not ok2:

                                st.warning(
                                    "Transportador desativado, "
                                    "mas o histórico não pôde "
                                    "ser atualizado: "
                                    f"{erro2}"
                                )

                            st.success(
                                "Transportador desativado."
                            )

                            st.rerun()

                        else:

                            st.error(
                                erro1
                            )

                else:

                    if st.button(
                        "Reativar",
                        key=(
                            f"reativar_"
                            f"{transportador['id']}"
                        ),
                        use_container_width=True
                    ):

                        historico.append(
                            snapshot_transportador(
                                transportador,
                                "ANTES DA REATIVAÇÃO"
                            )
                        )

                        transportador[
                            "ativo"
                        ] = True

                        transportador[
                            "atualizado_em"
                        ] = agora_iso()

                        ok1, erro1 = (
                            salvar_arquivo_github(
                                "transportadores.json",
                                transportadores,
                                sha_t,
                                (
                                    "Reativar transportador "
                                    f"{transportador['nome']}"
                                )
                            )
                        )

                        if ok1:

                            ok2, erro2 = (
                                salvar_arquivo_github(
                                    "historico.json",
                                    historico,
                                    sha_h,
                                    (
                                        "Registrar reativação - "
                                        f"{transportador['nome']}"
                                    )
                                )
                            )

                            if not ok2:

                                st.warning(
                                    "Transportador reativado, "
                                    "mas o histórico não pôde "
                                    "ser atualizado: "
                                    f"{erro2}"
                                )

                            st.success(
                                "Transportador reativado."
                            )

                            st.rerun()

                        else:

                            st.error(
                                erro1
                            )


# ==========================================================
# TELA DE RELATÓRIO
# ==========================================================

def tela_relatorio(
    transportadores,
    relatorios,
    sha_r
):

    st.title(
        "Gerar Relatório"
    )

    data_padrao = st.session_state.get(
        "data_relatorio",
        date.today()
    )

    data_escolhida = st.date_input(
        "Data de atualização",
        value=data_padrao,
        format="DD/MM/YYYY"
    )

    data_formatada = (
        data_escolhida.strftime(
            "%d/%m/%Y"
        )
    )

    ativos = [
        t
        for t in transportadores
        if t.get(
            "ativo",
            True
        )
    ]

    st.caption(
        f"Serão considerados "
        f"{len(ativos)} "
        f"transportador(es) ativo(s)."
    )

    if st.button(
        "Gerar relatório",
        type="primary",
        use_container_width=True
    ):

        texto = gerar_relatorio(
            transportadores,
            data_formatada
        )

        registro = {
            "id": str(uuid.uuid4()),
            "gerado_em": agora_iso(),
            "data_atualizacao": data_formatada,
            "texto": texto
        }

        relatorios.insert(
            0,
            registro
        )

        ok, erro = (
            salvar_arquivo_github(
                "relatorios.json",
                relatorios,
                sha_r,
                (
                    "Salvar relatório de "
                    f"{data_formatada}"
                )
            )
        )

        if ok:

            st.session_state[
                "relatorio_atual"
            ] = texto

            st.session_state[
                "relatorio_registro"
            ] = registro

            st.success(
                "Relatório gerado e salvo "
                "no histórico."
            )

        else:

            st.error(
                erro
            )

    texto = st.session_state.get(
        "relatorio_atual",
        ""
    )

    if texto:

        st.divider()

        st.subheader(
            "Relatório"
        )

        st.text_area(
            "Conteúdo completo",
            value=texto,
            height=600,
            key="area_relatorio"
        )

        copiar_texto_componente(
            texto,
            "relatorio_atual"
        )

        coluna1, coluna2 = st.columns(2)

        with coluna1:

            st.download_button(
                "Baixar TXT",
                data=texto.encode(
                    "utf-8"
                ),
                file_name=(
                    "relatorio_transportadores_"
                    f"{data_formatada.replace('/', '-')}.txt"
                ),
                mime="text/plain",
                use_container_width=True
            )

        with coluna2:

            documento = criar_docx(
                texto
            )

            st.download_button(
                "Baixar Word",
                data=documento,
                file_name=(
                    "relatorio_transportadores_"
                    f"{data_formatada.replace('/', '-')}.docx"
                ),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                use_container_width=True
            )


# ==========================================================
# RELATÓRIOS ANTERIORES
# ==========================================================

def tela_relatorios_anteriores(
    relatorios
):

    st.title(
        "Relatórios Anteriores"
    )

    if not relatorios:

        st.info(
            "Nenhum relatório foi gerado ainda."
        )

        return

    for indice, relatorio in enumerate(
        relatorios
    ):

        data_atualizacao = relatorio.get(
            "data_atualizacao",
            ""
        )

        gerado_em = relatorio.get(
            "gerado_em",
            ""
        )

        titulo = (
            f"Relatório de {data_atualizacao}"
            f" — gerado em {gerado_em}"
        )

        with st.expander(
            titulo
        ):

            texto = relatorio.get(
                "texto",
                ""
            )

            st.text_area(
                "Conteúdo",
                value=texto,
                height=400,
                key=(
                    f"relatorio_antigo_"
                    f"{relatorio.get('id', indice)}"
                )
            )

            copiar_texto_componente(
                texto,
                f"relatorio_antigo_{indice}"
            )

            coluna1, coluna2 = st.columns(2)

            with coluna1:

                st.download_button(
                    "Baixar TXT",
                    data=texto.encode(
                        "utf-8"
                    ),
                    file_name=(
                        "relatorio_transportadores_"
                        f"{str(data_atualizacao).replace('/', '-')}.txt"
                    ),
                    mime="text/plain",
                    key=(
                        f"download_txt_"
                        f"{relatorio.get('id', indice)}"
                    ),
                    use_container_width=True
                )

            with coluna2:

                documento = criar_docx(
                    texto
                )

                st.download_button(
                    "Baixar Word",
                    data=documento,
                    file_name=(
                        "relatorio_transportadores_"
                        f"{str(data_atualizacao).replace('/', '-')}.docx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    key=(
                        f"download_docx_"
                        f"{relatorio.get('id', indice)}"
                    ),
                    use_container_width=True
                )


# ==========================================================
# TELA INICIAL
# ==========================================================

def tela_inicio(
    transportadores,
    relatorios
):

    st.title(
        "Transportadores Licenciados e Credenciados"
    )

    st.caption(
        "Cadastro, gerenciamento e geração "
        "da relação por modalidade."
    )

    ativos = sum(
        1
        for t in transportadores
        if t.get(
            "ativo",
            True
        )
    )

    inativos = (
        len(transportadores)
        - ativos
    )

    modalidades_ativas = sum(
        len(
            set(
                t.get(
                    "modalidades",
                    []
                )
            )
        )
        for t in transportadores
        if t.get(
            "ativo",
            True
        )
    )

    coluna1, coluna2, coluna3, coluna4 = (
        st.columns(4)
    )

    coluna1.metric(
        "Transportadores ativos",
        ativos
    )

    coluna2.metric(
        "Transportadores inativos",
        inativos
    )

    coluna3.metric(
        "Modalidades associadas",
        modalidades_ativas
    )

    ultimo_relatorio = (
        relatorios[0].get(
            "data_atualizacao",
            "Nenhum"
        )
        if relatorios
        else "Nenhum"
    )

    coluna4.metric(
        "Último relatório",
        ultimo_relatorio
    )

    st.divider()

    st.info(
        "Os cadastros são mantidos por CNPJ, "
        "permitindo associar várias modalidades "
        "à mesma empresa. Os relatórios já gerados "
        "permanecem preservados mesmo após "
        "futuras edições."
    )


# ==========================================================
# FUNÇÃO PRINCIPAL
# ==========================================================

def main():

    token, repo, branch, data_dir = (
        github_config()
    )

    if not token or not repo:

        st.error(
            "O aplicativo ainda não está configurado."
        )

        st.write(
            "Adicione nos Secrets do Streamlit:"
        )

        st.code(
            'GITHUB_TOKEN = "seu_token"\n'
            'GITHUB_REPOSITORY = '
            '"ellenm0/Trabalho-Produ-o-Avan-ada"'
        )

        st.stop()

    # Verifica o acesso ao repositório
    github_ok, github_mensagem = (
        verificar_github()
    )

    if not github_ok:

        st.error(
            "Não foi possível acessar o "
            "repositório do GitHub."
        )

        st.warning(
            github_mensagem
        )

        st.info(
            "Verifique os Secrets do Streamlit "
            "e as permissões do GITHUB_TOKEN."
        )

        st.stop()

    (
        transportadores,
        historico,
        relatorios,
        sha_t,
        sha_h,
        sha_r
    ) = carregar_dados()

    garantir_dados_no_github(
        transportadores,
        historico,
        relatorios,
        sha_t,
        sha_h,
        sha_r
    )

    if "pagina" not in st.session_state:

        st.session_state[
            "pagina"
        ] = "Início"

    if "editando_id" not in st.session_state:

        st.session_state[
            "editando_id"
        ] = None

    st.sidebar.title(
        "Menu"
    )

    opcoes = [
        "Início",
        "Transportadores",
        "Novo Transportador",
        "Gerar Relatório",
        "Relatórios Anteriores"
    ]

    pagina_atual = st.sidebar.radio(
        "Navegação",
        opcoes,
        index=opcoes.index(
            st.session_state[
                "pagina"
            ]
        )
    )

    st.session_state[
        "pagina"
    ] = pagina_atual

    if pagina_atual == "Início":

        tela_inicio(
            transportadores,
            relatorios
        )

    elif pagina_atual == "Transportadores":

        tela_transportadores(
            transportadores,
            historico,
            sha_t,
            sha_h
        )

    elif pagina_atual == "Novo Transportador":

        tela_formulario(
            transportadores,
            historico,
            sha_t,
            sha_h
        )

    elif pagina_atual == "Gerar Relatório":

        tela_relatorio(
            transportadores,
            relatorios,
            sha_r
        )

    elif pagina_atual == "Relatórios Anteriores":

        tela_relatorios_anteriores(
            relatorios
        )


if __name__ == "__main__":
    main()
