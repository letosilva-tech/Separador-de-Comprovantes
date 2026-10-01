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
# NORMALIZAÇÃO
# ============================================================

def normalizar_texto(texto: str) -> str:

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
# IDENTIFICAÇÃO DO COMPROVANTE
# ============================================================

def identificar_tipo_comprovante(texto: str):

    texto = normalizar_texto(texto)

    # PIX
    if re.search(
        r"COMPROVANTE\s+PIX",
        texto
    ):
        return "PIX"

    # TRANSFERÊNCIA
    if re.search(
        r"COMPROVANTE\s+(DE\s+)?TRANSFERENCIA",
        texto
    ):
        return "TRANSFERENCIA"

    # TRANSAÇÃO BANCÁRIA
    if re.search(
        r"COMPROVANTE\s+DE\s+TRANSACAO\s+BANCARIA",
        texto
    ):
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# SEPARAÇÃO
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

    paginas_sem_comprovante = []

    total_paginas = len(
        leitor.pages
    )

    for indice, pagina in enumerate(
        leitor.pages
    ):

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
        # TEXTO
        # ----------------------------------------------------

        texto = pagina.extract_text() or ""

        # ----------------------------------------------------
        # IDENTIFICA TIPO
        # ----------------------------------------------------

        tipo = identificar_tipo_comprovante(
            texto
        )

        # ====================================================
        # NOVO COMPROVANTE
        # ====================================================

        if tipo is not None:

            # Salva o comprovante anterior
            if comprovante_atual:

                comprovantes.append({
                    "tipo": tipo_atual,
                    "paginas": comprovante_atual,
                    "pagina_inicio": pagina_inicio,
                    "pagina_fim": numero_pagina - 1
                })

            # Inicia novo comprovante
            comprovante_atual = [
                pagina
            ]

            tipo_atual = tipo

            pagina_inicio = numero_pagina

            continue

        # ====================================================
        # PÁGINA SEM COMPROVANTE
        # ====================================================

        if comprovante_atual:

            # ------------------------------------------------
            # ATENÇÃO:
            # Essa página é considerada continuação do
            # comprovante anterior.
            # ------------------------------------------------

            comprovante_atual.append(
                pagina
            )

        else:

            # Página que apareceu antes do primeiro comprovante
            paginas_sem_comprovante.append(
                {
                    "numero": numero_pagina,
                    "pagina": pagina
                }
            )

    # ========================================================
    # SALVA ÚLTIMO COMPROVANTE
    # ========================================================

    if comprovante_atual:

        comprovantes.append({
            "tipo": tipo_atual,
            "paginas": comprovante_atual,
            "pagina_inicio": pagina_inicio,
            "pagina_fim": total_paginas
        })

    return (
        comprovantes,
        paginas_sem_comprovante
    )


# ============================================================
# CRIA PDF INDIVIDUAL
# ============================================================

def criar_pdf_comprovante(
    paginas
):

    escritor = PdfWriter()

    for pagina in paginas:

        escritor.add_page(
            pagina
        )

    buffer = BytesIO()

    escritor.write(
        buffer
    )

    return buffer.getvalue()


# ============================================================
# CRIA ZIPS DE ATÉ 10 MB
# ============================================================

def criar_zips_comprovantes(
    comprovantes,
    limite_mb=10
):

    limite_bytes = (
        limite_mb
        * 1024
        * 1024
    )

    arquivos_zip = []

    zip_buffer = BytesIO()

    zip_file = zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    )

    tamanho_estimado = 0

    numero_parte = 1

    contador_arquivo = 1

    for comprovante in comprovantes:

        tipo = comprovante["tipo"]

        paginas = comprovante["paginas"]

        # ----------------------------------------------------
        # NOME
        # ----------------------------------------------------

        if tipo == "PIX":

            prefixo = "PIX"

        elif tipo == "TRANSFERENCIA":

            prefixo = "TRANSFERENCIA"

        elif tipo == "TRANSACAO_BANCARIA":

            prefixo = "TRANSACAO_BANCARIA"

        else:

            prefixo = "OUTRO"

        # ----------------------------------------------------
        # PDF
        # ----------------------------------------------------

        pdf_bytes = criar_pdf_comprovante(
            paginas
        )

        nome = (
            f"comprovante_"
            f"{prefixo}_"
            f"{contador_arquivo:03d}.pdf"
        )

        tamanho_pdf = len(
            pdf_bytes
        )

        # ----------------------------------------------------
        # NOVO ZIP
        # ----------------------------------------------------

        if (
            tamanho_estimado > 0
            and tamanho_estimado + tamanho_pdf > limite_bytes
        ):

            zip_file.close()

            arquivos_zip.append({
                "nome":
                    f"comprovantes_"
                    f"parte_{numero_parte:03d}.zip",

                "dados":
                    zip_buffer.getvalue()
            })

            numero_parte += 1

            zip_buffer = BytesIO()

            zip_file = zipfile.ZipFile(
                zip_buffer,
                "w",
                zipfile.ZIP_DEFLATED
            )

            tamanho_estimado = 0

        # ----------------------------------------------------
        # ADICIONA
        # ----------------------------------------------------

        zip_file.writestr(
            nome,
            pdf_bytes
        )

        tamanho_estimado += tamanho_pdf

        contador_arquivo += 1

    # --------------------------------------------------------
    # ÚLTIMO ZIP
    # --------------------------------------------------------

    zip_file.close()

    if tamanho_estimado > 0:

        arquivos_zip.append({
            "nome":
                f"comprovantes_"
                f"parte_{numero_parte:03d}.zip",

            "dados":
                zip_buffer.getvalue()
        })

    return arquivos_zip


# ============================================================
# PDF DAS PÁGINAS SEM COMPROVANTE
# ============================================================

def criar_pdf_sem_comprovantes(
    paginas
):

    if not paginas:

        return None

    escritor = PdfWriter()

    for item in paginas:

        escritor.add_page(
            item["pagina"]
        )

    buffer = BytesIO()

    escritor.write(
        buffer
    )

    return buffer.getvalue()


# ============================================================
# INTERFACE
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

    As páginas que não forem identificadas como comprovantes
    serão disponibilizadas separadamente.
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
# LIMPA RESULTADOS QUANDO TROCA O ARQUIVO
# ============================================================

if arquivo_pdf is None:

    chaves = [
        "arquivos_zip",
        "pdf_sem_comprovantes",
        "quantidade",
        "pix",
        "transferencias",
        "transacoes",
        "paginas_sem_comprovante",
        "detalhes"
    ]

    for chave in chaves:

        st.session_state.pop(
            chave,
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
                    "Todas as páginas foram consideradas "
                    "como páginas sem comprovante."
                )

                # Cria PDF com tudo
                pdf_restante = criar_pdf_sem_comprovantes(
                    paginas_sem_comprovante
                )

                st.session_state[
                    "pdf_sem_comprovantes"
                ] = pdf_restante

                st.session_state[
                    "paginas_sem_comprovante"
                ] = len(
                    paginas_sem_comprovante
                )

            else:

                # =================================================
                # GERA ZIPS
                # =================================================

                status.text(
                    "📦 Gerando arquivos dos comprovantes..."
                )

                arquivos_zip = criar_zips_comprovantes(
                    comprovantes,
                    limite_mb=10
                )

                # =================================================
                # GERA PDF RESTANTE
                # =================================================

                status.text(
                    "📄 Gerando arquivo das páginas restantes..."
                )

                pdf_restante = criar_pdf_sem_comprovantes(
                    paginas_sem_comprovante
                )

                # =================================================
                # CONTADORES
                # =================================================

                quantidade_pix = sum(
                    1
                    for c in comprovantes
                    if c["tipo"] == "PIX"
                )

                quantidade_transferencia = sum(
                    1
                    for c in comprovantes
                    if c["tipo"] == "TRANSFERENCIA"
                )

                quantidade_transacao = sum(
                    1
                    for c in comprovantes
                    if c["tipo"] == "TRANSACAO_BANCARIA"
                )

                # =================================================
                # SALVA
                # =================================================

                st.session_state[
                    "arquivos_zip"
                ] = arquivos_zip

                st.session_state[
                    "pdf_sem_comprovantes"
                ] = pdf_restante

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
                    "paginas_sem_comprovante"
                ] = len(
                    paginas_sem_comprovante
                )

                st.session_state[
                    "detalhes"
                ] = comprovantes

                # =================================================
                # TEMPO
                # =================================================

                tempo = (
                    time.time()
                    - inicio
                )

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
                # PÁGINAS SEM COMPROVANTE
                # =================================================

                if paginas_sem_comprovante:

                    st.warning(
                        f"⚠️ "
                        f"{len(paginas_sem_comprovante)} "
                        f"página(s) não foram identificadas "
                        f"como comprovantes."
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

                    dados.append({
                        "Nº": numero,

                        "Tipo":
                            comprovante["tipo"],

                        "Página inicial":
                            comprovante[
                                "pagina_inicio"
                            ],

                        "Página final":
                            comprovante[
                                "pagina_fim"
                            ],

                        "Quantidade de páginas":
                            len(
                                comprovante[
                                    "paginas"
                                ]
                            )
                    })

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
# DOWNLOADS
# ============================================================

if (
    arquivo_pdf is not None
    and "arquivos_zip"
    in st.session_state
):

    st.divider()

    st.subheader(
        "📦 Comprovantes separados"
    )

    arquivos_zip = st.session_state[
        "arquivos_zip"
    ]

    st.success(
        f"✅ {len(arquivos_zip)} "
        f"arquivo(s) ZIP foram gerados."
    )

    # ========================================================
    # ZIPS
    # ========================================================

    for arquivo in arquivos_zip:

        tamanho_mb = (
            len(
                arquivo["dados"]
            )
            / (
                1024 * 1024
            )
        )

        st.download_button(
            label=(
                f"📦 {arquivo['nome']} "
                f"— {tamanho_mb:.2f} MB"
            ),

            data=arquivo["dados"],

            file_name=arquivo["nome"],

            mime="application/zip",

            use_container_width=True
        )

    # ========================================================
    # RESTANTE
    # ========================================================

    st.divider()

    st.subheader(
        "📄 Arquivos restantes"
    )

    pdf_sem_comprovantes = st.session_state.get(
        "pdf_sem_comprovantes"
    )

    quantidade_restante = st.session_state.get(
        "paginas_sem_comprovante",
        0
    )

    if pdf_sem_comprovantes:

        tamanho_mb = (
            len(
                pdf_sem_comprovantes
            )
            / (
                1024 * 1024
            )
        )

        st.warning(
            f"⚠️ {quantidade_restante} "
            f"página(s) não foram identificadas "
            f"como comprovantes."
        )

        st.download_button(
            label=(
                f"📄 Baixar páginas restantes "
                f"— {tamanho_mb:.2f} MB"
            ),

            data=pdf_sem_comprovantes,

            file_name="paginas_sem_comprovantes.pdf",

            mime="application/pdf",

            use_container_width=True
        )

    else:

        st.success(
            "✅ Não existem páginas restantes."
        )
