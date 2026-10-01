import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import unicodedata
import re


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LIMITE_MB = 10
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# NORMALIZAÇÃO DO TEXTO
# ============================================================

def normalizar_texto(texto):

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
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICA SE A PÁGINA É UM COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # COMPROVANTE PIX
    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # COMPROVANTE DE TRANSFERENCIA
    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # COMPROVANTE DE TRANSACAO BANCARIA
    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# IDENTIFICA O INÍCIO DO ANEXO
# ============================================================

def identificar_anexo(texto):

    texto_normalizado = normalizar_texto(texto)

    # Procura a palavra ANEXO
    if re.search(r"\bANEXO\b", texto_normalizado):
        return True

    return False


# ============================================================
# GERA UM PDF A PARTIR DE UMA LISTA DE PÁGINAS
# ============================================================

def gerar_pdf(reader, paginas):

    writer = PdfWriter()

    for numero_pagina in paginas:

        writer.add_page(
            reader.pages[numero_pagina]
        )

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# AGRUPA AS PÁGINAS ATÉ O LIMITE DE 10 MB
# ============================================================

def agrupar_paginas(reader, paginas, prefixo):

    arquivos = []

    paginas_atual = []

    numero_arquivo = 1

    for numero_pagina in paginas:

        # ----------------------------------------------------
        # Testa como ficaria o PDF adicionando esta página
        # ----------------------------------------------------

        paginas_teste = (
            paginas_atual +
            [numero_pagina]
        )

        pdf_teste = gerar_pdf(
            reader,
            paginas_teste
        )

        tamanho_teste = len(
            pdf_teste
        )

        # ----------------------------------------------------
        # Se couber em 10 MB, adiciona
        # ----------------------------------------------------

        if tamanho_teste <= LIMITE_BYTES:

            paginas_atual.append(
                numero_pagina
            )

        else:

            # ------------------------------------------------
            # Salva o grupo anterior
            # ------------------------------------------------

            if paginas_atual:

                pdf_final = gerar_pdf(
                    reader,
                    paginas_atual
                )

                nome_arquivo = (
                    f"{prefixo}_"
                    f"{numero_arquivo:03d}.pdf"
                )

                arquivos.append(
                    (
                        nome_arquivo,
                        pdf_final
                    )
                )

                numero_arquivo += 1

            # ------------------------------------------------
            # Verifica se a página sozinha já passa de 10 MB
            # ------------------------------------------------

            pdf_pagina = gerar_pdf(
                reader,
                [numero_pagina]
            )

            tamanho_pagina = len(
                pdf_pagina
            )

            if tamanho_pagina > LIMITE_BYTES:

                # --------------------------------------------
                # Página maior que 10 MB.
                # Não há como dividir uma página PDF.
                # --------------------------------------------

                nome_arquivo = (
                    f"{prefixo}_"
                    f"{numero_arquivo:03d}_"
                    f"ACIMA_DE_10MB.pdf"
                )

                arquivos.append(
                    (
                        nome_arquivo,
                        pdf_pagina
                    )
                )

                numero_arquivo += 1

                paginas_atual = []

            else:

                # --------------------------------------------
                # Começa um novo grupo
                # --------------------------------------------

                paginas_atual = [
                    numero_pagina
                ]

    # --------------------------------------------------------
    # Salva o último grupo
    # --------------------------------------------------------

    if paginas_atual:

        pdf_final = gerar_pdf(
            reader,
            paginas_atual
        )

        nome_arquivo = (
            f"{prefixo}_"
            f"{numero_arquivo:03d}.pdf"
        )

        arquivos.append(
            (
                nome_arquivo,
                pdf_final
            )
        )

    return arquivos


# ============================================================
# PROCESSA O PDF
# ============================================================

def processar_pdf(arquivo):

    reader = PdfReader(arquivo)

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    contadores = {
        "PIX": 0,
        "TRANSFERENCIA": 0,
        "TRANSACAO_BANCARIA": 0
    }

    encontrou_anexo = False

    # ========================================================
    # PERCORRE AS PÁGINAS
    # ========================================================

    for numero_pagina, pagina in enumerate(
        reader.pages
    ):

        try:

            texto = pagina.extract_text() or ""

        except Exception:

            texto = ""

        # ====================================================
        # PROCURA O INÍCIO DO ANEXO
        # ====================================================

        if not encontrou_anexo:

            if identificar_anexo(texto):

                encontrou_anexo = True

            # Não inclui a própria página do ANEXO
            continue

        # ====================================================
        # IDENTIFICA O TIPO DA PÁGINA
        # ====================================================

        tipo = identificar_comprovante(
            texto
        )

        # ====================================================
        # É COMPROVANTE
        # ====================================================

        if tipo:

            paginas_comprovantes.append(
                numero_pagina
            )

            contadores[tipo] += 1

        # ====================================================
        # NÃO É COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

    # ========================================================
    # AGRUPA COMPROVANTES EM PDFs DE ATÉ 10 MB
    # ========================================================

    arquivos_comprovantes = agrupar_paginas(
        reader,
        paginas_comprovantes,
        "COMPROVANTES"
    )

    # ========================================================
    # AGRUPA OS DEMAIS ARQUIVOS EM PDFs DE ATÉ 10 MB
    # ========================================================

    arquivos_sem_comprovantes = agrupar_paginas(
        reader,
        paginas_sem_comprovantes,
        "SEM_COMPROVANTES"
    )

    return (
        arquivos_comprovantes,
        arquivos_sem_comprovantes,
        contadores,
        encontrou_anexo
    )


# ============================================================
# TELA
# ============================================================

st.title(
    "📄 Separador e Agrupador de Comprovantes"
)

st.write(
    "O sistema procura o ANEXO, identifica os comprovantes "
    "e agrupa as páginas em PDFs de até 10 MB."
)


# ============================================================
# INFORMAÇÕES
# ============================================================

with st.expander(
    "🔎 Critérios utilizados"
):

    st.write(
        "O sistema identifica exatamente estas nomenclaturas:"
    )

    st.write(
        "• COMPROVANTE PIX"
    )

    st.write(
        "• COMPROVANTE DE TRANSFERENCIA"
    )

    st.write(
        "• COMPROVANTE DE TRANSACAO BANCARIA"
    )

    st.write(
        "As páginas são agrupadas em PDFs de no máximo 10 MB."
    )


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# BOTÃO PROCESSAR
# ============================================================

if arquivo is not None:

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Processando o PDF e agrupando as páginas..."
        ):

            try:

                (
                    arquivos_comprovantes,
                    arquivos_sem_comprovantes,
                    contadores,
                    encontrou_anexo
                ) = processar_pdf(
                    arquivo
                )

                # --------------------------------------------
                # SALVA NO SESSION STATE
                # --------------------------------------------

                st.session_state[
                    "processado"
                ] = True

                st.session_state[
                    "arquivos_comprovantes"
                ] = arquivos_comprovantes

                st.session_state[
                    "arquivos_sem_comprovantes"
                ] = arquivos_sem_comprovantes

                st.session_state[
                    "contadores"
                ] = contadores

                st.session_state[
                    "encontrou_anexo"
                ] = encontrou_anexo

            except Exception as erro:

                st.error(
                    f"Erro ao processar o PDF: {erro}"
                )

                st.exception(erro)


# ============================================================
# EXIBE RESULTADO
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    arquivos_comprovantes = (
        st.session_state[
            "arquivos_comprovantes"
        ]
    )

    arquivos_sem_comprovantes = (
        st.session_state[
            "arquivos_sem_comprovantes"
        ]
    )

    contadores = (
        st.session_state[
            "contadores"
        ]
    )

    encontrou_anexo = (
        st.session_state[
            "encontrou_anexo"
        ]
    )

    # ========================================================
    # VERIFICA ANEXO
    # ========================================================

    if not encontrou_anexo:

        st.warning(
            "⚠️ A palavra ANEXO não foi encontrada no PDF."
        )

    else:

        st.success(
            "✅ ANEXO localizado e processado."
        )

    # ========================================================
    # RESUMO
    # ========================================================

    total_comprovantes = sum(
        contadores.values()
    )

    col1, col2, col3, col4 = st.columns(4)

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

    with col4:

        st.metric(
            "Total",
            total_comprovantes
        )

    # ========================================================
    # COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📦 Comprovantes agrupados"
    )

    if arquivos_comprovantes:

        st.write(
            f"{len(arquivos_comprovantes)} "
            "arquivo(s) gerado(s)."
        )

        for nome, dados in (
            arquivos_comprovantes
        ):

            tamanho_mb = (
                len(dados)
                / (1024 * 1024)
            )

            if (
                "ACIMA_DE_10MB"
                in nome
            ):

                st.warning(
                    f"⚠️ {nome} — "
                    f"{tamanho_mb:.2f} MB"
                )

            else:

                st.write(
                    f"📄 {nome} — "
                    f"{tamanho_mb:.2f} MB"
                )

            st.download_button(
                label=f"⬇️ Baixar {nome}",
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"download_comprovante_{nome}",
                use_container_width=True
            )

    else:

        st.info(
            "Nenhum comprovante foi encontrado."
        )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 Páginas sem comprovantes agrupadas"
    )

    if arquivos_sem_comprovantes:

        st.write(
            f"{len(arquivos_sem_comprovantes)} "
            "arquivo(s) gerado(s)."
        )

        for nome, dados in (
            arquivos_sem_comprovantes
        ):

            tamanho_mb = (
                len(dados)
                / (1024 * 1024)
            )

            if (
                "ACIMA_DE_10MB"
                in nome
            ):

                st.warning(
                    f"⚠️ {nome} — "
                    f"{tamanho_mb:.2f} MB"
                )

            else:

                st.write(
                    f"📄 {nome} — "
                    f"{tamanho_mb:.2f} MB"
                )

            st.download_button(
                label=f"⬇️ Baixar {nome}",
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"download_sem_comprovante_{nome}",
                use_container_width=True
            )

    else:

        st.success(
            "Não existem páginas sem comprovantes."
        )
