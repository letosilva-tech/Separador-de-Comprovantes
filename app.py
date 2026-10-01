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
# NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICAR ANEXO
# ============================================================

def identificar_anexo(texto):

    texto = normalizar_texto(texto)

    # Procura ANEXO isoladamente
    if re.search(r"\bANEXO\b", texto):
        return True

    return False


# ============================================================
# IDENTIFICAR COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # --------------------------------------------------------
    # PIX
    # --------------------------------------------------------

    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # --------------------------------------------------------
    # TRANSFERÊNCIA
    # --------------------------------------------------------

    if (
        "COMPROVANTE DE TRANSFERENCIA" in texto
        or
        "COMPROVANTE TRANSFERENCIA" in texto
    ):
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    if (
        "COMPROVANTE DE TRANSACAO BANCARIA" in texto
        or
        "COMPROVANTE TRANSACAO BANCARIA" in texto
    ):
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# CRIAR PDF COM UMA ÚNICA PÁGINA
# ============================================================

def criar_pdf_pagina(reader, numero_pagina):

    writer = PdfWriter()

    # SOMENTE A PÁGINA DO COMPROVANTE
    writer.add_page(
        reader.pages[numero_pagina]
    )

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# CRIAR PDF DE UMA PÁGINA NÃO COMPROVANTE
# ============================================================

def criar_pdf_pagina_sem_comprovante(
    reader,
    numero_pagina
):

    writer = PdfWriter()

    writer.add_page(
        reader.pages[numero_pagina]
    )

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# CRIAR ZIP
# ============================================================

def gerar_zip(arquivos):

    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
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
# DIVIDIR ARQUIVOS EM ZIPS DE ATÉ 10 MB
# ============================================================

def dividir_em_zips(
    arquivos,
    prefixo
):

    zips = []

    arquivos_atual = []

    numero_zip = 1

    for nome, dados in arquivos:

        # ----------------------------------------------------
        # Testa o arquivo sozinho
        # ----------------------------------------------------

        zip_individual = gerar_zip([
            (nome, dados)
        ])

        # ----------------------------------------------------
        # Se o próprio arquivo ultrapassar 10 MB
        # ----------------------------------------------------

        if len(zip_individual) > LIMITE_ZIP:

            # Fecha o ZIP atual
            if arquivos_atual:

                zip_bytes = gerar_zip(
                    arquivos_atual
                )

                nome_zip = (
                    f"{prefixo}_{numero_zip:03d}.zip"
                )

                zips.append(
                    (
                        nome_zip,
                        zip_bytes
                    )
                )

                numero_zip += 1

                arquivos_atual = []

            # Arquivo grande fica sozinho
            nome_zip = (
                f"{prefixo}_{numero_zip:03d}.zip"
            )

            zips.append(
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
        # Cabe no ZIP
        # ----------------------------------------------------

        if len(zip_teste) <= LIMITE_ZIP:

            arquivos_atual.append(
                (nome, dados)
            )

        # ----------------------------------------------------
        # Não cabe
        # ----------------------------------------------------

        else:

            if arquivos_atual:

                zip_bytes = gerar_zip(
                    arquivos_atual
                )

                nome_zip = (
                    f"{prefixo}_{numero_zip:03d}.zip"
                )

                zips.append(
                    (
                        nome_zip,
                        zip_bytes
                    )
                )

                numero_zip += 1

            # Começa novo ZIP
            arquivos_atual = [
                (nome, dados)
            ]

    # --------------------------------------------------------
    # Último ZIP
    # --------------------------------------------------------

    if arquivos_atual:

        zip_bytes = gerar_zip(
            arquivos_atual
        )

        nome_zip = (
            f"{prefixo}_{numero_zip:03d}.zip"
        )

        zips.append(
            (
                nome_zip,
                zip_bytes
            )
        )

    return zips


# ============================================================
# PROCESSAR PDF
# ============================================================

def processar_pdf(arquivo):

    reader = PdfReader(arquivo)

    comprovantes = []

    sem_comprovantes = []

    encontrou_anexo = False

    # ========================================================
    # PERCORRER PÁGINAS
    # ========================================================

    for numero_pagina, pagina in enumerate(
        reader.pages
    ):

        try:

            texto = pagina.extract_text() or ""

        except Exception:

            texto = ""

        # ----------------------------------------------------
        # ANTES DO ANEXO
        # ----------------------------------------------------

        if not encontrou_anexo:

            if identificar_anexo(texto):

                encontrou_anexo = True

                # A página do título "ANEXO" não é
                # considerada comprovante.
                # Portanto, não adicionamos aqui.

            continue

        # ----------------------------------------------------
        # DENTRO DO ANEXO
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        # ====================================================
        # É COMPROVANTE
        # ====================================================

        if tipo:

            comprovantes.append({
                "tipo": tipo,
                "pagina": numero_pagina
            })

        # ====================================================
        # NÃO É COMPROVANTE
        # ====================================================

        else:

            sem_comprovantes.append(
                numero_pagina
            )

    return (
        reader,
        comprovantes,
        sem_comprovantes,
        encontrou_anexo
    )


# ============================================================
# CONFIGURAÇÃO STREAMLIT
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
    "O sistema irá analisar somente o conteúdo "
    "do **Anexo**, separar os comprovantes das "
    "demais páginas e criar arquivos ZIP de até 10 MB."
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
            "Processando o PDF..."
        ):

            try:

                (
                    reader,
                    comprovantes,
                    paginas_sem_comprovante,
                    encontrou_anexo
                ) = processar_pdf(
                    arquivo
                )

                # ============================================
                # ANEXO NÃO ENCONTRADO
                # ============================================

                if not encontrou_anexo:

                    st.error(
                        "Não foi encontrada uma página "
                        "com a identificação 'ANEXO'."
                    )

                    st.stop()

                # ============================================
                # ARQUIVOS DOS COMPROVANTES
                # ============================================

                arquivos_comprovantes = []

                contadores = {
                    "PIX": 0,
                    "TRANSFERENCIA": 0,
                    "TRANSACAO_BANCARIA": 0
                }

                for comprovante in comprovantes:

                    tipo = comprovante[
                        "tipo"
                    ]

                    pagina = comprovante[
                        "pagina"
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

                # ============================================
                # ARQUIVOS SEM COMPROVANTE
                # ============================================

                arquivos_sem_comprovante = []

                for indice, pagina in enumerate(
                    paginas_sem_comprovante,
                    start=1
                ):

                    dados = (
                        criar_pdf_pagina_sem_comprovante(
                            reader,
                            pagina
                        )
                    )

                    nome = (
                        f"PAGINA_SEM_COMPROVANTE_"
                        f"{indice:04d}.pdf"
                    )

                    arquivos_sem_comprovante.append(
                        (
                            nome,
                            dados
                        )
                    )

                # ============================================
                # GERAR ZIPS DOS COMPROVANTES
                # ============================================

                zips_comprovantes = dividir_em_zips(
                    arquivos_comprovantes,
                    "COMPROVANTES"
                )

                # ============================================
                # GERAR ZIPS SEM COMPROVANTES
                # ============================================

                zips_sem_comprovantes = dividir_em_zips(
                    arquivos_sem_comprovante,
                    "SEM_COMPROVANTES"
                )

                # ============================================
                # SALVAR RESULTADO
                # ============================================

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
                    f"Erro ao processar o arquivo: {erro}"
                )


# ============================================================
# RESULTADOS
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    # ========================================================
    # RESUMO
    # ========================================================

    st.success(
        "✅ Processamento concluído!"
    )

    st.subheader(
        "📊 Resumo"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Comprovantes",
            st.session_state[
                "total_comprovantes"
            ]
        )

    with col2:

        st.metric(
            "Páginas sem comprovante",
            st.session_state[
                "total_sem_comprovantes"
            ]
        )

    # ========================================================
    # TIPOS
    # ========================================================

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
            "Transferências",
            contadores["TRANSFERENCIA"]
        )

    with col3:

        st.metric(
            "Transações bancárias",
            contadores[
                "TRANSACAO_BANCARIA"
            ]
        )

    st.divider()

    # ========================================================
    # COMPROVANTES
    # ========================================================

    st.subheader(
        "📦 ZIPs dos comprovantes"
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

            tamanho = (
                len(dados_zip)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome_zip} "
                    f"({tamanho:.2f} MB)"
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

            tamanho = (
                len(dados_zip)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome_zip} "
                    f"({tamanho:.2f} MB)"
                ),
                data=dados_zip,
                file_name=nome_zip,
                mime="application/zip",
                key=f"sem_{nome_zip}"
            )

    else:

        st.success(
            "Não existem páginas sem comprovante "
            "dentro do Anexo."
        )
