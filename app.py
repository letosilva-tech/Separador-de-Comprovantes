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
# CONFIGURAÇÕES
# ============================================================

TAMANHO_MAXIMO_MB = 10

TAMANHO_MAXIMO_BYTES = (
    TAMANHO_MAXIMO_MB * 1024 * 1024
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
# CRIAR PDF TEMPORÁRIO PARA MEDIR TAMANHO
# ============================================================

def medir_writer(
    writer,
    pasta_temporaria,
    nome_temporario
):

    caminho_temporario = os.path.join(
        pasta_temporaria,
        nome_temporario
    )

    salvar_pdf(
        writer,
        caminho_temporario
    )

    tamanho = os.path.getsize(
        caminho_temporario
    )

    try:

        os.remove(
            caminho_temporario
        )

    except Exception:

        pass

    return tamanho


# ============================================================
# DIVIDIR PDF EM ARQUIVOS DE ATÉ 10 MB
# ============================================================

def dividir_pdf_por_tamanho(
    reader,
    indices_paginas,
    pasta_saida,
    nome_base,
    progress_bar=None,
    progresso_inicial=0,
    progresso_final=1
):
    """
    Cria PDFs de até 10 MB.

    A divisão ocorre sempre entre páginas.
    Nenhuma página é cortada.

    Retorna uma lista de dicionários contendo:

        caminho
        tamanho
        paginas
        numero
    """

    arquivos_gerados = []

    if not indices_paginas:

        return arquivos_gerados

    writer_atual = PdfWriter()

    numero_arquivo = 1

    total_paginas = len(
        indices_paginas
    )

    pagina_processada = 0

    paginas_writer_atual = []

    for indice in indices_paginas:

        pagina_processada += 1

        # ----------------------------------------------------
        # Criar writer de teste
        # ----------------------------------------------------

        writer_teste = PdfWriter()

        for pagina_existente in paginas_writer_atual:

            writer_teste.add_page(
                pagina_existente
            )

        pagina_atual = reader.pages[
            indice
        ]

        writer_teste.add_page(
            pagina_atual
        )

        # ----------------------------------------------------
        # Medir tamanho
        # ----------------------------------------------------

        tamanho_teste = medir_writer(
            writer_teste,
            pasta_saida,
            f".medicao_{nome_base}_{numero_arquivo}.pdf"
        )

        # ----------------------------------------------------
        # Se passou de 10 MB
        # ----------------------------------------------------

        if (
            tamanho_teste
            >
            TAMANHO_MAXIMO_BYTES
            and
            len(paginas_writer_atual) > 0
        ):

            # -----------------------------------------------
            # Salvar lote anterior
            # -----------------------------------------------

            caminho_final = os.path.join(
                pasta_saida,
                f"{nome_base}_{numero_arquivo:02d}.pdf"
            )

            salvar_pdf(
                writer_atual,
                caminho_final
            )

            tamanho_final = os.path.getsize(
                caminho_final
            )

            paginas_numeros = [
                pagina["numero"]
                for pagina
                in paginas_writer_atual
            ]

            arquivos_gerados.append(
                {
                    "caminho":
                        caminho_final,

                    "tamanho":
                        tamanho_final,

                    "paginas":
                        paginas_numeros,

                    "numero":
                        numero_arquivo
                }
            )

            numero_arquivo += 1

            # -----------------------------------------------
            # Começar novo lote
            # -----------------------------------------------

            writer_atual = PdfWriter()

            paginas_writer_atual = []

            writer_atual.add_page(
                pagina_atual
            )

            paginas_writer_atual.append(
                {
                    "numero":
                        indice + 1,

                    "pagina":
                        pagina_atual
                }
            )

        else:

            # -----------------------------------------------
            # Adicionar ao lote atual
            # -----------------------------------------------

            writer_atual.add_page(
                pagina_atual
            )

            paginas_writer_atual.append(
                {
                    "numero":
                        indice + 1,

                    "pagina":
                        pagina_atual
                }
            )

        # ----------------------------------------------------
        # Atualizar progresso
        # ----------------------------------------------------

        if progress_bar is not None:

            percentual = (
                progresso_inicial
                +
                (
                    (
                        pagina_processada
                        /
                        total_paginas
                    )
                    *
                    (
                        progresso_final
                        -
                        progresso_inicial
                    )
                )
            )

            progress_bar.progress(
                min(
                    percentual,
                    1.0
                )
            )

    # ========================================================
    # SALVAR ÚLTIMO LOTE
    # ========================================================

    if len(
        paginas_writer_atual
    ) > 0:

        caminho_final = os.path.join(
            pasta_saida,
            f"{nome_base}_{numero_arquivo:02d}.pdf"
        )

        salvar_pdf(
            writer_atual,
            caminho_final
        )

        tamanho_final = os.path.getsize(
            caminho_final
        )

        paginas_numeros = [
            pagina["numero"]
            for pagina
            in paginas_writer_atual
        ]

        arquivos_gerados.append(
            {
                "caminho":
                    caminho_final,

                "tamanho":
                    tamanho_final,

                "paginas":
                    paginas_numeros,

                "numero":
                    numero_arquivo
            }
        )

    # ========================================================
    # VERIFICAR PÁGINAS INDIVIDUAIS MAIORES QUE 10 MB
    # ========================================================

    for arquivo in arquivos_gerados:

        if (
            arquivo["tamanho"]
            >
            TAMANHO_MAXIMO_BYTES
        ):

            arquivo[
                "acima_limite"
            ] = True

        else:

            arquivo[
                "acima_limite"
            ] = False

    gc.collect()

    return arquivos_gerados


# ============================================================
# CRIAR ZIP
# ============================================================

def criar_zip(
    arquivos,
    caminho_zip
):

    if not arquivos:

        return None

    with zipfile.ZipFile(
        caminho_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1
    ) as zip_file:

        for arquivo in arquivos:

            caminho = arquivo["caminho"]

            zip_file.write(
                caminho,
                arcname=os.path.basename(
                    caminho
                )
            )

    return caminho_zip


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
    # PROGRESSO
    # ========================================================

    progress_bar.progress(
        0.0
    )

    # ========================================================
    # CRIAR PDFs DE COMPROVANTES
    # ========================================================

    arquivos_comprovantes = []

    if paginas_comprovantes:

        status.info(
            "📄 Criando PDFs de COMPROVANTES "
            f"de até {TAMANHO_MAXIMO_MB} MB..."
        )

        arquivos_comprovantes = (
            dividir_pdf_por_tamanho(
                reader=reader,
                indices_paginas=paginas_comprovantes,
                pasta_saida=pasta_saida,
                nome_base="COMPROVANTES",
                progress_bar=progress_bar,
                progresso_inicial=0.0,
                progresso_final=0.5
            )
        )

    # ========================================================
    # CRIAR PDFs SEM COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = []

    if paginas_sem_comprovantes:

        status.info(
            "📄 Criando PDFs de SEM COMPROVANTES "
            f"de até {TAMANHO_MAXIMO_MB} MB..."
        )

        arquivos_sem_comprovantes = (
            dividir_pdf_por_tamanho(
                reader=reader,
                indices_paginas=paginas_sem_comprovantes,
                pasta_saida=pasta_saida,
                nome_base="SEM_COMPROVANTES",
                progress_bar=progress_bar,
                progresso_inicial=0.5,
                progresso_final=1.0
            )
        )

    # ========================================================
    # ZIP COMPROVANTES
    # ========================================================

    caminho_zip_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.zip"
    )

    if arquivos_comprovantes:

        status.info(
            "📦 Criando ZIP dos comprovantes..."
        )

        criar_zip(
            arquivos_comprovantes,
            caminho_zip_comprovantes
        )

    else:

        caminho_zip_comprovantes = None

    # ========================================================
    # ZIP SEM COMPROVANTES
    # ========================================================

    caminho_zip_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.zip"
    )

    if arquivos_sem_comprovantes:

        status.info(
            "📦 Criando ZIP das páginas sem comprovantes..."
        )

        criar_zip(
            arquivos_sem_comprovantes,
            caminho_zip_sem_comprovantes
        )

    else:

        caminho_zip_sem_comprovantes = None

    # ========================================================
    # TAMANHOS DOS ZIPs
    # ========================================================

    tamanho_zip_comprovantes = 0

    tamanho_zip_sem_comprovantes = 0

    if (
        caminho_zip_comprovantes
        and
        os.path.exists(
            caminho_zip_comprovantes
        )
    ):

        tamanho_zip_comprovantes = (
            os.path.getsize(
                caminho_zip_comprovantes
            )
        )

    if (
        caminho_zip_sem_comprovantes
        and
        os.path.exists(
            caminho_zip_sem_comprovantes
        )
    ):

        tamanho_zip_sem_comprovantes = (
            os.path.getsize(
                caminho_zip_sem_comprovantes
            )
        )

    # ========================================================
    # TEMPO
    # ========================================================

    tempo_total = (
        time.time() - inicio
    )

    progress_bar.progress(
        1.0
    )

    status.success(
        "✅ Processamento concluído!"
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

        "arquivos_comprovantes":
            arquivos_comprovantes,

        "arquivos_sem_comprovantes":
            arquivos_sem_comprovantes,

        "caminho_zip_comprovantes":
            caminho_zip_comprovantes,

        "caminho_zip_sem_comprovantes":
            caminho_zip_sem_comprovantes,

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
    f"""
    O sistema analisa o PDF página por página e separa:

    🔵 **COMPROVANTES**

    🟢 **PÁGINAS SEM COMPROVANTES**

    Cada grupo é dividido automaticamente em arquivos PDF
    de no máximo **{TAMANHO_MAXIMO_MB} MB**.

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
    f"""
    💡 O PDF original não é alterado.

    Os arquivos gerados possuem no máximo
    **{TAMANHO_MAXIMO_MB} MB cada**, sempre respeitando
    a divisão por páginas.
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
            # QUANTIDADE DE ARQUIVOS
            # =================================================

            st.subheader(
                "📦 Arquivos gerados"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "📄 PDFs de comprovantes",
                    len(
                        resultado[
                            "arquivos_comprovantes"
                        ]
                    )
                )

            with col2:

                st.metric(
                    "📄 PDFs sem comprovantes",
                    len(
                        resultado[
                            "arquivos_sem_comprovantes"
                        ]
                    )
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
                    "### 🔵 COMPROVANTES"
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
                    "### 🟢 SEM COMPROVANTES"
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
            # PDFs DE COMPROVANTES
            # =================================================

            if resultado[
                "arquivos_comprovantes"
            ]:

                st.divider()

                st.subheader(
                    "📄 PDFs — Comprovantes"
                )

                for arquivo in resultado[
                    "arquivos_comprovantes"
                ]:

                    caminho = arquivo[
                        "caminho"
                    ]

                    numero = arquivo[
                        "numero"
                    ]

                    tamanho = arquivo[
                        "tamanho"
                    ]

                    paginas = arquivo[
                        "paginas"
                    ]

                    acima_limite = arquivo[
                        "acima_limite"
                    ]

                    nome = os.path.basename(
                        caminho
                    )

                    col1, col2, col3 = st.columns(
                        [2, 1, 2]
                    )

                    with col1:

                        st.write(
                            f"**{nome}**"
                        )

                    with col2:

                        st.write(
                            formatar_tamanho(
                                tamanho
                            )
                        )

                    with col3:

                        st.write(
                            f"Páginas: "
                            f"{paginas[0]}"
                            f" até "
                            f"{paginas[-1]}"
                        )

                    if acima_limite:

                        st.warning(
                            f"⚠️ {nome} ultrapassou "
                            f"{TAMANHO_MAXIMO_MB} MB."
                        )

                    with open(
                        caminho,
                        "rb"
                    ) as arquivo_pdf:

                        dados_pdf = (
                            arquivo_pdf.read()
                        )

                    st.download_button(
                        label=(
                            f"⬇️ Baixar {nome}"
                        ),
                        data=dados_pdf,
                        file_name=nome,
                        mime="application/pdf",
                        use_container_width=True,
                        key=(
                            f"download_"
                            f"comprovantes_"
                            f"{numero}"
                        )
                    )

            # =================================================
            # PDFs SEM COMPROVANTES
            # =================================================

            if resultado[
                "arquivos_sem_comprovantes"
            ]:

                st.divider()

                st.subheader(
                    "📄 PDFs — Sem comprovantes"
                )

                for arquivo in resultado[
                    "arquivos_sem_comprovantes"
                ]:

                    caminho = arquivo[
                        "caminho"
                    ]

                    numero = arquivo[
                        "numero"
                    ]

                    tamanho = arquivo[
                        "tamanho"
                    ]

                    paginas = arquivo[
                        "paginas"
                    ]

                    acima_limite = arquivo[
                        "acima_limite"
                    ]

                    nome = os.path.basename(
                        caminho
                    )

                    col1, col2, col3 = st.columns(
                        [2, 1, 2]
                    )

                    with col1:

                        st.write(
                            f"**{nome}**"
                        )

                    with col2:

                        st.write(
                            formatar_tamanho(
                                tamanho
                            )
                        )

                    with col3:

                        st.write(
                            f"Páginas: "
                            f"{paginas[0]}"
                            f" até "
                            f"{paginas[-1]}"
                        )

                    if acima_limite:

                        st.warning(
                            f"⚠️ {nome} ultrapassou "
                            f"{TAMANHO_MAXIMO_MB} MB."
                        )

                    with open(
                        caminho,
                        "rb"
                    ) as arquivo_pdf:

                        dados_pdf = (
                            arquivo_pdf.read()
                        )

                    st.download_button(
                        label=(
                            f"⬇️ Baixar {nome}"
                        ),
                        data=dados_pdf,
                        file_name=nome,
                        mime="application/pdf",
                        use_container_width=True,
                        key=(
                            f"download_"
                            f"sem_comprovantes_"
                            f"{numero}"
                        )
                    )

            # =================================================
            # ZIP COMPROVANTES
            # =================================================

            if (
                resultado[
                    "caminho_zip_comprovantes"
                ]
                and
                os.path.exists(
                    resultado[
                        "caminho_zip_comprovantes"
                    ]
                )
            ):

                st.divider()

                st.subheader(
                    "📦 ZIP — Todos os comprovantes"
                )

                st.write(
                    f"Tamanho: "
                    f"**"
                    f"{formatar_tamanho(
                        resultado[
                            'tamanho_zip_comprovantes'
                        ]
                    )}"
                    f"**"
                )

                with open(
                    resultado[
                        "caminho_zip_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    dados_zip = (
                        arquivo.read()
                    )

                st.download_button(
                    label=(
                        "⬇️ Baixar "
                        "COMPROVANTES.zip"
                    ),
                    data=dados_zip,
                    file_name=(
                        "COMPROVANTES.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True,
                    key=(
                        "download_zip_comprovantes"
                    )
                )

            # =================================================
            # ZIP SEM COMPROVANTES
            # =================================================

            if (
                resultado[
                    "caminho_zip_sem_comprovantes"
                ]
                and
                os.path.exists(
                    resultado[
                        "caminho_zip_sem_comprovantes"
                    ]
                )
            ):

                st.divider()

                st.subheader(
                    "📦 ZIP — Todos os arquivos sem comprovantes"
                )

                st.write(
                    f"Tamanho: "
                    f"**"
                    f"{formatar_tamanho(
                        resultado[
                            'tamanho_zip_sem_comprovantes'
                        ]
                    )}"
                    f"**"
                )

                with open(
                    resultado[
                        "caminho_zip_sem_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    dados_zip = (
                        arquivo.read()
                    )

                st.download_button(
                    label=(
                        "⬇️ Baixar "
                        "SEM_COMPROVANTES.zip"
                    ),
                    data=dados_zip,
                    file_name=(
                        "SEM_COMPROVANTES.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True,
                    key=(
                        "download_zip_sem_comprovantes"
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

            # =================================================
            # TODAS AS PÁGINAS NÃO SÃO COMPROVANTES
            # =================================================

            if (
                resultado[
                    "total_comprovantes"
                ]
                == 0
                and
                resultado[
                    "total_sem_comprovantes"
                ]
                > 0
            ):

                st.info(
                    "ℹ️ Todas as páginas foram "
                    "classificadas como sem comprovante."
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
