import zipfile
from io import BytesIO
import re
import unicodedata
import time

import streamlit as st
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# NORMALIZAÇÃO DO TEXTO
# ============================================================

def normalizar_texto(texto: str) -> str:
    """
    Normaliza o texto:
    - maiúsculas
    - remove acentos
    - remove quebras de linha
    - remove espaços duplicados
    """

    texto = texto.upper()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICAÇÃO DO TIPO DE COMPROVANTE
# ============================================================

def identificar_tipo_comprovante(texto: str):
    """
    Identifica o tipo do comprovante.

    Tipos aceitos:
    1. COMPROVANTE PIX
    2. COMPROVANTE DE TRANSFERENCIA
    3. COMPROVANTE DE TRANSACAO BANCARIA
    """

    texto = normalizar_texto(texto)

    # --------------------------------------------------------
    # COMPROVANTE PIX
    # --------------------------------------------------------

    if re.search(
        r"COMPROVANTE\s+PIX",
        texto
    ):
        return "PIX"

    # --------------------------------------------------------
    # COMPROVANTE DE TRANSFERÊNCIA
    # --------------------------------------------------------

    if re.search(
        r"COMPROVANTE\s+(DE\s+)?TRANSFERENCIA",
        texto
    ):
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # COMPROVANTE DE TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    if re.search(
        r"COMPROVANTE\s+DE\s+TRANSACAO\s+BANCARIA",
        texto
    ):
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# VERIFICA PÁGINA EM BRANCO
# ============================================================

def is_pagina_em_branco(pagina):
    texto = pagina.extract_text() or ""

    try:
        tem_imagens = len(pagina.images) > 0
    except Exception:
        tem_imagens = False

    return (
        not texto.strip()
        and not tem_imagens
    )


# ============================================================
# SEPARAÇÃO DOS COMPROVANTES
# ============================================================

def separar_comprovantes(
    leitor,
    progresso,
    status
):
    comprovantes = []

    comprovante_atual = []
    tipo_atual = None
    pagina_inicio = None

    paginas_brancas = 0
    paginas_sem_comprovante = []

    total_paginas = len(leitor.pages)

    # ========================================================
    # ANALISA CADA PÁGINA
    # ========================================================

    for indice, pagina in enumerate(leitor.pages):

        numero_pagina = indice + 1

        # ----------------------------------------------------
        # PROGRESSO
        # ----------------------------------------------------

        progresso.progress(
            numero_pagina / total_paginas
        )

        status.text(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )

        # ----------------------------------------------------
        # EXTRAI TEXTO
        # ----------------------------------------------------

        texto = pagina.extract_text() or ""

        # ----------------------------------------------------
        # IDENTIFICA TIPO
        # ----------------------------------------------------

        tipo = identificar_tipo_comprovante(texto)

        # ====================================================
        # NOVO COMPROVANTE
        # ====================================================

        if tipo is not None:

            # -----------------------------------------------
            # Salva comprovante anterior
            # -----------------------------------------------

            if comprovante_atual:

                comprovantes.append(
                    {
                        "tipo": tipo_atual,
                        "paginas": comprovante_atual,
                        "pagina_inicio": pagina_inicio,
                        "pagina_fim": numero_pagina - 1
                    }
                )

            # -----------------------------------------------
            # Inicia novo comprovante
            # -----------------------------------------------

            comprovante_atual = [pagina]
            tipo_atual = tipo
            pagina_inicio = numero_pagina

            continue

        # ====================================================
        # PÁGINA EM BRANCO
        # ====================================================

        if is_pagina_em_branco(pagina):

            paginas_brancas += 1

            continue

        # ====================================================
        # CONTINUAÇÃO DO COMPROVANTE
        # ====================================================

        if comprovante_atual:

            comprovante_atual.append(pagina)

        else:

            paginas_sem_comprovante.append(
                numero_pagina
            )

    # ========================================================
    # SALVA O ÚLTIMO COMPROVANTE
    # ========================================================

    if comprovante_atual:

        comprovantes.append(
            {
                "tipo": tipo_atual,
                "paginas": comprovante_atual,
                "pagina_inicio": pagina_inicio,
                "pagina_fim": total_paginas
            }
        )

    return (
        comprovantes,
        paginas_brancas,
        paginas_sem_comprovante
    )


# ============================================================
# TELA
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.write(
    """
    Selecione um único PDF contendo vários comprovantes.

    O sistema identifica automaticamente:

    🔵 **COMPROVANTE PIX**

    🟢 **COMPROVANTE DE TRANSFERÊNCIA**

    🟣 **COMPROVANTE DE TRANSAÇÃO BANCÁRIA**

    Cada comprovante pode possuir uma ou várias páginas.
    """
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_pdf = st.file_uploader(
    "Selecione o arquivo PDF",
    type=["pdf"]
)


# ============================================================
# LIMPA RESULTADOS
# ============================================================

if arquivo_pdf is None:

    st.session_state.pop(
        "zip_comprovantes",
        None
    )

    st.session_state.pop(
        "quantidade",
        None
    )

    st.session_state.pop(
        "pix",
        None
    )

    st.session_state.pop(
        "transferencias",
        None
    )

    st.session_state.pop(
        "transacoes",
        None
    )

    st.session_state.pop(
        "ignoradas",
        None
    )

    st.session_state.pop(
        "detalhes",
        None
    )


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo_pdf is not None:

    try:

        leitor = PdfReader(
            arquivo_pdf
        )

        total_paginas = len(
            leitor.pages
        )

        st.success(
            f"✅ Arquivo selecionado: "
            f"{arquivo_pdf.name}"
        )

        st.info(
            f"📄 O arquivo possui "
            f"**{total_paginas} páginas**."
        )

        # ====================================================
        # BOTÃO
        # ====================================================

        if st.button(
            "🔄 Separar Comprovantes",
            type="primary",
            use_container_width=True
        ):

            inicio = time.time()

            st.divider()

            status = st.empty()

            progresso = st.progress(0)

            # =================================================
            # ANALISA
            # =================================================

            (
                comprovantes,
                paginas_brancas,
                paginas_sem_comprovante
            ) = separar_comprovantes(
                leitor,
                progresso,
                status
            )

            # =================================================
            # NENHUM COMPROVANTE
            # =================================================

            if not comprovantes:

                status.error(
                    "❌ Nenhum comprovante encontrado."
                )

                st.warning(
                    """
                    Nenhum dos tipos de comprovante
                    foi identificado.
                    """
                )

            else:

                # =================================================
                # CRIA ZIP
                # =================================================

                status.text(
                    "📦 Gerando arquivos..."
                )

                zip_buffer = BytesIO()

                quantidade_pix = 0
                quantidade_transferencia = 0
                quantidade_transacao = 0

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    for numero, comprovante in enumerate(
                        comprovantes,
                        start=1
                    ):

                        tipo = comprovante["tipo"]

                        paginas = comprovante["paginas"]

                        # -----------------------------------------
                        # CONTADORES
                        # -----------------------------------------

                        if tipo == "PIX":

                            quantidade_pix += 1

                            prefixo = "PIX"

                        elif tipo == "TRANSFERENCIA":

                            quantidade_transferencia += 1

                            prefixo = "TRANSFERENCIA"

                        elif tipo == "TRANSACAO_BANCARIA":

                            quantidade_transacao += 1

                            prefixo = "TRANSACAO_BANCARIA"

                        else:

                            prefixo = "OUTRO"

                        # -----------------------------------------
                        # CRIA PDF
                        # -----------------------------------------

                        escritor = PdfWriter()

                        for pagina in paginas:

                            escritor.add_page(
                                pagina
                            )

                        pdf_buffer = BytesIO()

                        escritor.write(
                            pdf_buffer
                        )

                        # -----------------------------------------
                        # NOME
                        # -----------------------------------------

                        nome = (
                            f"comprovante_"
                            f"{prefixo}_"
                            f"{numero:03d}.pdf"
                        )

                        # -----------------------------------------
                        # ZIP
                        # -----------------------------------------

                        zip_file.writestr(
                            nome,
                            pdf_buffer.getvalue()
                        )

                # =================================================
                # SALVA RESULTADOS
                # =================================================

                st.session_state[
                    "zip_comprovantes"
                ] = zip_buffer.getvalue()

                st.session_state[
                    "quantidade"
                ] = len(comprovantes)

                st.session_state[
                    "pix"
                ] = quantidade_pix

                st.session_state[
                    "transferencias"
                ] = quantidade_transferencia

                st.session_state[
                    "transacoes"
                ] = quantidade_transacao

                st.session_state[
                    "ignoradas"
                ] = paginas_brancas

                st.session_state[
                    "detalhes"
                ] = comprovantes

                # =================================================
                # TEMPO
                # =================================================

                tempo = time.time() - inicio

                progresso.progress(
                    1.0
                )

                status.success(
                    "✅ Processamento concluído!"
                )

                # =================================================
                # RESULTADO
                # =================================================

                st.divider()

                st.subheader(
                    "📊 Resultado"
                )

                col1, col2, col3, col4 = st.columns(4)

                with col1:

                    st.metric(
                        "Total",
                        len(comprovantes)
                    )

                with col2:

                    st.metric(
                        "PIX",
                        quantidade_pix
                    )

                with col3:

                    st.metric(
                        "Transferências",
                        quantidade_transferencia
                    )

                with col4:

                    st.metric(
                        "Transações bancárias",
                        quantidade_transacao
                    )

                st.info(
                    f"⏱️ Tempo de processamento: "
                    f"**{tempo:.1f} segundos**"
                )

                # =================================================
                # PÁGINAS EM BRANCO
                # =================================================

                if paginas_brancas > 0:

                    st.warning(
                        f"⚠️ {paginas_brancas} "
                        f"página(s) em branco foram ignoradas."
                    )

                # =================================================
                # PÁGINAS SEM COMPROVANTE
                # =================================================

                if paginas_sem_comprovante:

                    st.warning(
                        f"⚠️ {len(paginas_sem_comprovante)} "
                        f"página(s) não identificadas como "
                        f"parte de um comprovante."
                    )

                # =================================================
                # TABELA
                # =================================================

                st.divider()

                st.subheader(
                    "🔎 Comprovantes identificados"
                )

                dados = []

                for numero, comprovante in enumerate(
                    comprovantes,
                    start=1
                ):

                    dados.append(
                        {
                            "Nº": numero,
                            "Tipo": comprovante["tipo"],
                            "Página inicial": (
                                comprovante["pagina_inicio"]
                            ),
                            "Página final": (
                                comprovante["pagina_fim"]
                            ),
                            "Quantidade de páginas": (
                                len(comprovante["paginas"])
                            )
                        }
                    )

                st.dataframe(
                    dados,
                    use_container_width=True,
                    hide_index=True
                )

    except Exception as erro:

        st.error(
            f"❌ Erro ao processar o PDF: {erro}"
        )


# ============================================================
# DOWNLOAD
# ============================================================

if (
    arquivo_pdf is not None
    and "zip_comprovantes" in st.session_state
):

    st.divider()

    st.subheader(
        "📦 Arquivos prontos"
    )

    quantidade = st.session_state[
        "quantidade"
    ]

    pix = st.session_state[
        "pix"
    ]

    transferencias = st.session_state[
        "transferencias"
    ]

    transacoes = st.session_state[
        "transacoes"
    ]

    st.success(
        f"✅ {quantidade} comprovante(s) "
        f"foram separados."
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.write(
            f"🔵 PIX: **{pix}**"
        )

    with col2:

        st.write(
            f"🟢 Transferências: "
            f"**{transferencias}**"
        )

    with col3:

        st.write(
            f"🟣 Transações bancárias: "
            f"**{transacoes}**"
        )

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state[
            "zip_comprovantes"
        ],
        file_name="comprovantes_separados.zip",
        mime="application/zip",
        use_container_width=True
    )
