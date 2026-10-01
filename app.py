import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile
import unicodedata
import re


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LIMITE_ZIP = 10 * 1024 * 1024  # 10 MB


# ============================================================
# NORMALIZA TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper()

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


# ============================================================
# IDENTIFICA O TIPO DO COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # ========================================================
    # 1 - COMPROVANTE PIX
    # ========================================================

    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # ========================================================
    # 2 - COMPROVANTE DE TRANSFERENCIA
    # ========================================================

    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # ========================================================
    # 3 - COMPROVANTE DE TRANSACAO BANCARIA
    # ========================================================

    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# CRIA PDF DE UMA ÚNICA PÁGINA
# ============================================================

def criar_pdf_pagina(reader, numero_pagina):

    writer = PdfWriter()

    # IMPORTANTE:
    # SOMENTE ESTA PÁGINA SERÁ EXTRAÍDA
    writer.add_page(
        reader.pages[numero_pagina]
    )

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# PROCESSA O PDF
# ============================================================

def processar_pdf(arquivo):

    reader = PdfReader(arquivo)

    comprovantes = []

    demais_paginas = []

    # ========================================================
    # PERCORRE TODAS AS PÁGINAS
    # ========================================================

    for numero_pagina, pagina in enumerate(
        reader.pages
    ):

        try:

            texto = pagina.extract_text() or ""

        except Exception:

            texto = ""

        tipo = identificar_comprovante(texto)

        # ====================================================
        # É COMPROVANTE
        # ====================================================

        if tipo:

            comprovantes.append({
                "pagina": numero_pagina,
                "tipo": tipo
            })

        # ====================================================
        # NÃO É COMPROVANTE
        # ====================================================

        else:

            demais_paginas.append(
                numero_pagina
            )

    return (
        reader,
        comprovantes,
        demais_paginas
    )


# ============================================================
# CRIA ZIP
# ============================================================

def gerar_zip(arquivos):

    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6
    ) as zip_file:

        for nome, dados in arquivos:

            zip_file.writestr(
                nome,
                dados
            )

    return buffer.getvalue()


# ============================================================
# DIVIDE EM ZIPS DE ATÉ 10 MB
# ============================================================

def dividir_em_zips(
    arquivos,
    prefixo
):

    resultado = []

    arquivos_atual = []

    numero_zip = 1

    for nome, dados in arquivos:

        # ----------------------------------------------------
        # Verifica tamanho do arquivo sozinho
        # ----------------------------------------------------

        zip_individual = gerar_zip([
            (nome, dados)
        ])

        # ----------------------------------------------------
        # Se o próprio arquivo já for maior que 10 MB
        # ----------------------------------------------------

        if len(zip_individual) > LIMITE_ZIP:

            # Fecha o ZIP atual
            if arquivos_atual:

                dados_zip = gerar_zip(
                    arquivos_atual
                )

                nome_zip = (
                    f"{prefixo}_{numero_zip:03d}.zip"
                )

                resultado.append(
                    (
                        nome_zip,
                        dados_zip
                    )
                )

                numero_zip += 1

                arquivos_atual = []

            # Coloca o arquivo sozinho
            nome_zip = (
                f"{prefixo}_{numero_zip:03d}.zip"
            )

            resultado.append(
                (
                    nome_zip,
                    zip_individual
                )
            )

            numero_zip += 1

            continue

        # ----------------------------------------------------
        # Testa adicionar ao ZIP atual
        # ----------------------------------------------------

        tentativa = (
            arquivos_atual
            + [(nome, dados)]
        )

        zip_teste = gerar_zip(
            tentativa
        )

        # ----------------------------------------------------
        # Cabe no limite
        # ----------------------------------------------------

        if len(zip_teste) <= LIMITE_ZIP:

            arquivos_atual.append(
                (nome, dados)
            )

        # ----------------------------------------------------
        # Ultrapassou 10 MB
        # ----------------------------------------------------

        else:

            if arquivos_atual:

                dados_zip = gerar_zip(
                    arquivos_atual
                )

                nome_zip = (
                    f"{prefixo}_{numero_zip:03d}.zip"
                )

                resultado.append(
                    (
                        nome_zip,
                        dados_zip
                    )
                )

                numero_zip += 1

            # Começa novo ZIP
            arquivos_atual = [
                (nome, dados)
            ]

    # --------------------------------------------------------
    # Fecha último ZIP
    # --------------------------------------------------------

    if arquivos_atual:

        dados_zip = gerar_zip(
            arquivos_atual
        )

        nome_zip = (
            f"{prefixo}_{numero_zip:03d}.zip"
        )

        resultado.append(
            (
                nome_zip,
                dados_zip
            )
        )

    return resultado


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Extrator de Comprovantes",
    page_icon="📄",
    layout="centered"
)


# ============================================================
# TÍTULO
# ============================================================

st.title(
    "📄 Extrator de Comprovantes"
)

st.write(
    "O sistema identifica somente as páginas que possuem "
    "uma das três nomenclaturas de comprovante."
)


# ============================================================
# NOMENCLATURAS
# ============================================================

with st.expander(
    "🔎 Nomenclaturas identificadas"
):

    st.write(
        "1. COMPROVANTE PIX"
    )

    st.write(
        "2. COMPROVANTE DE TRANSFERENCIA"
    )

    st.write(
        "3. COMPROVANTE DE TRANSACAO BANCARIA"
    )


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo is not None:

    if st.button(
        "🔎 Processar PDF",
        type="primary"
    ):

        with st.spinner(
            "Analisando as páginas..."
        ):

            try:

                (
                    reader,
                    comprovantes,
                    demais_paginas
                ) = processar_pdf(
                    arquivo
                )

                # =================================================
                # CONTADORES
                # =================================================

                contadores = {
                    "PIX": 0,
                    "TRANSFERENCIA": 0,
                    "TRANSACAO_BANCARIA": 0
                }

                arquivos_comprovantes = []

                # =================================================
                # CRIA OS COMPROVANTES
                # =================================================

                for comprovante in comprovantes:

                    pagina = comprovante[
                        "pagina"
                    ]

                    tipo = comprovante[
                        "tipo"
                    ]

                    contadores[tipo] += 1

                    numero = contadores[tipo]

                    dados = criar_pdf_pagina(
                        reader,
                        pagina
                    )

                    nome = (
                        f"{tipo}_{numero:04d}.pdf"
                    )

                    arquivos_comprovantes.append(
                        (
                            nome,
                            dados
                        )
                    )

                # =================================================
                # CRIA OS DEMAIS ARQUIVOS
                # =================================================

                arquivos_demais = []

                for indice, pagina in enumerate(
                    demais_paginas,
                    start=1
                ):

                    dados = criar_pdf_pagina(
                        reader,
                        pagina
                    )

                    nome = (
                        f"PAGINA_{indice:04d}.pdf"
                    )

                    arquivos_demais.append(
                        (
                            nome,
                            dados
                        )
                    )

                # =================================================
                # ZIP DOS COMPROVANTES
                # =================================================

                zips_comprovantes = dividir_em_zips(
                    arquivos_comprovantes,
                    "COMPROVANTES"
                )

                # =================================================
                # ZIP DOS DEMAIS
                # =================================================

                zips_demais = dividir_em_zips(
                    arquivos_demais,
                    "SEM_COMPROVANTES"
                )

                # =================================================
                # SALVA NO SESSION STATE
                # =================================================

                st.session_state[
                    "processado"
                ] = True

                st.session_state[
                    "zips_comprovantes"
                ] = zips_comprovantes

                st.session_state[
                    "zips_demais"
                ] = zips_demais

                st.session_state[
                    "total_comprovantes"
                ] = len(comprovantes)

                st.session_state[
                    "total_demais"
                ] = len(demais_paginas)

                st.session_state[
                    "contadores"
                ] = contadores

            except Exception as erro:

                st.error(
                    f"Erro ao processar o PDF: {erro}"
                )


# ============================================================
# RESULTADO
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    st.success(
        "✅ Processamento concluído!"
    )

    # ========================================================
    # RESUMO
    # ========================================================

    st.subheader(
        "📊 Resumo"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Total de comprovantes",
            st.session_state[
                "total_comprovantes"
            ]
        )

    with col2:

        st.metric(
            "Demais páginas",
            st.session_state[
                "total_demais"
            ]
        )

    # ========================================================
    # TIPOS
    # ========================================================

    st.subheader(
        "📋 Comprovantes encontrados"
    )

    contadores = st.session_state[
        "contadores"
    ]

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "PIX",
            contadores["PIX"]
        )

    with col2:

        st.metric(
            "Transferência",
            contadores["TRANSFERENCIA"]
        )

    with col3:

        st.metric(
            "Transação bancária",
            contadores[
                "TRANSACAO_BANCARIA"
            ]
        )

    # ========================================================
    # DOWNLOAD COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📦 1. ZIPs dos comprovantes"
    )

    zips_comprovantes = (
        st.session_state[
            "zips_comprovantes"
        ]
    )

    if zips_comprovantes:

        for nome_zip, dados_zip in (
            zips_comprovantes
        ):

            tamanho_mb = (
                len(dados_zip)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome_zip} "
                    f"— {tamanho_mb:.2f} MB"
                ),
                data=dados_zip,
                file_name=nome_zip,
                mime="application/zip",
                key=f"download_comp_{nome_zip}"
            )

    else:

        st.warning(
            "Nenhum comprovante encontrado."
        )

    # ========================================================
    # DOWNLOAD DEMAIS
    # ========================================================

    st.divider()

    st.subheader(
        "📁 2. ZIPs sem comprovantes"
    )

    zips_demais = (
        st.session_state[
            "zips_demais"
        ]
    )

    if zips_demais:

        for nome_zip, dados_zip in (
            zips_demais
        ):

            tamanho_mb = (
                len(dados_zip)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome_zip} "
                    f"— {tamanho_mb:.2f} MB"
                ),
                data=dados_zip,
                file_name=nome_zip,
                mime="application/zip",
                key=f"download_demais_{nome_zip}"
            )

    else:

        st.success(
            "Não existem outras páginas para separar."
        )
