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
# CONFIGURAÇÕES
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide",
)

LIMITE_ZIP = 10 * 1024 * 1024
LIMITE_SEGURANCA = 9_500_000


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """
    Remove acentos, converte para maiúsculas
    e mantém somente letras e números.
    """

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto,
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
        texto,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def identificar_comprovante(texto):
    """
    Identifica o tipo de comprovante através
    do texto da página.

    Retornos:

        PIX
        TRANSFERENCIA
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
        r"\bCOMPROVANTE\s+(?:DE\s+)?PIX\b",
        r"\bCOMPROVANTE\s+PIX\b",
        r"\bPIX\s+REALIZADO\b",
        r"\bPIX\s+EFETUADO\b",
        r"\bPAGAMENTO\s+PIX\b",
        r"\bTRANSFERENCIA\s+VIA\s+PIX\b",
    ]

    for padrao in padroes_pix:

        if re.search(
            padrao,
            texto,
        ):
            return "PIX"

    # ========================================================
    # TRANSFERÊNCIA
    # ========================================================

    padroes_transferencia = [
        r"\bCOMPROVANTE\s+(?:DE\s+)?TRANSFERENCIA\b",
        r"\bTRANSFERENCIA\s+REALIZADA\b",
        r"\bTRANSFERENCIA\s+EFETUADA\b",
        r"\bCOMPROVANTE\s+TED\b",
        r"\bCOMPROVANTE\s+DOC\b",
        r"\bTRANSFERENCIA\s+BANCARIA\b",
    ]

    for padrao in padroes_transferencia:

        if re.search(
            padrao,
            texto,
        ):
            return "TRANSFERENCIA"

    # ========================================================
    # TRANSAÇÃO BANCÁRIA
    # ========================================================

    padroes_transacao = [
        r"\bCOMPROVANTE\s+(?:DE\s+)?TRANSACAO\s+BANCARIA\b",
        r"\bCOMPROVANTE\s+DE\s+TRANSACAO\b",
        r"\bTRANSACAO\s+BANCARIA\b",
        r"\bTRANSACAO\s+REALIZADA\b",
        r"\bTRANSACAO\s+EFETUADA\b",
    ]

    for padrao in padroes_transacao:

        if re.search(
            padrao,
            texto,
        ):
            return "TRANSACAO_BANCARIA"

    return None


def formatar_tamanho(tamanho):
    """
    Converte bytes para uma unidade mais amigável.
    """

    if tamanho < 1024:

        return f"{tamanho} B"

    if tamanho < 1024 * 1024:

        return f"{tamanho / 1024:.2f} KB"

    return (
        f"{tamanho / (1024 * 1024):.2f} MB"
    )


def nome_seguro(nome):
    """
    Remove caracteres especiais do nome do arquivo.
    """

    nome = unicodedata.normalize(
        "NFKD",
        nome,
    )

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nome,
    )

    return nome.strip("._") or "arquivo"


def salvar_writer(writer, caminho):
    """
    Salva um PdfWriter no caminho informado.
    """

    with open(
        caminho,
        "wb",
    ) as arquivo:

        writer.write(arquivo)


# ============================================================
# PROCESSAMENTO DO PDF
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar,
    status,
):

    inicio = time.time()

    # ========================================================
    # ABRE PDF
    # ========================================================

    status.info(
        "📖 Abrindo PDF..."
    )

    reader = PdfReader(
        caminho_pdf,
        strict=False,
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
        "saida",
    )

    os.makedirs(
        pasta_saida,
        exist_ok=True,
    )

    # ========================================================
    # LISTAS DE PÁGINAS
    #
    # IMPORTANTE:
    #
    # Aqui NÃO criamos os PDFs ainda.
    #
    # Primeiro identificamos todas as páginas.
    # Depois criamos cada PDF separadamente.
    # ========================================================

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    tipos_paginas = {}

    # ========================================================
    # CONTADORES
    # ========================================================

    quantidade_pix = 0

    quantidade_transferencia = 0

    quantidade_transacao = 0

    diagnostico = []

    # ========================================================
    # ANALISA CADA PÁGINA
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
        # EXTRAÇÃO DO TEXTO
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

        # ----------------------------------------------------
        # IDENTIFICA COMPROVANTE
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        tipos_paginas[
            numero_pagina
        ] = tipo

        # ====================================================
        # É COMPROVANTE
        # ====================================================

        if tipo:

            paginas_comprovantes.append(
                indice
            )

            if tipo == "PIX":

                quantidade_pix += 1

            elif tipo == "TRANSFERENCIA":

                quantidade_transferencia += 1

            elif tipo == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1

        # ====================================================
        # NÃO É COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                indice
            )

    # ========================================================
    # VALIDAÇÃO 1
    #
    # Todas as páginas precisam estar em exatamente um grupo.
    # ========================================================

    total_classificado = (
        len(paginas_comprovantes)
        +
        len(paginas_sem_comprovantes)
    )

    if total_classificado != total_paginas:

        raise ValueError(
            "Erro na classificação das páginas.\n\n"
            f"PDF original: {total_paginas} páginas\n"
            f"Classificadas: {total_classificado} páginas"
        )

    # ========================================================
    # VALIDAÇÃO 2
    #
    # Uma página não pode estar nos dois grupos.
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
            "Erro: as seguintes páginas "
            "foram classificadas nos dois grupos: "
            f"{paginas_duplicadas_numeros}"
        )

    # ========================================================
    # CAMINHOS
    # ========================================================

    caminho_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.pdf",
    )

    caminho_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.pdf",
    )

    # ========================================================
    # CRIA COMPROVANTES.PDF
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

        salvar_writer(
            writer_comprovantes,
            caminho_comprovantes,
        )

        del writer_comprovantes

    # ========================================================
    # CRIA SEM_COMPROVANTES.PDF
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

        salvar_writer(
            writer_sem_comprovantes,
            caminho_sem_comprovantes,
        )

        del writer_sem_comprovantes

    # ========================================================
    # LIBERA MEMÓRIA
    # ========================================================

    gc.collect()

    # ========================================================
    # TAMANHO DOS PDFs
    # ========================================================

    tamanho_comprovantes = 0

    tamanho_sem_comprovantes = 0

    if os.path.exists(
        caminho_comprovantes
    ):

        tamanho_comprovantes = (
            os.path.getsize(
                caminho_comprovantes
            )
        )

    if os.path.exists(
        caminho_sem_comprovantes
    ):

        tamanho_sem_comprovantes = (
            os.path.getsize(
                caminho_sem_comprovantes
            )
        )

    # ========================================================
    # ZIP DOS COMPROVANTES
    # ========================================================

    caminho_zip_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.zip",
    )

    if os.path.exists(
        caminho_comprovantes
    ):

        with zipfile.ZipFile(
            caminho_zip_comprovantes,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1,
        ) as zip_file:

            zip_file.write(
                caminho_comprovantes,
                arcname="COMPROVANTES.pdf",
            )

    # ========================================================
    # ZIP SEM COMPROVANTES
    # ========================================================

    caminho_zip_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.zip",
    )

    if os.path.exists(
        caminho_sem_comprovantes
    ):

        with zipfile.ZipFile(
            caminho_zip_sem_comprovantes,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1,
        ) as zip_file:

            zip_file.write(
                caminho_sem_comprovantes,
                arcname="SEM_COMPROVANTES.pdf",
            )

    # ========================================================
    # TAMANHO DOS ZIPs
    # ========================================================

    tamanho_zip_comprovantes = 0

    tamanho_zip_sem_comprovantes = 0

    if os.path.exists(
        caminho_zip_comprovantes
    ):

        tamanho_zip_comprovantes = (
            os.path.getsize(
                caminho_zip_comprovantes
            )
        )

    if os.path.exists(
        caminho_zip_sem_comprovantes
    ):

        tamanho_zip_sem_comprovantes = (
            os.path.getsize(
                caminho_zip_sem_comprovantes
            )
        )

    # ========================================================
    # LIBERA READER
    # ========================================================

    del reader

    gc.collect()

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
            for indice in paginas_comprovantes
        ],

        "paginas_sem_comprovantes": [
            indice + 1
            for indice in paginas_sem_comprovantes
        ],

        "tipos_paginas":
            tipos_paginas,
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

    Cada página será enviada para **apenas um dos grupos**.

    Depois são disponibilizados os PDFs e arquivos ZIP.
    """
)

st.info(
    """
    💡 O PDF original não é alterado.

    As páginas são apenas classificadas e copiadas
    para dois novos arquivos PDF.
    """
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_enviado = st.file_uploader(
    "Selecione o PDF que deseja processar",
    type=["pdf"],
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
        use_container_width=True,
    ):

        # ----------------------------------------------------
        # PASTA TEMPORÁRIA
        # ----------------------------------------------------

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        caminho_pdf_original = os.path.join(
            pasta_trabalho,
            nome_seguro(
                arquivo_enviado.name
            ),
        )

        try:

            # =================================================
            # SALVA PDF ORIGINAL
            # =================================================

            with open(
                caminho_pdf_original,
                "wb",
            ) as arquivo:

                arquivo.write(
                    arquivo_enviado.getbuffer()
                )

            # =================================================
            # COMPONENTES DE PROGRESSO
            # =================================================

            progress_bar = st.progress(
                0
            )

            status = st.empty()

            # =================================================
            # PROCESSA PDF
            # =================================================

            resultado = processar_pdf(
                caminho_pdf_original,
                pasta_trabalho,
                progress_bar,
                status,
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

            col1, col2, col3, col4 = st.columns(
                4
            )

            col1.metric(
                "Total de páginas",
                resultado[
                    "total_paginas"
                ],
            )

            col2.metric(
                "Comprovantes",
                resultado[
                    "total_comprovantes"
                ],
            )

            col3.metric(
                "Sem comprovante",
                resultado[
                    "total_sem_comprovantes"
                ],
            )

            col4.metric(
                "Tempo",
                f"{resultado['tempo_total']:.1f}s",
            )

            # =================================================
            # CONFERÊNCIA
            # =================================================

            st.subheader(
                "🔎 Conferência da separação"
            )

            total_verificacao = (
                resultado[
                    "total_comprovantes"
                ]
                +
                resultado[
                    "total_sem_comprovantes"
                ]
            )

            if (
                total_verificacao
                ==
                resultado[
                    "total_paginas"
                ]
            ):

                st.success(
                    "✅ Todas as páginas foram "
                    "classificadas sem duplicidade."
                )

            else:

                st.error(
                    "❌ A quantidade de páginas "
                    "classificadas não corresponde "
                    "ao PDF original."
                )

            # =================================================
            # PÁGINAS
            # =================================================

            with st.expander(
                "📋 Ver páginas classificadas"
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

                    st.write(
                        "Nenhuma página identificada."
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

                    st.write(
                        "Nenhuma página identificada."
                    )

            # =================================================
            # TIPOS IDENTIFICADOS
            # =================================================

            st.subheader(
                "🔎 Tipos identificados"
            )

            c1, c2, c3 = st.columns(
                3
            )

            c1.metric(
                "🔵 PIX",
                resultado[
                    "quantidade_pix"
                ],
            )

            c2.metric(
                "🟢 Transferência",
                resultado[
                    "quantidade_transferencia"
                ],
            )

            c3.metric(
                "🟣 Transação bancária",
                resultado[
                    "quantidade_transacao"
                ],
            )

            # =================================================
            # PDF COMPROVANTES
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

                st.write(
                    f"**"
                    f"{resultado['total_comprovantes']}"
                    f" página(s)"
                    f"** — "
                    f"{formatar_tamanho("
                        resultado[
                            "tamanho_comprovantes"
                        ]
                    )}"
                )

                with open(
                    resultado[
                        "caminho_comprovantes"
                    ],
                    "rb",
                ) as arquivo:

                    st.download_button(
                        label=(
                            "⬇️ Baixar "
                            "COMPROVANTES.pdf"
                        ),
                        data=arquivo.read(),
                        file_name=(
                            "COMPROVANTES.pdf"
                        ),
                        mime="application/pdf",
                        use_container_width=True,
                        key=(
                            "download_"
                            "comprovantes_pdf"
                        ),
                    )

            # =================================================
            # PDF SEM COMPROVANTES
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

                st.write(
                    f"**"
                    f"{resultado['total_sem_comprovantes']}"
                    f" página(s)"
                    f"** — "
                    f"{formatar_tamanho("
                        resultado[
                            "tamanho_sem_comprovantes"
                        ]
                    )}"
                )

                with open(
                    resultado[
                        "caminho_sem_comprovantes"
                    ],
                    "rb",
                ) as arquivo:

                    st.download_button(
                        label=(
                            "⬇️ Baixar "
                            "SEM_COMPROVANTES.pdf"
                        ),
                        data=arquivo.read(),
                        file_name=(
                            "SEM_COMPROVANTES.pdf"
                        ),
                        mime="application/pdf",
                        use_container_width=True,
                        key=(
                            "download_"
                            "sem_comprovantes_pdf"
                        ),
                    )

            # =================================================
            # ZIP COMPROVANTES
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
                    "rb",
                ) as arquivo:

                    st.download_button(
                        label=(
                            "⬇️ Baixar "
                            "COMPROVANTES.zip"
                        ),
                        data=arquivo.read(),
                        file_name=(
                            "COMPROVANTES.zip"
                        ),
                        mime="application/zip",
                        use_container_width=True,
                        key=(
                            "download_"
                            "comprovantes_zip"
                        ),
                    )

            # =================================================
            # ZIP SEM COMPROVANTES
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
                    "rb",
                ) as arquivo:

                    st.download_button(
                        label=(
                            "⬇️ Baixar "
                            "SEM_COMPROVANTES.zip"
                        ),
                        data=arquivo.read(),
                        file_name=(
                            "SEM_COMPROVANTES.zip"
                        ),
                        mime="application/zip",
                        use_container_width=True,
                        key=(
                            "download_"
                            "sem_comprovantes_zip"
                        ),
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

                    for mensagem in resultado[
                        "diagnostico"
                    ]:

                        st.write(
                            mensagem
                        )

            # =================================================
            # AVISO — NENHUM COMPROVANTE
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
                    Isso pode acontecer quando o PDF
                    é uma imagem digitalizada ou quando
                    o texto do comprovante utiliza
                    termos diferentes dos padrões
                    configurados.
                    """
                )

            # =================================================
            # AVISO — TODAS AS PÁGINAS SÃO COMPROVANTES
            # =================================================

            if (
                resultado[
                    "total_sem_comprovantes"
                ]
                == 0
            ):

                st.info(
                    "ℹ️ Todas as páginas do PDF foram "
                    "identificadas como comprovantes."
                )

        # =====================================================
        # TRATAMENTO DE ERRO
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
                    ignore_errors=True,
                )

            except Exception:

                pass
