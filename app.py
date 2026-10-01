```python
import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import unicodedata
import re


# ============================================================
# CONFIGURAÇÃO
# ============================================================

LIMITE_MB = 10
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


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
# IDENTIFICA O COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # --------------------------------------------------------
    # 1 - PIX
    # --------------------------------------------------------

    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # --------------------------------------------------------
    # 2 - TRANSFERÊNCIA
    # --------------------------------------------------------

    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # 3 - TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# CRIA PDF COM AS PÁGINAS RECEBIDAS
# ============================================================

def gerar_pdf(reader, paginas):

    writer = PdfWriter()

    for pagina in paginas:

        writer.add_page(
            reader.pages[pagina]
        )

    buffer = BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


# ============================================================
# AGRUPA PÁGINAS ATÉ 10 MB
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    prefixo,
    progress_bar=None,
    status_box=None,
    etapa_atual=0,
    total_etapas=1
):

    arquivos = []

    paginas_atual = []

    numero_arquivo = 1

    total_paginas = len(paginas)

    if total_paginas == 0:

        if progress_bar:

            progresso = etapa_atual / total_etapas

            progress_bar.progress(
                progresso,
                text=(
                    f"Etapa {etapa_atual}/"
                    f"{total_etapas}"
                )
            )

        return arquivos

    for indice, numero_pagina in enumerate(
        paginas,
        start=1
    ):

        # ----------------------------------------------------
        # Atualiza status
        # ----------------------------------------------------

        if status_box:

            status_box.info(
                f"📦 **Agrupando {prefixo}**\n\n"
                f"📄 Página {indice} de "
                f"{total_paginas}\n\n"
                f"📁 Arquivos criados: "
                f"**{len(arquivos)}**\n\n"
                f"🗂️ Arquivo atual: "
                f"**{numero_arquivo:03d}**"
            )

        # ----------------------------------------------------
        # Testa adicionar a página atual
        # ----------------------------------------------------

        tentativa = paginas_atual + [
            numero_pagina
        ]

        pdf_teste = gerar_pdf(
            reader,
            tentativa
        )

        tamanho_teste = len(
            pdf_teste
        )

        # ----------------------------------------------------
        # A página cabe no PDF atual
        # ----------------------------------------------------

        if tamanho_teste <= LIMITE_BYTES:

            paginas_atual.append(
                numero_pagina
            )

        # ----------------------------------------------------
        # Passou de 10 MB
        # ----------------------------------------------------

        else:

            # -----------------------------------------------
            # Salva o PDF atual
            # -----------------------------------------------

            if paginas_atual:

                pdf_final = gerar_pdf(
                    reader,
                    paginas_atual
                )

                nome = (
                    f"{prefixo}_"
                    f"{numero_arquivo:03d}.pdf"
                )

                arquivos.append(
                    (
                        nome,
                        pdf_final
                    )
                )

                numero_arquivo += 1

            # -----------------------------------------------
            # Começa novo PDF
            # -----------------------------------------------

            paginas_atual = [
                numero_pagina
            ]

            # -----------------------------------------------
            # Se uma única página já tiver mais de 10 MB,
            # ela será mantida sozinha.
            # -----------------------------------------------

            if len(pdf_teste) > LIMITE_BYTES:

                pdf_grande = gerar_pdf(
                    reader,
                    [numero_pagina]
                )

                nome = (
                    f"{prefixo}_"
                    f"{numero_arquivo:03d}.pdf"
                )

                arquivos.append(
                    (
                        nome,
                        pdf_grande
                    )
                )

                numero_arquivo += 1

                paginas_atual = []

        # ----------------------------------------------------
        # Progresso da etapa
        # ----------------------------------------------------

        progresso_etapa = (
            indice / total_paginas
        )

        progresso_total = (
            etapa_atual + progresso_etapa
        ) / total_etapas

        if progress_bar:

            progress_bar.progress(
                progresso_total,
                text=(
                    f"Processamento — "
                    f"{progresso_total:.0%}"
                )
            )

    # --------------------------------------------------------
    # Salva o último PDF
    # --------------------------------------------------------

    if paginas_atual:

        pdf_final = gerar_pdf(
            reader,
            paginas_atual
        )

        nome = (
            f"{prefixo}_"
            f"{numero_arquivo:03d}.pdf"
        )

        arquivos.append(
            (
                nome,
                pdf_final
            )
        )

    return arquivos


# ============================================================
# PROCESSA O PDF
# ============================================================

def processar_pdf(
    arquivo,
    progress_bar,
    status_box
):

    reader = PdfReader(arquivo)

    total_paginas = len(reader.pages)

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    contadores = {
        "PIX": 0,
        "TRANSFERENCIA": 0,
        "TRANSACAO_BANCARIA": 0
    }

    # ========================================================
    # INFORMAÇÕES INICIAIS
    # ========================================================

    status_box.info(
        f"📄 **Arquivo:** {arquivo.name}\n\n"
        f"📑 **Total de páginas:** "
        f"{total_paginas}\n\n"
        "🔎 Preparando análise..."
    )

    progress_bar.progress(
        0,
        text="Preparando processamento..."
    )

    # ========================================================
    # PERCORRE TODAS AS PÁGINAS
    # ========================================================

    for numero_pagina, pagina in enumerate(
        reader.pages,
        start=1
    ):

        # ----------------------------------------------------
        # Extrai texto
        # ----------------------------------------------------

        try:

            texto = pagina.extract_text() or ""

        except Exception:

            texto = ""

        # ----------------------------------------------------
        # Identifica comprovante
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        # ----------------------------------------------------
        # Comprovante encontrado
        # ----------------------------------------------------

        if tipo:

            paginas_comprovantes.append(
                numero_pagina - 1
            )

            contadores[tipo] += 1

        # ----------------------------------------------------
        # Página sem comprovante
        # ----------------------------------------------------

        else:

            paginas_sem_comprovantes.append(
                numero_pagina - 1
            )

        # ----------------------------------------------------
        # Calcula progresso
        # ----------------------------------------------------

        progresso = (
            numero_pagina / total_paginas
        )

        # ----------------------------------------------------
        # Atualiza barra
        # ----------------------------------------------------

        progress_bar.progress(
            progresso * 0.70,
            text=(
                f"🔎 Analisando páginas — "
                f"{numero_pagina}/{total_paginas} "
                f"— {progresso:.0%}"
            )
        )

        # ----------------------------------------------------
        # Atualiza informações
        # ----------------------------------------------------

        status_box.info(
            f"🔎 **Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}**\n\n"

            f"📋 PIX: "
            f"**{contadores['PIX']}**\n\n"

            f"🔄 Transferências: "
            f"**{contadores['TRANSFERENCIA']}**\n\n"

            f"🏦 Transações bancárias: "
            f"**{contadores['TRANSACAO_BANCARIA']}**\n\n"

            f"📁 Sem comprovante: "
            f"**{len(paginas_sem_comprovantes)}**"
        )

    # ========================================================
    # ANÁLISE CONCLUÍDA
    # ========================================================

    total_comprovantes = sum(
        contadores.values()
    )

    status_box.success(
        "✅ **Análise das páginas concluída!**\n\n"

        f"📋 Total de comprovantes: "
        f"**{total_comprovantes}**\n\n"

        f"📄 Páginas sem comprovantes: "
        f"**{len(paginas_sem_comprovantes)}**\n\n"

        "📦 Iniciando agrupamento dos PDFs..."
    )

    # ========================================================
    # AGRUPA COMPROVANTES
    # ========================================================

    arquivos_comprovantes = agrupar_paginas(
        reader,
        paginas_comprovantes,
        "COMPROVANTES",
        progress_bar,
        status_box,
        etapa_atual=1,
        total_etapas=2
    )

    # ========================================================
    # AGRUPA PÁGINAS SEM COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = agrupar_paginas(
        reader,
        paginas_sem_comprovantes,
        "SEM_COMPROVANTES",
        progress_bar,
        status_box,
        etapa_atual=1,
        total_etapas=2
    )

    # ========================================================
    # PROCESSAMENTO FINALIZADO
    # ========================================================

    progress_bar.progress(
        1.0,
        text="✅ Processamento concluído — 100%"
    )

    status_box.success(
        "🎉 **Processamento concluído!**\n\n"

        f"📋 Comprovantes encontrados: "
        f"**{total_comprovantes}**\n\n"

        f"📦 PDFs de comprovantes: "
        f"**{len(arquivos_comprovantes)}**\n\n"

        f"📁 PDFs sem comprovantes: "
        f"**{len(arquivos_sem_comprovantes)}**"
    )

    return (
        arquivos_comprovantes,
        arquivos_sem_comprovantes,
        contadores
    )


# ============================================================
# CONFIGURAÇÃO DO STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Agrupador de Comprovantes",
    page_icon="📄",
    layout="centered"
)


# ============================================================
# TÍTULO
# ============================================================

st.title(
    "📄 Agrupador de Comprovantes"
)

st.write(
    "O sistema separa as páginas de comprovantes das "
    "demais páginas e agrupa cada grupo em PDFs de até "
    "10 MB."
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
# INFORMAÇÃO DO ARQUIVO
# ============================================================

if arquivo is not None:

    tamanho_arquivo_mb = (
        arquivo.size
        / (1024 * 1024)
    )

    st.info(
        f"📄 **Arquivo selecionado:** "
        f"{arquivo.name}\n\n"
        f"💾 **Tamanho:** "
        f"{tamanho_arquivo_mb:.2f} MB"
    )


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo is not None:

    if st.button(
        "🔎 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        # ----------------------------------------------------
        # Limpa processamento anterior
        # ----------------------------------------------------

        st.session_state[
            "processado"
        ] = False

        st.session_state.pop(
            "arquivos_comprovantes",
            None
        )

        st.session_state.pop(
            "arquivos_sem_comprovantes",
            None
        )

        st.session_state.pop(
            "contadores",
            None
        )

        st.session_state.pop(
            "total_comprovantes",
            None
        )

        # ----------------------------------------------------
        # Área de execução
        # ----------------------------------------------------

        st.divider()

        st.subheader(
            "⚙️ Execução do processamento"
        )

        # ----------------------------------------------------
        # Barra de progresso
        # ----------------------------------------------------

        progress_bar = st.progress(
            0,
            text="Preparando processamento..."
        )

        # ----------------------------------------------------
        # Caixa de status
        # ----------------------------------------------------

        status_box = st.empty()

        try:

            # =================================================
            # PROCESSA
            # =================================================

            (
                arquivos_comprovantes,
                arquivos_sem_comprovantes,
                contadores
            ) = processar_pdf(
                arquivo,
                progress_bar,
                status_box
            )

            # =================================================
            # SALVA RESULTADOS
            # =================================================

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
                "total_comprovantes"
            ] = sum(
                contadores.values()
            )

        except Exception as erro:

            status_box.error(
                f"❌ **Erro ao processar o PDF:**\n\n"
                f"{erro}"
            )

            st.exception(erro)


# ============================================================
# RESULTADO
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    st.divider()

    st.success(
        "✅ Processamento concluído!"
    )

    # ========================================================
    # RECUPERA RESULTADOS
    # ========================================================

    contadores = st.session_state[
        "contadores"
    ]

    total_comprovantes = (
        st.session_state[
            "total_comprovantes"
        ]
    )

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

    # ========================================================
    # RESUMO
    # ========================================================

    st.subheader(
        "📊 Resumo da execução"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Total de comprovantes",
            total_comprovantes
        )

    with col2:

        st.metric(
            "Arquivos de comprovantes",
            len(arquivos_comprovantes)
        )

    with col3:

        st.metric(
            "Arquivos sem comprovantes",
            len(arquivos_sem_comprovantes)
        )

    # ========================================================
    # TIPOS
    # ========================================================

    st.subheader(
        "📋 Comprovantes encontrados"
    )

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
        "📦 PDFs com comprovantes"
    )

    if arquivos_comprovantes:

        for nome, dados in (
            arquivos_comprovantes
        ):

            tamanho_mb = (
                len(dados)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome} "
                    f"— {tamanho_mb:.2f} MB"
                ),
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"comp_{nome}",
                use_container_width=True
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
        "📁 PDFs sem comprovantes"
    )

    if arquivos_sem_comprovantes:

        for nome, dados in (
            arquivos_sem_comprovantes
        ):

            tamanho_mb = (
                len(dados)
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"⬇️ {nome} "
                    f"— {tamanho_mb:.2f} MB"
                ),
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"sem_{nome}",
                use_container_width=True
            )

    else:

        st.success(
            "Não existem páginas sem comprovantes."
        )
```
