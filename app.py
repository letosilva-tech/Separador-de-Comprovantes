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
    Identifica o tipo de comprovante.

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
            texto,
        ):
            return "TRANSFERENCIA"

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
            texto,
        ):
            return "TRANSACAO_BANCARIA"

    return None


def formatar_tamanho(tamanho):
    """
    Converte bytes para uma unidade amigável.
    """

    if tamanho < 1024:

        return f"{tamanho} B"

    if tamanho < 1024 * 1024:

        return (
            f"{tamanho / 1024:.2f} KB"
        )

    return (
        f"{tamanho / (1024 * 1024):.2f} MB"
    )


def nome_seguro(nome):
    """
    Remove caracteres especiais do nome.
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

    return (
        nome.strip("._")
        or "arquivo"
    )


def salvar_writer(
    writer,
    caminho,
):
    """
    Salva o PdfWriter no caminho.
    """

    with open(
        caminho,
        "wb",
    ) as arquivo:

        writer.write(
            arquivo
        )


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
    # ABRIR PDF
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
    # Primeiro classificamos.
    # Somente depois criamos os PDFs.
    # ========================================================

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    tipos_paginas = {}

    textos_paginas = {}

    # ========================================================
    # CONTADORES
    # ========================================================

    quantidade_pix = 0

    quantidade_transferencia = 0

    quantidade_transacao = 0

    diagnostico = []

    # ========================================================
    # ANALISAR TODAS AS PÁGINAS
    # ========================================================

    for indice in range(
        total_paginas
    ):

        numero_pagina = (
            indice + 1
        )

        status.info(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )

        progress_bar.progress(
            numero_pagina
            / total_paginas
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

        # Guarda o texto para diagnóstico
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
    # VALIDAÇÃO DA CLASSIFICAÇÃO
    # ========================================================

    total_classificado = (
        len(paginas_comprovantes)
        +
        len(paginas_sem_comprovantes)
    )

    if total_classificado != total_paginas:

        raise ValueError(
            "Erro na classificação.\n\n"
            f"PDF original: "
            f"{total_paginas} páginas\n"
            f"Classificadas: "
            f"{total_classificado} páginas"
        )

    # ========================================================
    # VERIFICA DUPLICIDADE
    # ========================================================

    conjunto_comprovantes = set(
        paginas_comprovantes
    )

    conjunto_sem_comprovantes =
