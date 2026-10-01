import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile
import unicodedata
import re


# ============================================================
# CONFIGURAÇÃO
# ============================================================

LIMITE_ZIP = 10 * 1024 * 1024  # 10 MB


# ============================================================
# NORMALIZAÇÃO
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
# IDENTIFICA COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # 1. COMPROVANTE PIX
    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # 2. COMPROVANTE DE TRANSFERENCIA
    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # 3. COMPROVANTE DE TRANSACAO BANCARIA
    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# CRIA PDF COM UMA ÚNICA PÁGINA
# ============================================================

def criar_pdf_pagina(reader, numero_pagina):

    writer = PdfWriter()

    # Somente esta página
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
    sem_comprovantes = []

    for numero_pagina, pagina in enumerate(
        reader.pages
    ):

        try:
            texto = pagina.extract_text() or ""
        except Exception:
            texto = ""

        tipo = identificar_comprovante(texto)

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo:

            comprovantes.append({
                "pagina": numero_pagina,
                "tipo": tipo
            })

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            sem_comprovantes.append(
                numero_pagina
            )

    return (
        reader,
        comprovantes,
        sem_comprovantes
    )


# ============================================================
# CRIA ZIP
# ============================================================

def criar_zip(lista_arquivos):

    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6
    ) as zip_file:

        for nome, dados in lista_arquivos:

            zip_file.writestr(
                nome,
                dados
            )

    return buffer.getvalue()


# ============================================================
# AGRUPA PDFs EM ZIPS DE ATÉ 10 MB
# ============================================================

def agrupar_em_zips(
    arquivos,
    prefixo
):

    resultado = []

    grupo_atual = []

    numero_zip = 1

    for nome, dados in arquivos:

        # ====================================================
        # TESTA O ARQUIVO SOZINHO
        # ====================================================

        zip_individual = criar_zip([
            (nome, dados)
        ])

        # ====================================================
        # ARQUIVO INDIVIDUAL MAIOR QUE 10 MB
        # ====================================================

        if len(zip_individual) > LIMITE_ZIP:

            # Fecha o grupo anterior
            if grupo_atual:

                zip_bytes = criar_zip(
                    grupo_atual
                )

                nome_zip = (
                    f"{prefixo}_{numero_zip:03d}.zip"
                )

                resultado.append(
                    (
                        nome_zip,
                        zip_bytes
                    )
                )

                numero_zip += 1

                grupo_atual = []

            # Coloca o arquivo grande sozinho
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

        # ====================================================
        # TESTA O GRUPO + NOVO PDF
        # ====================================================

        tentativa = (
            grupo_atual
            + [(nome, dados)]
        )

        zip_teste = criar_zip(
            tentativa
        )

        # ====================================================
        # SE COUBER NOS 10 MB
        # ====================================================

        if len(zip_teste) <= LIMITE_ZIP:

            grupo_atual.append(
                (nome, dados)
            )

        # ====================================================
        # SE PASSAR DOS 10 MB
        # ====================================================

        else:

            # Fecha o ZIP atual
            if grupo_atual:

                zip_bytes = criar_zip(
                    grupo_atual
                )

                nome_zip = (
                    f"{prefixo}_{numero_zip:03d}.zip"
                )

                resultado.append(
                    (
                        nome_zip,
                        zip_bytes
                    )
                )

                numero_zip += 1

            # Começa novo grupo com o arquivo atual
            grupo_atual = [
                (nome, dados)
            ]

    # ========================================================
    # FECHA ÚLTIMO GRUPO
    # ========================================================

    if grupo_atual:

        zip_bytes = criar_zip(
            grupo_atual
        )

        nome_zip = (
            f"{prefixo}_{numero_zip:03d}.zip"
        )

        resultado.append(
            (
                nome_zip,
                zip_bytes
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


st.title(
    "📄 Extrator de Comprovantes"
)

st.write(
    "O sistema identifica os comprovantes e agrupa os "
    "PDFs em arquivos ZIP de até 10 MB."
)


# ============================================================
# NOMENCLATURAS
# ============================================================

with st.expander(
    "🔎 Nomenclaturas utilizadas"
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
            "Processando PDF..."
        ):

            try:

                (
                    reader,
                    comprovantes,
                    paginas_sem_comprovante
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

                # =================================================
                # LISTA DOS PDFs DE COMPROVANTES
                # =================================================

                arquivos_comprovantes = []

                for comprovante in comprovantes:

                    pagina = comprovante[
                        "pagina"
                    ]

                    tipo = comprovante[
                        "tipo"
                    ]

                    contadores[tipo] += 1

                    numero = contadores[tipo]

                    pdf_bytes = criar_pdf_pagina(
                        reader,
                        pagina
                    )

                    nome_pdf = (
                        f"{tipo}_{numero:04d}.pdf"
                    )

                    arquivos_comprovantes.append(
                        (
                            nome_pdf,
                            pdf_bytes
                        )
                    )

                # =================================================
                # LISTA DOS PDFs SEM COMPROVANTES
                # =================================================

                arquivos_sem_comprovantes = []

                for indice, pagina in enumerate(
                    paginas_sem_comprovante,
                    start=1
                ):

                    pdf_bytes = criar_pdf_pagina(
                        reader,
                        pagina
                    )

                    nome_pdf = (
                        f"PAGINA_{indice:04d}.pdf"
                    )

                    arquivos_sem_comprovantes.append(
                        (
                            nome_pdf,
                            pdf_bytes
                        )
                    )

                # =================================================
                # AGRUPAR COMPROVANTES
                # =================================================

                zips_comprovantes = agrupar_em_zips(
                    arquivos_comprovantes,
                    "COMPROVANTES"
                )

                # =================================================
                # AGRUPAR SEM COMPROVANTES
                # =================================================

                zips_sem_comprovantes = agrupar_em_zips(
                    arquivos_sem_comprovantes,
                    "SEM_COMPROVANTES"
                )

                # =================================================
                # SALVAR RESULTADOS
                # =================================================

                st.session_state[
                    "processado"
                ] = True

                st.session_state[
                    "zips_comprovantes"
                ] = zips_comprovantes

                st.session_state[
                    "zips_sem_comprovantes"
                ] = zips_sem_comprovantes

                st.session_state[
                    "total_comprovantes"
                ] = len(comprovantes)

                st.session_state[
                    "total_sem_comprovantes"
                ] = len(
                    paginas_sem_comprovante
                )

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

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Comprovantes",
            st.session_state[
                "total_comprovantes"
            ]
        )

    with col2:

        st.metric(
            "Sem comprovantes",
            st.session_state[
                "total_sem_comprovantes"
            ]
        )

    with col3:

        total_zips = (
            len(
                st.session_state[
                    "zips_comprovantes"
                ]
            )
            +
            len(
                st.session_state[
                    "zips_sem_comprovantes"
                ]
            )
        )

        st.metric(
            "Total de ZIPs",
            total_zips
        )

    # ========================================================
    # TIPOS
    # ========================================================

    st.subheader(
        "📋 Tipos de comprovantes"
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
    # COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📦 ZIPs com comprovantes"
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
                    f"({tamanho_mb:.2f} MB)"
                ),
                data=dados_zip,
                file_name=nome_zip,
                mime="application/zip",
                key=f"comp_{nome_zip}"
            )

    else:

        st.warning(
            "Nenhum comprovante encontrado."
        )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 ZIPs sem comprovantes"
    )

    zips_sem_comprovantes = (
        st.session_state[
            "zips_sem_comprovantes"
        ]
    )

    if zips_sem_comprovantes:

        for nome_zip, dados_zip in (
            zips_sem_comprovantes
        ):

            tamanho_mb = (
                len(dados_zip)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome_zip} "
                    f"({tamanho_mb:.2f} MB)"
                ),
                data=dados_zip,
                file_name=nome_zip,
                mime="application/zip",
                key=f"sem_{nome_zip}"
            )

    else:

        st.success(
            "Não existem páginas sem comprovantes."
        )
