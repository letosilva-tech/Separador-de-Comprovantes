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

LIMITE_MB = 10
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


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
# CRIA PDF COM PÁGINAS
# ============================================================

def criar_pdf_paginas(paginas):

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
# SEPARAÇÃO DOS COMPROVANTES
# ============================================================

def separar_comprovantes(
    leitor,
    progresso,
    status
):

    comprovantes = []

    demais_paginas = []

    comprovante_atual = None

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

        tipo = identificar_tipo_comprovante(
            texto
        )

        # ====================================================
        # ENCONTROU UM NOVO COMPROVANTE
        # ====================================================

        if tipo is not None:

            # ------------------------------------------------
            # Salva comprovante anterior
            # ------------------------------------------------

            if comprovante_atual is not None:

                comprovantes.append(
                    comprovante_atual
                )

            # ------------------------------------------------
            # Inicia novo comprovante
            # ------------------------------------------------

            comprovante_atual = {
                "tipo": tipo,
                "paginas": [
                    pagina
                ],
                "pagina_inicio": numero_pagina,
                "pagina_fim": numero_pagina
            }

            continue

        # ====================================================
        # PÁGINA SEM NOVO CABEÇALHO
        # ====================================================

        if comprovante_atual is not None:

            # ------------------------------------------------
            # Mantém como continuação do comprovante
            # ------------------------------------------------

            comprovante_atual[
                "paginas"
            ].append(
                pagina
            )

            comprovante_atual[
                "pagina_fim"
            ] = numero_pagina

        else:

            # ------------------------------------------------
            # Ainda não encontramos nenhum comprovante.
            # Essa página vai para os demais arquivos.
            # ------------------------------------------------

            demais_paginas.append({
                "numero": numero_pagina,
                "pagina": pagina
            })

    # ========================================================
    # SALVA ÚLTIMO COMPROVANTE
    # ========================================================

    if comprovante_atual is not None:

        comprovantes.append(
            comprovante_atual
        )

    return (
        comprovantes,
        demais_paginas
    )


# ============================================================
# ADICIONA ARQUIVOS A UM ZIP
# ============================================================

def adicionar_ao_zip(
    zip_buffer,
    nome_arquivo,
    dados
):

    with zipfile.ZipFile(
        zip_buffer,
        "a",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        zip_file.writestr(
            nome_arquivo,
            dados
        )


# ============================================================
# CRIA ZIPS COM LIMITE REAL DE 10 MB
# ============================================================

def criar_pacotes_zip(
    arquivos,
    prefixo,
    limite_bytes=LIMITE_BYTES
):

    pacotes = []

    numero_pacote = 1

    zip_buffer = BytesIO()

    contador_arquivos = 0

    for nome_arquivo, dados in arquivos:

        # ----------------------------------------------------
        # Se ainda não existe arquivo no ZIP
        # ----------------------------------------------------

        if contador_arquivos == 0:

            zip_buffer = BytesIO()

            adicionar_ao_zip(
                zip_buffer,
                nome_arquivo,
                dados
            )

            tamanho_atual = len(
                zip_buffer.getvalue()
            )

            # Arquivo sozinho maior que 10 MB
            if tamanho_atual > limite_bytes:

                pacotes.append({
                    "nome": (
                        f"{prefixo}_"
                        f"{numero_pacote:03d}.zip"
                    ),
                    "dados":
                        zip_buffer.getvalue(),
                    "tamanho":
                        tamanho_atual
                })

                numero_pacote += 1

                contador_arquivos = 0

            else:

                contador_arquivos = 1

            continue

        # ----------------------------------------------------
        # Testa se cabe no ZIP atual
        # ----------------------------------------------------

        teste_buffer = BytesIO()

        with zipfile.ZipFile(
            teste_buffer,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zip_teste:

            with zipfile.ZipFile(
                BytesIO(
                    zip_buffer.getvalue()
                ),
                "r"
            ) as zip_atual:

                for item in zip_atual.infolist():

                    zip_teste.writestr(
                        item,
                        zip_atual.read(
                            item.filename
                        )
                    )

            zip_teste.writestr(
                nome_arquivo,
                dados
            )

        tamanho_teste = len(
            teste_buffer.getvalue()
        )

        # ----------------------------------------------------
        # Cabe no ZIP atual
        # ----------------------------------------------------

        if tamanho_teste <= limite_bytes:

            zip_buffer = teste_buffer

            contador_arquivos += 1

        else:

            # ------------------------------------------------
            # Fecha pacote atual
            # ------------------------------------------------

            pacotes.append({
                "nome": (
                    f"{prefixo}_"
                    f"{numero_pacote:03d}.zip"
                ),
                "dados":
                    zip_buffer.getvalue(),
                "tamanho":
                    len(zip_buffer.getvalue())
            })

            numero_pacote += 1

            # ------------------------------------------------
            # Começa novo pacote
            # ------------------------------------------------

            zip_buffer = BytesIO()

            adicionar_ao_zip(
                zip_buffer,
                nome_arquivo,
                dados
            )

            contador_arquivos = 1

    # ========================================================
    # SALVA ÚLTIMO PACOTE
    # ========================================================

    if contador_arquivos > 0:

        dados_zip = zip_buffer.getvalue()

        pacotes.append({
            "nome": (
                f"{prefixo}_"
                f"{numero_pacote:03d}.zip"
            ),
            "dados": dados_zip,
            "tamanho": len(dados_zip)
        })

    return pacotes


# ============================================================
# CRIA ARQUIVOS DOS COMPROVANTES
# ============================================================

def preparar_comprovantes(
    comprovantes
):

    arquivos = []

    for numero, comprovante in enumerate(
        comprovantes,
        start=1
    ):

        tipo = comprovante["tipo"]

        if tipo == "PIX":

            prefixo = "PIX"

        elif tipo == "TRANSFERENCIA":

            prefixo = "TRANSFERENCIA"

        elif tipo == "TRANSACAO_BANCARIA":

            prefixo = "TRANSACAO_BANCARIA"

        else:

            prefixo = "OUTRO"

        pdf_bytes = criar_pdf_paginas(
            comprovante["paginas"]
        )

        nome = (
            f"comprovante_"
            f"{prefixo}_"
            f"{numero:03d}.pdf"
        )

        arquivos.append(
            (
                nome,
                pdf_bytes
            )
        )

    return arquivos


# ============================================================
# CRIA ARQUIVOS DOS DEMAIS
# ============================================================

def preparar_demais_arquivos(
    demais_paginas
):

    arquivos = []

    for item in demais_paginas:

        numero = item["numero"]

        pagina = item["pagina"]

        pdf_bytes = criar_pdf_paginas(
            [pagina]
        )

        nome = (
            f"pagina_"
            f"{numero:03d}.pdf"
        )

        arquivos.append(
            (
                nome,
                pdf_bytes
            )
        )

    return arquivos


# ============================================================
# LIMPA RESULTADOS
# ============================================================

def limpar_resultados():

    chaves = [
        "comprovantes",
        "demais_paginas",
        "pacotes_comprovantes",
        "pacotes_demais",
        "processado",
        "tempo_processamento"
    ]

    for chave in chaves:

        st.session_state.pop(
            chave,
            None
        )


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.write(
    """
    Selecione um único PDF contendo vários documentos.

    O sistema identifica automaticamente:

    🔵 **COMPROVANTE PIX**

    🟢 **COMPROVANTE DE TRANSFERÊNCIA**

    🟣 **COMPROVANTE DE TRANSAÇÃO BANCÁRIA**

    Os resultados serão organizados em pacotes ZIP de até
    **10 MB**.
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
# PROCESSAMENTO
# ============================================================

if arquivo_pdf is not None:

    st.success(
        f"✅ Arquivo selecionado: "
        f"**{arquivo_pdf.name}**"
    )

    try:

        leitor = PdfReader(
            arquivo_pdf
        )

        total_paginas = len(
            leitor.pages
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

            status = st.empty()

            progresso = st.progress(0)

            # =================================================
            # ANALISA
            # =================================================

            (
                comprovantes,
                demais_paginas
            ) = separar_comprovantes(
                leitor,
                progresso,
                status
            )

            # =================================================
            # PREPARA COMPROVANTES
            # =================================================

            status.text(
                "📦 Preparando comprovantes..."
            )

            arquivos_comprovantes = (
                preparar_comprovantes(
                    comprovantes
                )
            )

            pacotes_comprovantes = (
                criar_pacotes_zip(
                    arquivos_comprovantes,
                    "COMPROVANTES"
                )
            )

            # =================================================
            # PREPARA DEMAIS ARQUIVOS
            # =================================================

            status.text(
                "📄 Preparando demais arquivos..."
            )

            arquivos_demais = (
                preparar_demais_arquivos(
                    demais_paginas
                )
            )

            pacotes_demais = (
                criar_pacotes_zip(
                    arquivos_demais,
                    "SEM_COMPROVANTES"
                )
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
            # SALVA SESSION STATE
            # =================================================

            st.session_state[
                "comprovantes"
            ] = comprovantes

            st.session_state[
                "demais_paginas"
            ] = demais_paginas

            st.session_state[
                "pacotes_comprovantes"
            ] = pacotes_comprovantes

            st.session_state[
                "pacotes_demais"
            ] = pacotes_demais

            st.session_state[
                "quantidade_total"
            ] = len(comprovantes)

            st.session_state[
                "quantidade_pix"
            ] = quantidade_pix

            st.session_state[
                "quantidade_transferencia"
            ] = quantidade_transferencia

            st.session_state[
                "quantidade_transacao"
            ] = quantidade_transacao

            st.session_state[
                "quantidade_demais"
            ] = len(demais_paginas)

            st.session_state[
                "processado"
            ] = True

            st.session_state[
                "tempo_processamento"
            ] = time.time() - inicio

            progresso.progress(1.0)

            status.success(
                "✅ Processamento concluído!"
            )

            st.rerun()

    except Exception as erro:

        st.error(
            f"❌ Erro ao abrir o PDF: {erro}"
        )


# ============================================================
# RESULTADO
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    st.divider()

    st.subheader(
        "📊 Resultado da separação"
    )

    # ========================================================
    # CONTADORES
    # ========================================================

    total = st.session_state[
        "quantidade_total"
    ]

    pix = st.session_state[
        "quantidade_pix"
    ]

    transferencias = st.session_state[
        "quantidade_transferencia"
    ]

    transacoes = st.session_state[
        "quantidade_transacao"
    ]

    demais = st.session_state[
        "quantidade_demais"
    ]

    # --------------------------------------------------------
    # DESTAQUE TOTAL
    # --------------------------------------------------------

    st.success(
        f"🎯 **{total} comprovante(s) encontrados!**"
    )

    # --------------------------------------------------------
    # MÉTRICAS
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "📄 Comprovantes",
            total
        )

    with col2:

        st.metric(
            "🔵 PIX",
            pix
        )

    with col3:

        st.metric(
            "🟢 Transferências",
            transferencias
        )

    with col4:

        st.metric(
            "🟣 Transações bancárias",
            transacoes
        )

    # ========================================================
    # DEMAIS PÁGINAS
    # ========================================================

    st.info(
        f"📑 **{demais} página(s)** "
        f"não foram identificadas como comprovantes."
    )

    st.info(
        f"⏱️ Tempo de processamento: "
        f"**{st.session_state['tempo_processamento']:.1f} segundos**"
    )

    # ========================================================
    # DETALHAMENTO
    # ========================================================

    st.divider()

    st.subheader(
        "🔎 Comprovantes encontrados"
    )

    dados = []

    for numero, comprovante in enumerate(
        st.session_state["comprovantes"],
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

    # ========================================================
    # DOWNLOAD COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📦 1. Comprovantes agrupados"
    )

    pacotes_comprovantes = (
        st.session_state[
            "pacotes_comprovantes"
        ]
    )

    if pacotes_comprovantes:

        st.success(
            f"✅ {len(pacotes_comprovantes)} "
            f"pacote(s) de comprovantes."
        )

        for pacote in pacotes_comprovantes:

            tamanho_mb = (
                pacote["tamanho"]
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"📦 {pacote['nome']} "
                    f"— {tamanho_mb:.2f} MB"
                ),

                data=pacote["dados"],

                file_name=pacote["nome"],

                mime="application/zip",

                use_container_width=True,

                key=(
                    f"download_comprovantes_"
                    f"{pacote['nome']}"
                )
            )

    else:

        st.warning(
            "Nenhum comprovante foi encontrado."
        )

    # ========================================================
    # DOWNLOAD DEMAIS ARQUIVOS
    # ========================================================

    st.divider()

    st.subheader(
        "📁 2. Arquivos sem comprovantes"
    )

    pacotes_demais = (
        st.session_state[
            "pacotes_demais"
        ]
    )

    if pacotes_demais:

        st.warning(
            f"⚠️ {len(pacotes_demais)} "
            f"pacote(s) contendo as páginas "
            f"que não foram identificadas como comprovantes."
        )

        for pacote in pacotes_demais:

            tamanho_mb = (
                pacote["tamanho"]
                / (1024 * 1024)
            )

            st.download_button(
                label=(
                    f"📁 {pacote['nome']} "
                    f"— {tamanho_mb:.2f} MB"
                ),

                data=pacote["dados"],

                file_name=pacote["nome"],

                mime="application/zip",

                use_container_width=True,

                key=(
                    f"download_demais_"
                    f"{pacote['nome']}"
                )
            )

    else:

        st.success(
            "✅ Não existem páginas sem comprovantes."
        )
