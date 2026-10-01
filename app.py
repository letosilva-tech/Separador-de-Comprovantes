import gc
import os
import re
import shutil
import tempfile
import time
import unicodedata
import zipfile

import streamlit as st
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """
    Remove acentos, converte para maiúsculas
    e normaliza espaços.
    """

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = texto.upper()

    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICAÇÃO DO COMPROVANTE
# ============================================================

def identificar_comprovante(texto):
    """
    Identifica se a página possui características
    de um comprovante.

    Retorna:

        PIX
        TRANSFERENCIA
        PAGAMENTO
        TRANSACAO_BANCARIA
        None
    """

    texto = normalizar_texto(texto)

    if not texto:
        return None

    # ========================================================
    # PIX
    # ========================================================

    padroes_pix = [
        r"\bCOMPROVANTE\s+DE\s+PIX\b",
        r"\bCOMPROVANTE\s+PIX\b",
        r"\bCOMPROVANTE\s+DO\s+PIX\b",
        r"\bPIX\s+REALIZADO\b",
        r"\bPIX\s+EFETUADO\b",
        r"\bPAGAMENTO\s+PIX\b",
        r"\bPIX\s+ENVIADO\b",
        r"\bPIX\s+RECEBIDO\b",
        r"\bPAGAMENTO\s+REALIZADO\s+VIA\s+PIX\b",
        r"\bTRANSFERENCIA\s+VIA\s+PIX\b",
        r"\bTRANSACAO\s+PIX\b",
    ]

    for padrao in padroes_pix:

        if re.search(
            padrao,
            texto
        ):
            return "PIX"

    # ========================================================
    # TRANSFERÊNCIA
    # ========================================================

    padroes_transferencia = [
        r"\bCOMPROVANTE\s+DE\s+TRANSFERENCIA\b",
        r"\bCOMPROVANTE\s+TRANSFERENCIA\b",
        r"\bCOMPROVANTE\s+DA\s+TRANSFERENCIA\b",
        r"\bTRANSFERENCIA\s+REALIZADA\b",
        r"\bTRANSFERENCIA\s+EFETUADA\b",
        r"\bTRANSFERENCIA\s+BANCARIA\b",
        r"\bTRANSFERENCIA\s+ELETRONICA\b",
        r"\bTRANSFERENCIA\s+CONCLUIDA\b",
        r"\bCOMPROVANTE\s+TED\b",
        r"\bCOMPROVANTE\s+DOC\b",
        r"\bTED\s+REALIZADA\b",
        r"\bTED\s+EFETUADA\b",
        r"\bDOC\s+REALIZADO\b",
        r"\bDOC\s+EFETUADO\b",
    ]

    for padrao in padroes_transferencia:

        if re.search(
            padrao,
            texto
        ):
            return "TRANSFERENCIA"

    # ========================================================
    # COMPROVANTE DE PAGAMENTO
    # ========================================================

    padroes_pagamento = [
        r"\bCOMPROVANTE\s+DE\s+PAGAMENTO\b",
        r"\bCOMPROVANTE\s+PAGAMENTO\b",
        r"\bCOMPROVANTE\s+DO\s+PAGAMENTO\b",
        r"\bCOMPROVANTE\s+DE\s+PAGAMENTO\s+BANCARIO\b",
        r"\bCOMPROVANTE\s+DE\s+PAGAMENTO\s+ONLINE\b",
        r"\bPAGAMENTO\s+REALIZADO\b",
        r"\bPAGAMENTO\s+EFETUADO\b",
        r"\bPAGAMENTO\s+CONCLUIDO\b",
        r"\bPAGAMENTO\s+CONFIRMADO\b",
    ]

    for padrao in padroes_pagamento:

        if re.search(
            padrao,
            texto
        ):
            return "PAGAMENTO"

    # ========================================================
    # TRANSAÇÃO BANCÁRIA
    # ========================================================

    padroes_transacao = [
        r"\bCOMPROVANTE\s+DE\s+TRANSACAO\s+BANCARIA\b",
        r"\bCOMPROVANTE\s+TRANSACAO\s+BANCARIA\b",
        r"\bCOMPROVANTE\s+DE\s+TRANSACAO\b",
        r"\bTRANSACAO\s+BANCARIA\b",
        r"\bTRANSACAO\s+REALIZADA\b",
        r"\bTRANSACAO\s+EFETUADA\b",
        r"\bTRANSACAO\s+CONCLUIDA\b",
    ]

    for padrao in padroes_transacao:

        if re.search(
            padrao,
            texto
        ):
            return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# FORMATAÇÃO DE TAMANHO
# ============================================================

def formatar_tamanho(tamanho):

    if tamanho < 1024:

        return f"{tamanho} B"

    if tamanho < 1024 * 1024:

        return f"{tamanho / 1024:.2f} KB"

    return f"{tamanho / (1024 * 1024):.2f} MB"


# ============================================================
# NOME SEGURO
# ============================================================

def nome_seguro(nome):

    nome = unicodedata.normalize(
        "NFKD",
        nome
    )

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nome
    )

    return (
        nome.strip("._")
        or "arquivo"
    )


# ============================================================
# SALVAR PDF
# ============================================================

def salvar_pdf(
    writer,
    caminho
):

    with open(
        caminho,
        "wb"
    ) as arquivo:

        writer.write(
            arquivo
        )


# ============================================================
# PROCESSAMENTO
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar,
    status
):

    inicio = time.time()

    # ========================================================
    # ABRIR PDF
    # ========================================================

    status.info(
        "📖 Abrindo PDF..."
    )

    reader = PdfReader(
        caminho_pdf,
        strict=False
    )

    total_paginas = len(
        reader.pages
    )

    if total_paginas == 0:

        raise ValueError(
            "O PDF não possui páginas."
        )

    # ========================================================
    # PASTA DE SAÍDA
    # ========================================================

    pasta_saida = os.path.join(
        pasta_trabalho,
        "saida"
    )

    os.makedirs(
        pasta_saida,
        exist_ok=True
    )

    # ========================================================
    # LISTAS
    # ========================================================

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    tipos_paginas = {}

    textos_paginas = {}

    diagnostico = []

    # ========================================================
    # CONTADORES
    # ========================================================

    quantidade_pix = 0

    quantidade_transferencia = 0

    quantidade_pagamento = 0

    quantidade_transacao = 0

    # ========================================================
    # ANALISAR TODAS AS PÁGINAS
    # ========================================================

    for indice in range(
        total_paginas
    ):

        numero_pagina = indice + 1

        status.info(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )

        progress_bar.progress(
            numero_pagina / total_paginas
        )

        pagina = reader.pages[
            indice
        ]

        # ----------------------------------------------------
        # EXTRAIR TEXTO
        # ----------------------------------------------------

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except Exception as erro:

            texto = ""

            diagnostico.append(
                f"Página {numero_pagina}: "
                f"erro ao extrair texto: "
                f"{erro}"
            )

        textos_paginas[
            numero_pagina
        ] = texto

        # ----------------------------------------------------
        # IDENTIFICAR
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        tipos_paginas[
            numero_pagina
        ] = tipo

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo is not None:

            paginas_comprovantes.append(
                indice
            )

            if tipo == "PIX":

                quantidade_pix += 1

            elif tipo == "TRANSFERENCIA":

                quantidade_transferencia += 1

            elif tipo == "PAGAMENTO":

                quantidade_pagamento += 1

            elif tipo == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                indice
            )

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    total_classificado = (
        len(paginas_comprovantes)
        +
        len(paginas_sem_comprovantes)
    )

    if total_classificado != total_paginas:

        raise ValueError(
            "Erro na classificação das páginas.\n\n"
            f"Total do PDF: {total_paginas}\n"
            f"Total classificado: {total_classificado}"
        )

    # ========================================================
    # VERIFICAR DUPLICIDADE
    # ========================================================

    conjunto_comprovantes = set(
        paginas_comprovantes
    )

    conjunto_sem_comprovantes = set(
        paginas_sem_comprovantes
    )

    paginas_duplicadas = (
        conjunto_comprovantes
        &
        conjunto_sem_comprovantes
    )

    if paginas_duplicadas:

        paginas_duplicadas_numeros = [
            indice + 1
            for indice in sorted(
                paginas_duplicadas
            )
        ]

        raise ValueError(
            "Erro: páginas classificadas "
            "nos dois grupos: "
            f"{paginas_duplicadas_numeros}"
        )

    # ========================================================
    # VERIFICAR SE TODAS AS PÁGINAS ESTÃO CLASSIFICADAS
    # ========================================================

    todas_as_paginas = (
        paginas_comprovantes
        +
        paginas_sem_comprovantes
    )

    if len(
        set(todas_as_paginas)
    ) != total_paginas:

        raise ValueError(
            "Erro: existem páginas duplicadas "
            "ou páginas não classificadas."
        )

    # ========================================================
    # CAMINHOS
    # ========================================================

    caminho_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.pdf"
    )

    caminho_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.pdf"
    )

    # ========================================================
    # CRIAR COMPROVANTES.PDF
    # ========================================================

    if paginas_comprovantes:

        status.info(
            "💾 Criando COMPROVANTES.pdf..."
        )

        writer_comprovantes = PdfWriter()

        for indice in paginas_comprovantes:

            writer_comprovantes.add_page(
                reader.pages[indice]
            )

        salvar_pdf(
            writer_comprovantes,
            caminho_comprovantes
        )

        del writer_comprovantes

    # ========================================================
    # CRIAR SEM_COMPROVANTES.PDF
    # ========================================================

    if paginas_sem_comprovantes:

        status.info(
            "💾 Criando SEM_COMPROVANTES.pdf..."
        )

        writer_sem_comprovantes = PdfWriter()

        for indice in paginas_sem_comprovantes:

            writer_sem_comprovantes.add_page(
                reader.pages[indice]
            )

        salvar_pdf(
            writer_sem_comprovantes,
            caminho_sem_comprovantes
        )

        del writer_sem_comprovantes

    # ========================================================
    # LIBERAR MEMÓRIA
    # ========================================================

    gc.collect()

    # ========================================================
    # TAMANHOS
    # ========================================================

    tamanho_comprovantes = 0

    tamanho_sem_comprovantes = 0

    if os.path.exists(
        caminho_comprovantes
    ):

        tamanho_comprovantes = os.path.getsize(
            caminho_comprovantes
        )

    if os.path.exists(
        caminho_sem_comprovantes
    ):

        tamanho_sem_comprovantes = os.path.getsize(
            caminho_sem_comprovantes
        )

    # ========================================================
    # ZIP COMPROVANTES
    # ========================================================

    caminho_zip_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.zip"
    )

    if os.path.exists(
        caminho_comprovantes
    ):

        with zipfile.ZipFile(
            caminho_zip_comprovantes,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        ) as zip_file:

            zip_file.write(
                caminho_comprovantes,
                arcname="COMPROVANTES.pdf"
            )

    # ========================================================
    # ZIP SEM COMPROVANTES
    # ========================================================

    caminho_zip_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.zip"
    )

    if os.path.exists(
        caminho_sem_comprovantes
    ):

        with zipfile.ZipFile(
            caminho_zip_sem_comprovantes,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        ) as zip_file:

            zip_file.write(
                caminho_sem_comprovantes,
                arcname="SEM_COMPROVANTES.pdf"
            )

    # ========================================================
    # TAMANHO DOS ZIPs
    # ========================================================

    tamanho_zip_comprovantes = 0

    tamanho_zip_sem_comprovantes = 0

    if os.path.exists(
        caminho_zip_comprovantes
    ):

        tamanho_zip_comprovantes = os.path.getsize(
            caminho_zip_comprovantes
        )

    if os.path.exists(
        caminho_zip_sem_comprovantes
    ):

        tamanho_zip_sem_comprovantes = os.path.getsize(
            caminho_zip_sem_comprovantes
        )

    # ========================================================
    # TEMPO
    # ========================================================

    tempo_total = (
        time.time() - inicio
    )

    # ========================================================
    # RETORNO
    # ========================================================

    return {

        "total_paginas":
            total_paginas,

        "total_comprovantes":
            len(paginas_comprovantes),

        "total_sem_comprovantes":
            len(paginas_sem_comprovantes),

        "quantidade_pix":
            quantidade_pix,

        "quantidade_transferencia":
            quantidade_transferencia,

        "quantidade_pagamento":
            quantidade_pagamento,

        "quantidade_transacao":
            quantidade_transacao,

        "caminho_comprovantes":
            caminho_comprovantes,

        "caminho_sem_comprovantes":
            caminho_sem_comprovantes,

        "caminho_zip_comprovantes":
            caminho_zip_comprovantes,

        "caminho_zip_sem_comprovantes":
            caminho_zip_sem_comprovantes,

        "tamanho_comprovantes":
            tamanho_comprovantes,

        "tamanho_sem_comprovantes":
            tamanho_sem_comprovantes,

        "tamanho_zip_comprovantes":
            tamanho_zip_comprovantes,

        "tamanho_zip_sem_comprovantes":
            tamanho_zip_sem_comprovantes,

        "diagnostico":
            diagnostico,

        "tempo_total":
            tempo_total,

        "paginas_comprovantes": [
            indice + 1
            for indice
            in paginas_comprovantes
        ],

        "paginas_sem_comprovantes": [
            indice + 1
            for indice
            in paginas_sem_comprovantes
        ],

        "tipos_paginas":
            tipos_paginas,

        "textos_paginas":
            textos_paginas
    }


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.write(
    """
    O sistema analisa o PDF página por página e separa:

    🔵 **COMPROVANTES**

    🟢 **PÁGINAS SEM COMPROVANTES**

    São reconhecidos comprovantes de:

    • PIX
    • Transferência
    • TED
    • DOC
    • Comprovante de Pagamento
    • Transação bancária
    """
)

st.info(
    """
    💡 O PDF original não é alterado.
    O sistema cria novos PDFs somente com as páginas
    classificadas em cada grupo.
    """
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_enviado = st.file_uploader(
    "Selecione o PDF que deseja processar",
    type=["pdf"]
)


if arquivo_enviado is not None:

    st.success(
        f"Arquivo selecionado: "
        f"**{arquivo_enviado.name}** "
        f"({formatar_tamanho(arquivo_enviado.size)})"
    )

    # ========================================================
    # BOTÃO PROCESSAR
    # ========================================================

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        caminho_pdf_original = os.path.join(
            pasta_trabalho,
            nome_seguro(
                arquivo_enviado.name
            )
        )

        try:

            # =================================================
            # SALVAR PDF ORIGINAL
            # =================================================

            with open(
                caminho_pdf_original,
                "wb"
            ) as arquivo:

                arquivo.write(
                    arquivo_enviado.getbuffer()
                )

            # =================================================
            # PROGRESSO
            # =================================================

            progress_bar = st.progress(
                0
            )

            status = st.empty()

            # =================================================
            # PROCESSAR
            # =================================================

            resultado = processar_pdf(
                caminho_pdf_original,
                pasta_trabalho,
                progress_bar,
                status
            )

            progress_bar.progress(
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

            col1.metric(
                "Total de páginas",
                resultado[
                    "total_paginas"
                ]
            )

            col2.metric(
                "Comprovantes",
                resultado[
                    "total_comprovantes"
                ]
            )

            col3.metric(
                "Sem comprovante",
                resultado[
                    "total_sem_comprovantes"
                ]
            )

            col4.metric(
                "Tempo",
                f"{resultado['tempo_total']:.1f}s"
            )

            # =================================================
            # CONFERÊNCIA
            # =================================================

            st.subheader(
                "🔐 Conferência"
            )

            total_classificado = (
                resultado[
                    "total_comprovantes"
                ]
                +
                resultado[
                    "total_sem_comprovantes"
                ]
            )

            if (
                total_classificado
                ==
                resultado[
                    "total_paginas"
                ]
            ):

                st.success(
                    "✅ Todas as páginas foram "
                    "classificadas corretamente."
                )

            else:

                st.error(
                    "❌ Existe diferença na "
                    "quantidade de páginas."
                )

            # =================================================
            # CONFERIR PÁGINAS
            # =================================================

            with st.expander(
                "🔎 Conferir páginas separadas"
            ):

                st.write(
                    "### 🔵 COMPROVANTES.pdf"
                )

                if resultado[
                    "paginas_comprovantes"
                ]:

                    st.write(
                        resultado[
                            "paginas_comprovantes"
                        ]
                    )

                else:

                    st.warning(
                        "Nenhum comprovante foi identificado."
                    )

                st.write(
                    "### 🟢 SEM_COMPROVANTES.pdf"
                )

                if resultado[
                    "paginas_sem_comprovantes"
                ]:

                    st.write(
                        resultado[
                            "paginas_sem_comprovantes"
                        ]
                    )

                else:

                    st.info(
                        "Nenhuma página ficou "
                        "neste grupo."
                    )

            # =================================================
            # TIPOS IDENTIFICADOS
            # =================================================

            st.subheader(
                "🔎 Tipos de comprovantes identificados"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "🔵 PIX",
                resultado[
                    "quantidade_pix"
                ]
            )

            c2.metric(
                "🟢 Transferência",
                resultado[
                    "quantidade_transferencia"
                ]
            )

            c3.metric(
                "🟠 Pagamento",
                resultado[
                    "quantidade_pagamento"
                ]
            )

            c4.metric(
                "🟣 Transação bancária",
                resultado[
                    "quantidade_transacao"
                ]
            )

            # =================================================
            # DOWNLOAD COMPROVANTES
            # =================================================

            if os.path.exists(
                resultado[
                    "caminho_comprovantes"
                ]
            ):

                st.divider()

                st.subheader(
                    "📄 PDF — Comprovantes"
                )

                tamanho_comprovantes = (
                    formatar_tamanho(
                        resultado[
                            "tamanho_comprovantes"
                        ]
                    )
                )

                st.write(
                    f"**"
                    f"{resultado['total_comprovantes']}"
                    f" página(s)** — "
                    f"{tamanho_comprovantes}"
                )

                with open(
                    resultado[
                        "caminho_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    dados_comprovantes = (
                        arquivo.read()
                    )

                st.download_button(
                    label=(
                        "⬇️ Baixar "
                        "COMPROVANTES.pdf"
                    ),
                    data=dados_comprovantes,
                    file_name=(
                        "COMPROVANTES.pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                    key=(
                        "download_comprovantes_pdf"
                    )
                )

            # =================================================
            # DOWNLOAD SEM COMPROVANTES
            # =================================================

            if os.path.exists(
                resultado[
                    "caminho_sem_comprovantes"
                ]
            ):

                st.divider()

                st.subheader(
                    "📄 PDF — Sem comprovantes"
                )

                tamanho_sem_comprovantes = (
                    formatar_tamanho(
                        resultado[
                            "tamanho_sem_comprovantes"
                        ]
                    )
                )

                st.write(
                    f"**"
                    f"{resultado['total_sem_comprovantes']}"
                    f" página(s)** — "
                    f"{tamanho_sem_comprovantes}"
                )

                with open(
                    resultado[
                        "caminho_sem_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    dados_sem_comprovantes = (
                        arquivo.read()
                    )

                st.download_button(
                    label=(
                        "⬇️ Baixar "
                        "SEM_COMPROVANTES.pdf"
                    ),
                    data=dados_sem_comprovantes,
                    file_name=(
                        "SEM_COMPROVANTES.pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                    key=(
                        "download_sem_comprovantes_pdf"
                    )
                )

            # =================================================
            # DOWNLOAD ZIP COMPROVANTES
            # =================================================

            if os.path.exists(
                resultado[
                    "caminho_zip_comprovantes"
                ]
            ):

                st.divider()

                st.subheader(
                    "📦 ZIP — Comprovantes"
                )

                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_zip_comprovantes"
                        ]
                    )
                )

                with open(
                    resultado[
                        "caminho_zip_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    dados_zip_comprovantes = (
                        arquivo.read()
                    )

                st.download_button(
                    label=(
                        "⬇️ Baixar "
                        "COMPROVANTES.zip"
                    ),
                    data=dados_zip_comprovantes,
                    file_name=(
                        "COMPROVANTES.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True,
                    key=(
                        "download_comprovantes_zip"
                    )
                )

            # =================================================
            # DOWNLOAD ZIP SEM COMPROVANTES
            # =================================================

            if os.path.exists(
                resultado[
                    "caminho_zip_sem_comprovantes"
                ]
            ):

                st.divider()

                st.subheader(
                    "📦 ZIP — Sem comprovantes"
                )

                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_zip_sem_comprovantes"
                        ]
                    )
                )

                with open(
                    resultado[
                        "caminho_zip_sem_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    dados_zip_sem_comprovantes = (
                        arquivo.read()
                    )

                st.download_button(
                    label=(
                        "⬇️ Baixar "
                        "SEM_COMPROVANTES.zip"
                    ),
                    data=dados_zip_sem_comprovantes,
                    file_name=(
                        "SEM_COMPROVANTES.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True,
                    key=(
                        "download_sem_comprovantes_zip"
                    )
                )

            # =================================================
            # DIAGNÓSTICO
            # =================================================

            if resultado[
                "diagnostico"
            ]:

                with st.expander(
                    "⚠️ Diagnóstico"
                ):

                    for mensagem in (
                        resultado[
                            "diagnostico"
                        ]
                    ):

                        st.write(
                            mensagem
                        )

            # =================================================
            # NENHUM COMPROVANTE
            # =================================================

            if (
                resultado[
                    "total_comprovantes"
                ]
                == 0
            ):

                st.warning(
                    "⚠️ Nenhum comprovante foi "
                    "identificado."
                )

                st.info(
                    """
                    Se o PDF possui comprovantes, mas
                    nenhum foi identificado, provavelmente
                    o PDF é escaneado/imagem ou utiliza
                    textos diferentes dos padrões configurados.
                    """
                )

            # =================================================
            # TODAS AS PÁGINAS SÃO COMPROVANTES
            # =================================================

            if (
                resultado[
                    "total_sem_comprovantes"
                ]
                == 0
            ):

                st.info(
                    "ℹ️ Todas as páginas foram "
                    "identificadas como comprovantes."
                )

        # =====================================================
        # ERRO
        # =====================================================

        except Exception as erro:

            st.error(
                "❌ Ocorreu um erro durante "
                "o processamento."
            )

            st.exception(
                erro
            )

        # =====================================================
        # LIMPEZA
        # =====================================================

        finally:

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except Exception:

                pass
