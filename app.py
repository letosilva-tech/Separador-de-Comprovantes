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

TAMANHO_MAXIMO_MB = 10
TAMANHO_MAXIMO_BYTES = TAMANHO_MAXIMO_MB * 1024 * 1024


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """
    Remove acentos, caracteres especiais e normaliza
    o texto para facilitar a identificação dos comprovantes.
    """

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = texto.encode(
        "ASCII",
        "ignore"
    ).decode(
        "ASCII"
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


def identificar_comprovante(texto):
    """
    Identifica se a página contém um comprovante.

    Retorna:
        (True, tipo)
    ou:
        (False, None)
    """

    texto_normalizado = normalizar_texto(texto)

    if not texto_normalizado:
        return False, None

    # --------------------------------------------------------
    # PIX
    # --------------------------------------------------------

    padroes_pix = [
        "COMPROVANTE DE PIX",
        "COMPROVANTE PIX",
        "COMPROVANTE DO PIX",
        "PIX REALIZADO",
        "PIX EFETUADO",
        "PAGAMENTO PIX",
        "PIX ENVIADO",
        "PIX RECEBIDO",
        "PAGAMENTO REALIZADO VIA PIX",
        "TRANSFERENCIA VIA PIX",
        "TRANSACAO PIX",
    ]

    for padrao in padroes_pix:
        if padrao in texto_normalizado:
            return True, "PIX"

    # --------------------------------------------------------
    # TRANSFERÊNCIA
    # --------------------------------------------------------

    padroes_transferencia = [
        "COMPROVANTE DE TRANSFERENCIA",
        "COMPROVANTE TRANSFERENCIA",
        "COMPROVANTE DA TRANSFERENCIA",
        "TRANSFERENCIA REALIZADA",
        "TRANSFERENCIA EFETUADA",
        "TRANSFERENCIA BANCARIA",
        "TRANSFERENCIA ELETRONICA",
        "TRANSFERENCIA CONCLUIDA",
        "COMPROVANTE TED",
        "COMPROVANTE DOC",
        "TED REALIZADA",
        "TED EFETUADA",
        "DOC REALIZADO",
        "DOC EFETUADO",
    ]

    for padrao in padroes_transferencia:
        if padrao in texto_normalizado:
            return True, "TRANSFERÊNCIA"

    # --------------------------------------------------------
    # PAGAMENTO
    # --------------------------------------------------------

    padroes_pagamento = [
        "COMPROVANTE DE PAGAMENTO",
        "COMPROVANTE PAGAMENTO",
        "COMPROVANTE DO PAGAMENTO",
        "COMPROVANTE DE PAGAMENTO BANCARIO",
        "COMPROVANTE DE PAGAMENTO ONLINE",
        "PAGAMENTO REALIZADO",
        "PAGAMENTO EFETUADO",
        "PAGAMENTO CONCLUIDO",
        "PAGAMENTO CONFIRMADO",
    ]

    for padrao in padroes_pagamento:
        if padrao in texto_normalizado:
            return True, "PAGAMENTO"

    # --------------------------------------------------------
    # TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    padroes_transacao = [
        "COMPROVANTE DE TRANSACAO BANCARIA",
        "COMPROVANTE TRANSACAO BANCARIA",
        "COMPROVANTE DE TRANSACAO",
        "TRANSACAO BANCARIA",
        "TRANSACAO REALIZADA",
        "TRANSACAO EFETUADA",
        "TRANSACAO CONCLUIDA",
    ]

    for padrao in padroes_transacao:
        if padrao in texto_normalizado:
            return True, "TRANSAÇÃO"

    return False, None


def formatar_tamanho(tamanho_bytes):
    """
    Formata bytes em KB, MB ou GB.
    """

    if tamanho_bytes is None:
        return "0 B"

    if tamanho_bytes < 1024:
        return f"{tamanho_bytes} B"

    if tamanho_bytes < 1024 * 1024:
        return f"{tamanho_bytes / 1024:.2f} KB"

    if tamanho_bytes < 1024 * 1024 * 1024:
        return f"{tamanho_bytes / (1024 * 1024):.2f} MB"

    return f"{tamanho_bytes / (1024 * 1024 * 1024):.2f} GB"


def nome_seguro(nome):
    """
    Remove caracteres problemáticos de nomes de arquivos.
    """

    nome = unicodedata.normalize(
        "NFKD",
        nome
    )

    nome = nome.encode(
        "ASCII",
        "ignore"
    ).decode(
        "ASCII"
    )

    nome = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nome
    )

    return nome.strip("_")


# ============================================================
# CRIAÇÃO DE PDF
# ============================================================

def criar_pdf_com_paginas(
    reader,
    indices_paginas,
    caminho_saida
):
    """
    Cria um PDF utilizando os índices das páginas
    diretamente do PdfReader.

    IMPORTANTE:
    Não reutiliza PageObjects previamente armazenados.
    Isso evita o erro:

        ValueError: Invalid page object
    """

    writer = PdfWriter()

    for indice in indices_paginas:

        pagina = reader.pages[indice]

        writer.add_page(
            pagina
        )

    with open(
        caminho_saida,
        "wb"
    ) as arquivo:

        writer.write(
            arquivo
        )

    tamanho = os.path.getsize(
        caminho_saida
    )

    return tamanho


def medir_pdf_com_paginas(
    reader,
    indices_paginas,
    pasta_temporaria,
    nome_base
):
    """
    Cria um PDF temporário para medir seu tamanho real.
    """

    nome_teste = (
        f"_teste_"
        f"{nome_base}_"
        f"{time.time_ns()}.pdf"
    )

    caminho_teste = os.path.join(
        pasta_temporaria,
        nome_teste
    )

    try:

        tamanho = criar_pdf_com_paginas(
            reader=reader,
            indices_paginas=indices_paginas,
            caminho_saida=caminho_teste
        )

        return tamanho

    finally:

        if os.path.exists(
            caminho_teste
        ):

            try:
                os.remove(
                    caminho_teste
                )

            except Exception:
                pass


# ============================================================
# DIVISÃO DOS PDFS POR TAMANHO
# ============================================================

def dividir_pdf_por_tamanho(
    reader,
    indices_paginas,
    pasta_saida,
    nome_base,
    tamanho_maximo_bytes,
    progresso_inicio=0.0,
    progresso_final=1.0,
    status=None
):
    """
    Agrupa várias páginas em PDFs de até o limite definido.

    Exemplo:

        COMPROVANTES_01.pdf
        COMPROVANTES_02.pdf
        COMPROVANTES_03.pdf

    Cada PDF recebe o maior número possível de páginas
    sem ultrapassar o limite de tamanho.

    A mesma lógica é utilizada para:

        COMPROVANTES

    e:

        SEM_COMPROVANTES
    """

    arquivos_gerados = []

    if not indices_paginas:
        return arquivos_gerados

    os.makedirs(
        pasta_saida,
        exist_ok=True
    )

    total_paginas = len(
        indices_paginas
    )

    # --------------------------------------------------------
    # O lote guarda somente os índices das páginas.
    #
    # NÃO guarda PageObjects.
    # --------------------------------------------------------

    lote_atual = []

    contador_arquivo = 1

    # --------------------------------------------------------
    # Função interna para salvar um lote
    # --------------------------------------------------------

    def salvar_lote(
        indices,
        numero
    ):

        if not indices:
            return None

        nome_arquivo = (
            f"{nome_base}_"
            f"{numero:02d}.pdf"
        )

        caminho_final = os.path.join(
            pasta_saida,
            nome_arquivo
        )

        tamanho = criar_pdf_com_paginas(
            reader=reader,
            indices_paginas=indices,
            caminho_saida=caminho_final
        )

        return {
            "path": caminho_final,
            "nome": nome_arquivo,
            "size": tamanho,
            "size_mb": (
                tamanho /
                (1024 * 1024)
            ),
            "pages": list(indices),
            "page_count": len(indices),
            "number": numero,
            "above_limit": (
                tamanho >
                tamanho_maximo_bytes
            )
        }

    # --------------------------------------------------------
    # Processamento das páginas
    # --------------------------------------------------------

    for posicao, indice_pagina in enumerate(
        indices_paginas
    ):

        # ====================================================
        # PRIMEIRA PÁGINA DO LOTE
        # ====================================================

        if not lote_atual:

            tamanho_pagina = medir_pdf_com_paginas(
                reader=reader,
                indices_paginas=[
                    indice_pagina
                ],
                pasta_temporaria=pasta_saida,
                nome_base=nome_base
            )

            # ------------------------------------------------
            # A própria página já ultrapassa 10 MB.
            # ------------------------------------------------

            if (
                tamanho_pagina >
                tamanho_maximo_bytes
            ):

                arquivo = salvar_lote(
                    indices=[
                        indice_pagina
                    ],
                    numero=contador_arquivo
                )

                arquivos_gerados.append(
                    arquivo
                )

                contador_arquivo += 1

                lote_atual = []

            else:

                lote_atual = [
                    indice_pagina
                ]

        # ====================================================
        # JÁ EXISTE UM LOTE
        # ====================================================

        else:

            lote_teste = (
                lote_atual +
                [indice_pagina]
            )

            tamanho_teste = medir_pdf_com_paginas(
                reader=reader,
                indices_paginas=lote_teste,
                pasta_temporaria=pasta_saida,
                nome_base=nome_base
            )

            # ------------------------------------------------
            # A nova página cabe no PDF atual.
            # ------------------------------------------------

            if (
                tamanho_teste <=
                tamanho_maximo_bytes
            ):

                lote_atual.append(
                    indice_pagina
                )

            # ------------------------------------------------
            # A nova página faria o PDF ultrapassar 10 MB.
            # ------------------------------------------------

            else:

                # --------------------------------------------
                # Fecha o lote atual.
                # --------------------------------------------

                arquivo = salvar_lote(
                    indices=lote_atual,
                    numero=contador_arquivo
                )

                arquivos_gerados.append(
                    arquivo
                )

                contador_arquivo += 1

                # --------------------------------------------
                # Começa novo lote.
                # --------------------------------------------

                tamanho_pagina = medir_pdf_com_paginas(
                    reader=reader,
                    indices_paginas=[
                        indice_pagina
                    ],
                    pasta_temporaria=pasta_saida,
                    nome_base=nome_base
                )

                lote_atual = [
                    indice_pagina
                ]

                # --------------------------------------------
                # Se uma única página já tiver mais de 10 MB,
                # ela fica sozinha.
                # --------------------------------------------

                if (
                    tamanho_pagina >
                    tamanho_maximo_bytes
                ):

                    arquivo = salvar_lote(
                        indices=lote_atual,
                        numero=contador_arquivo
                    )

                    arquivos_gerados.append(
                        arquivo
                    )

                    contador_arquivo += 1

                    lote_atual = []

        # ====================================================
        # PROGRESSO
        # ====================================================

        if status is not None:

            percentual = (
                progresso_inicio
                +
                (
                    (posicao + 1) /
                    total_paginas
                )
                *
                (
                    progresso_final -
                    progresso_inicio
                )
            )

            try:

                status.progress(
                    min(
                        percentual,
                        1.0
                    )
                )

            except Exception:
                pass

    # ========================================================
    # SALVA O ÚLTIMO LOTE
    # ========================================================

    if lote_atual:

        arquivo = salvar_lote(
            indices=lote_atual,
            numero=contador_arquivo
        )

        arquivos_gerados.append(
            arquivo
        )

    return arquivos_gerados


# ============================================================
# CRIAÇÃO DO ZIP
# ============================================================

def criar_zip(
    arquivos,
    caminho_zip
):
    """
    Cria um ZIP contendo os PDFs gerados.
    """

    with zipfile.ZipFile(
        caminho_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED
    ) as zipf:

        for arquivo in arquivos:

            caminho = arquivo["path"]

            if os.path.exists(
                caminho
            ):

                zipf.write(
                    caminho,
                    arcname=os.path.basename(
                        caminho
                    )
                )

    return caminho_zip


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar_pdf(
    caminho_pdf_original,
    pasta_base=None,
    status=None
):
    """
    Processa o PDF original.

    Classifica cada página como:

        COMPROVANTE

    ou:

        SEM_COMPROVANTE

    Depois agrupa os PDFs em lotes de até 10 MB.
    """

    inicio = time.time()

    # --------------------------------------------------------
    # Validação
    # --------------------------------------------------------

    if not os.path.exists(
        caminho_pdf_original
    ):

        raise FileNotFoundError(
            "O arquivo PDF informado não existe."
        )

    # --------------------------------------------------------
    # Cria pasta de trabalho
    # --------------------------------------------------------

    if pasta_base is None:

        pasta_base = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

    os.makedirs(
        pasta_base,
        exist_ok=True
    )

    pasta_saida = os.path.join(
        pasta_base,
        "saida"
    )

    os.makedirs(
        pasta_saida,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Lê o PDF
    # --------------------------------------------------------

    reader = PdfReader(
        caminho_pdf_original,
        strict=False
    )

    total_paginas = len(
        reader.pages
    )

    if total_paginas == 0:

        raise ValueError(
            "O PDF não possui páginas."
        )

    # --------------------------------------------------------
    # Estruturas
    # --------------------------------------------------------

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    tipos_comprovantes = {}

    textos_paginas = {}

    diagnosticos = []

    # ========================================================
    # CLASSIFICAÇÃO DAS PÁGINAS
    # ========================================================

    if status is not None:

        try:
            status.progress(
                0.05
            )

        except Exception:
            pass

    for indice, pagina in enumerate(
        reader.pages
    ):

        numero_pagina = indice + 1

        try:

            texto = pagina.extract_text()

        except Exception as erro:

            texto = ""

            diagnosticos.append(
                f"Página {numero_pagina}: "
                f"erro ao extrair texto: {erro}"
            )

        texto = texto or ""

        textos_paginas[
            numero_pagina
        ] = texto

        eh_comprovante, tipo = identificar_comprovante(
            texto
        )

        if eh_comprovante:

            paginas_comprovantes.append(
                indice
            )

            tipos_comprovantes[
                indice
            ] = tipo

        else:

            paginas_sem_comprovantes.append(
                indice
            )

        # ----------------------------------------------------
        # Progresso da classificação
        # ----------------------------------------------------

        if status is not None:

            percentual = (
                0.05
                +
                (
                    (indice + 1) /
                    total_paginas
                )
                * 0.30
            )

            try:

                status.progress(
                    min(
                        percentual,
                        1.0
                    )
                )

            except Exception:
                pass

    # ========================================================
    # VALIDAÇÕES
    # ========================================================

    total_classificado = (
        len(paginas_comprovantes)
        +
        len(paginas_sem_comprovantes)
    )

    if total_classificado != total_paginas:

        raise ValueError(
            "A quantidade de páginas classificadas "
            "não corresponde ao total de páginas do PDF."
        )

    conjunto_comprovantes = set(
        paginas_comprovantes
    )

    conjunto_sem_comprovantes = set(
        paginas_sem_comprovantes
    )

    intersecao = (
        conjunto_comprovantes &
        conjunto_sem_comprovantes
    )

    if intersecao:

        raise ValueError(
            "Existem páginas classificadas "
            "simultaneamente como comprovante "
            "e sem comprovante."
        )

    conjunto_todas_paginas = (
        conjunto_comprovantes |
        conjunto_sem_comprovantes
    )

    if len(
        conjunto_todas_paginas
    ) != total_paginas:

        raise ValueError(
            "Nem todas as páginas foram classificadas."
        )

    # ========================================================
    # DIVISÃO DOS COMPROVANTES
    # ========================================================

    if status is not None:

        try:
            status.progress(
                0.40
            )

        except Exception:
            pass

    arquivos_comprovantes = dividir_pdf_por_tamanho(
        reader=reader,
        indices_paginas=paginas_comprovantes,
        pasta_saida=pasta_saida,
        nome_base="COMPROVANTES",
        tamanho_maximo_bytes=TAMANHO_MAXIMO_BYTES,
        progresso_inicio=0.40,
        progresso_final=0.65,
        status=status
    )

    # ========================================================
    # DIVISÃO DOS SEM COMPROVANTES
    # ========================================================

    if status is not None:

        try:
            status.progress(
                0.65
            )

        except Exception:
            pass

    arquivos_sem_comprovantes = dividir_pdf_por_tamanho(
        reader=reader,
        indices_paginas=paginas_sem_comprovantes,
        pasta_saida=pasta_saida,
        nome_base="SEM_COMPROVANTES",
        tamanho_maximo_bytes=TAMANHO_MAXIMO_BYTES,
        progresso_inicio=0.65,
        progresso_final=0.90,
        status=status
    )

    # ========================================================
    # CRIAÇÃO DOS ZIPS
    # ========================================================

    zip_comprovantes = None

    zip_sem_comprovantes = None

    if arquivos_comprovantes:

        zip_comprovantes = os.path.join(
            pasta_saida,
            "COMPROVANTES.zip"
        )

        criar_zip(
            arquivos=arquivos_comprovantes,
            caminho_zip=zip_comprovantes
        )

    if arquivos_sem_comprovantes:

        zip_sem_comprovantes = os.path.join(
            pasta_saida,
            "SEM_COMPROVANTES.zip"
        )

        criar_zip(
            arquivos=arquivos_sem_comprovantes,
            caminho_zip=zip_sem_comprovantes
        )

    # ========================================================
    # RESULTADO
    # ========================================================

    tempo_total = (
        time.time() -
        inicio
    )

    tamanho_original = os.path.getsize(
        caminho_pdf_original
    )

    resultado = {
        "total_paginas": total_paginas,

        "paginas_comprovantes": paginas_comprovantes,

        "paginas_sem_comprovantes": paginas_sem_comprovantes,

        "total_comprovantes": len(
            paginas_comprovantes
        ),

        "total_sem_comprovantes": len(
            paginas_sem_comprovantes
        ),

        "tipos_comprovantes": tipos_comprovantes,

        "textos_paginas": textos_paginas,

        "arquivos_comprovantes": arquivos_comprovantes,

        "arquivos_sem_comprovantes": arquivos_sem_comprovantes,

        "zip_comprovantes": zip_comprovantes,

        "zip_sem_comprovantes": zip_sem_comprovantes,

        "diagnosticos": diagnosticos,

        "tempo_total": tempo_total,

        "tamanho_original": tamanho_original,

        "tamanho_original_mb": (
            tamanho_original /
            (1024 * 1024)
        ),

        "tamanho_maximo_mb": TAMANHO_MAXIMO_MB,

        "pasta_saida": pasta_saida,
    }

    if status is not None:

        try:
            status.progress(
                1.0
            )

        except Exception:
            pass

    # --------------------------------------------------------
    # Libera objetos
    # --------------------------------------------------------

    gc.collect()

    return resultado


# ============================================================
# INTERFACE STREAMLIT
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.markdown(
    """
Esta ferramenta analisa cada página do PDF e separa:

- **Comprovantes**
- **Páginas sem comprovantes**

Os comprovantes são agrupados em PDFs de até **10 MB por arquivo**.
"""
)

st.info(
    f"📦 Cada PDF poderá conter vários comprovantes, "
    f"até atingir aproximadamente {TAMANHO_MAXIMO_MB} MB."
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_upload = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo_upload is not None:

    st.success(
        f"Arquivo selecionado: "
        f"**{arquivo_upload.name}**"
    )

    tamanho_upload = (
        len(
            arquivo_upload.getvalue()
        )
    )

    st.write(
        f"Tamanho original: "
        f"**{formatar_tamanho(tamanho_upload)}**"
    )

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
                arquivo_upload.name
            )
        )

        status = st.progress(
            0
        )

        texto_status = st.empty()

        try:

            # ------------------------------------------------
            # Salva upload
            # ------------------------------------------------

            texto_status.write(
                "📥 Salvando PDF..."
            )

            with open(
                caminho_pdf_original,
                "wb"
            ) as arquivo:

                arquivo.write(
                    arquivo_upload.getbuffer()
                )

            # ------------------------------------------------
            # Processa
            # ------------------------------------------------

            texto_status.write(
                "🔎 Analisando e separando as páginas..."
            )

            resultado = processar_pdf(
                caminho_pdf_original,
                pasta_base=pasta_trabalho,
                status=status
            )

            # ------------------------------------------------
            # Finalização
            # ------------------------------------------------

            texto_status.write(
                "✅ Processamento concluído!"
            )

            status.progress(
                1.0
            )

            st.divider()

            # =================================================
            # RESUMO
            # =================================================

            st.subheader(
                "📊 Resumo"
            )

            col1, col2, col3, col4 = st.columns(
                4
            )

            with col1:

                st.metric(
                    "Total de páginas",
                    resultado[
                        "total_paginas"
                    ]
                )

            with col2:

                st.metric(
                    "Comprovantes",
                    resultado[
                        "total_comprovantes"
                    ]
                )

            with col3:

                st.metric(
                    "Sem comprovantes",
                    resultado[
                        "total_sem_comprovantes"
                    ]
                )

            with col4:

                st.metric(
                    "Tempo",
                    f"{resultado['tempo_total']:.2f}s"
                )

            # =================================================
            # CONFERÊNCIA
            # =================================================

            st.subheader(
                "🔎 Conferência"
            )

            total_conferido = (
                resultado[
                    "total_comprovantes"
                ]
                +
                resultado[
                    "total_sem_comprovantes"
                ]
            )

            if (
                total_conferido ==
                resultado[
                    "total_paginas"
                ]
            ):

                st.success(
                    f"✅ Conferência OK: "
                    f"{total_conferido} páginas "
                    f"classificadas de "
                    f"{resultado['total_paginas']}."
                )

            else:

                st.error(
                    f"❌ Divergência: "
                    f"{total_conferido} páginas "
                    f"classificadas de "
                    f"{resultado['total_paginas']}."
                )

            # =================================================
            # ARQUIVOS DE COMPROVANTES
            # =================================================

            st.divider()

            st.subheader(
                "📄 PDFs de Comprovantes"
            )

            arquivos_comprovantes = resultado[
                "arquivos_comprovantes"
            ]

            if arquivos_comprovantes:

                st.info(
                    f"Foram gerados "
                    f"**{len(arquivos_comprovantes)} PDF(s)** "
                    f"de comprovantes."
                )

                for arquivo in arquivos_comprovantes:

                    paginas = arquivo[
                        "pages"
                    ]

                    pagina_inicial = (
                        min(paginas) + 1
                    )

                    pagina_final = (
                        max(paginas) + 1
                    )

                    tamanho = arquivo[
                        "size"
                    ]

                    nome = arquivo[
                        "nome"
                    ]

                    acima_limite = arquivo[
                        "above_limit"
                    ]

                    col_a, col_b, col_c = st.columns(
                        [3, 2, 2]
                    )

                    with col_a:

                        st.write(
                            f"📄 **{nome}**"
                        )

                        st.caption(
                            f"{arquivo['page_count']} "
                            f"página(s) | "
                            f"Páginas originais "
                            f"{pagina_inicial}–{pagina_final}"
                        )

                    with col_b:

                        st.write(
                            formatar_tamanho(
                                tamanho
                            )
                        )

                    with col_c:

                        with open(
                            arquivo["path"],
                            "rb"
                        ) as pdf_file:

                            st.download_button(
                                label="⬇️ Baixar PDF",
                                data=pdf_file.read(),
                                file_name=nome,
                                mime="application/pdf",
                                key=(
                                    f"download_comp_"
                                    f"{arquivo['number']}"
                                ),
                                use_container_width=True
                            )

                    if acima_limite:

                        st.warning(
                            f"⚠️ {nome} possui "
                            f"{formatar_tamanho(tamanho)}. "
                            f"Uma das páginas individuais "
                            f"já ultrapassou o limite de "
                            f"{TAMANHO_MAXIMO_MB} MB."
                        )

            else:

                st.warning(
                    "Nenhum comprovante foi identificado."
                )

            # =================================================
            # ZIP DE COMPROVANTES
            # =================================================

            if resultado[
                "zip_comprovantes"
            ]:

                st.markdown(
                    "### 📦 ZIP dos comprovantes"
                )

                caminho_zip = resultado[
                    "zip_comprovantes"
                ]

                with open(
                    caminho_zip,
                    "rb"
                ) as zip_file:

                    st.download_button(
                        label="⬇️ Baixar todos os comprovantes (ZIP)",
                        data=zip_file.read(),
                        file_name="COMPROVANTES.zip",
                        mime="application/zip",
                        key="download_zip_comprovantes",
                        use_container_width=True
                    )

            # =================================================
            # SEM COMPROVANTES
            # =================================================

            st.divider()

            st.subheader(
                "📄 PDFs sem Comprovantes"
            )

            arquivos_sem = resultado[
                "arquivos_sem_comprovantes"
            ]

            if arquivos_sem:

                st.info(
                    f"Foram gerados "
                    f"**{len(arquivos_sem)} PDF(s)** "
                    f"sem comprovantes."
                )

                for arquivo in arquivos_sem:

                    paginas = arquivo[
                        "pages"
                    ]

                    pagina_inicial = (
                        min(paginas) + 1
                    )

                    pagina_final = (
                        max(paginas) + 1
                    )

                    tamanho = arquivo[
                        "size"
                    ]

                    nome = arquivo[
                        "nome"
                    ]

                    acima_limite = arquivo[
                        "above_limit"
                    ]

                    col_a, col_b, col_c = st.columns(
                        [3, 2, 2]
                    )

                    with col_a:

                        st.write(
                            f"📄 **{nome}**"
                        )

                        st.caption(
                            f"{arquivo['page_count']} "
                            f"página(s) | "
                            f"Páginas originais "
                            f"{pagina_inicial}–{pagina_final}"
                        )

                    with col_b:

                        st.write(
                            formatar_tamanho(
                                tamanho
                            )
                        )

                    with col_c:

                        with open(
                            arquivo["path"],
                            "rb"
                        ) as pdf_file:

                            st.download_button(
                                label="⬇️ Baixar PDF",
                                data=pdf_file.read(),
                                file_name=nome,
                                mime="application/pdf",
                                key=(
                                    f"download_sem_"
                                    f"{arquivo['number']}"
                                ),
                                use_container_width=True
                            )

                    if acima_limite:

                        st.warning(
                            f"⚠️ {nome} possui "
                            f"{formatar_tamanho(tamanho)}. "
                            f"Uma das páginas individuais "
                            f"já ultrapassou o limite de "
                            f"{TAMANHO_MAXIMO_MB} MB."
                        )

            else:

                st.success(
                    "Não existem páginas sem comprovantes."
                )

            # =================================================
            # ZIP SEM COMPROVANTES
            # =================================================

            if resultado[
                "zip_sem_comprovantes"
            ]:

                st.markdown(
                    "### 📦 ZIP das páginas sem comprovantes"
                )

                caminho_zip_sem = resultado[
                    "zip_sem_comprovantes"
                ]

                with open(
                    caminho_zip_sem,
                    "rb"
                ) as zip_file:

                    st.download_button(
                        label="⬇️ Baixar todos sem comprovantes (ZIP)",
                        data=zip_file.read(),
                        file_name="SEM_COMPROVANTES.zip",
                        mime="application/zip",
                        key="download_zip_sem_comprovantes",
                        use_container_width=True
                    )

            # =================================================
            # TIPOS DE COMPROVANTES
            # =================================================

            st.divider()

            st.subheader(
                "📋 Tipos de comprovantes identificados"
            )

            contagem_tipos = {}

            for tipo in resultado[
                "tipos_comprovantes"
            ].values():

                contagem_tipos[tipo] = (
                    contagem_tipos.get(
                        tipo,
                        0
                    ) + 1
                )

            if contagem_tipos:

                colunas = st.columns(
                    len(contagem_tipos)
                )

                for coluna, (
                    tipo,
                    quantidade
                ) in zip(
                    colunas,
                    contagem_tipos.items()
                ):

                    with coluna:

                        st.metric(
                            tipo,
                            quantidade
                        )

            else:

                st.info(
                    "Nenhum tipo de comprovante identificado."
                )

            # =================================================
            # PÁGINAS DOS COMPROVANTES
            # =================================================

            with st.expander(
                "📑 Ver páginas identificadas como comprovantes"
            ):

                paginas_exibicao = [
                    pagina + 1
                    for pagina in resultado[
                        "paginas_comprovantes"
                    ]
                ]

                if paginas_exibicao:

                    st.write(
                        paginas_exibicao
                    )

                else:

                    st.write(
                        "Nenhuma."
                    )

            # =================================================
            # PÁGINAS SEM COMPROVANTES
            # =================================================

            with st.expander(
                "📑 Ver páginas sem comprovantes"
            ):

                paginas_exibicao = [
                    pagina + 1
                    for pagina in resultado[
                        "paginas_sem_comprovantes"
                    ]
                ]

                if paginas_exibicao:

                    st.write(
                        paginas_exibicao
                    )

                else:

                    st.write(
                        "Nenhuma."
                    )

            # =================================================
            # DIAGNÓSTICOS
            # =================================================

            diagnosticos = resultado[
                "diagnosticos"
            ]

            if diagnosticos:

                st.divider()

                st.subheader(
                    "⚠️ Diagnósticos"
                )

                for diagnostico in diagnosticos:

                    st.warning(
                        diagnostico
                    )

            # =================================================
            # INFORMAÇÕES DO PROCESSAMENTO
            # =================================================

            st.divider()

            st.subheader(
                "ℹ️ Informações"
            )

            col1, col2, col3 = st.columns(
                3
            )

            with col1:

                st.write(
                    "**PDF original:**"
                )

                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_original"
                        ]
                    )
                )

            with col2:

                st.write(
                    "**Limite por PDF:**"
                )

                st.write(
                    f"{TAMANHO_MAXIMO_MB} MB"
                )

            with col3:

                st.write(
                    "**Tempo de processamento:**"
                )

                st.write(
                    f"{resultado['tempo_total']:.2f} segundos"
                )

        except Exception as erro:

            st.error(
                "❌ Ocorreu um erro durante o processamento."
            )

            st.exception(
                erro
            )

        finally:

            # ------------------------------------------------
            # Limpeza
            # ------------------------------------------------

            gc.collect()

            # Pequena pausa para liberar arquivos
            time.sleep(
                0.2
            )

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except Exception:
                pass
