import streamlit as st
import os
import re
import unicodedata
import tempfile
import shutil
import gc

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
# CONFIGURAÇÃO DE TAMANHO
# ============================================================

# 10 MB = 10.000.000 bytes
LIMITE_BYTES = 10_000_000

# Usamos uma margem de segurança para garantir
# que o arquivo final não ultrapasse 10 MB.
LIMITE_INTERNO = 9_500_000


# ============================================================
# INTERFACE
# ============================================================

st.title("📄 Separador de Comprovantes")

st.write(
    "Envie o PDF mensal para separar comprovantes "
    "e páginas sem comprovantes."
)

st.info(
    "Os arquivos serão agrupados automaticamente em PDFs "
    "de até aproximadamente 10 MB."
)


# ============================================================
# NORMALIZA TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
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
# IDENTIFICA COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(
        texto
    )

    if not texto:
        return None

    possui_pix = bool(
        re.search(
            r"\bPIX\b",
            texto
        )
    )

    possui_comprovante = bool(
        re.search(
            r"\bCOMPROVANTE\b",
            texto
        )
    )

    # --------------------------------------------------------
    # PIX
    # --------------------------------------------------------

    if (
        possui_pix
        and possui_comprovante
    ):
        return "PIX"

    if re.search(
        r"\bPAGAMENTO\s+PIX\b",
        texto
    ):
        return "PIX"

    if re.search(
        r"\bPIX\s+PAGAMENTO\b",
        texto
    ):
        return "PIX"

    # --------------------------------------------------------
    # TRANSFERÊNCIA
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSFERENCIA\b",
            texto
        )
    ):
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSACAO\b",
            texto
        )
        and re.search(
            r"\bBANCARIA\b",
            texto
        )
    ):
        return "TRANSACAO_BANCARIA"

    # --------------------------------------------------------
    # PAGAMENTO
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bPAGAMENTO\b",
            texto
        )
    ):
        return "PAGAMENTO"

    # --------------------------------------------------------
    # DEPÓSITO
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bDEPOSITO\b",
            texto
        )
    ):
        return "DEPOSITO"

    # --------------------------------------------------------
    # TED
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bTED\b",
            texto
        )
    ):
        return "TED"

    # --------------------------------------------------------
    # DOC
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bDOC\b",
            texto
        )
    ):
        return "DOC"

    # --------------------------------------------------------
    # BOLETO
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bBOLETO\b",
            texto
        )
    ):
        return "BOLETO"

    # --------------------------------------------------------
    # AGENDAMENTO
    # --------------------------------------------------------

    if (
        possui_comprovante
        and re.search(
            r"\bAGENDAMENTO\b",
            texto
        )
    ):
        return "AGENDAMENTO"

    # --------------------------------------------------------
    # OUTRO COMPROVANTE
    # --------------------------------------------------------

    if possui_comprovante:
        return "OUTRO_COMPROVANTE"

    return None


# ============================================================
# FORMATA TAMANHO
# ============================================================

def formatar_tamanho(tamanho):

    if tamanho < 1024:
        return f"{tamanho} B"

    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.2f} KB"

    return f"{tamanho / (1024 * 1024):.2f} MB"


# ============================================================
# CRIA PDF COM DETERMINADAS PÁGINAS
# ============================================================

def criar_pdf(
    reader,
    paginas,
    caminho
):

    writer = PdfWriter()

    for numero_pagina in paginas:

        writer.add_page(
            reader.pages[
                numero_pagina
            ]
        )

    with open(
        caminho,
        "wb"
    ) as arquivo:

        writer.write(
            arquivo
        )

    tamanho = os.path.getsize(
        caminho
    )

    del writer

    gc.collect()

    return tamanho


# ============================================================
# TESTA TAMANHO DE UM GRUPO
# ============================================================

def testar_grupo(
    reader,
    paginas,
    pasta_temp,
    contador
):

    nome = (
        f"teste_{contador}.pdf"
    )

    caminho = os.path.join(
        pasta_temp,
        nome
    )

    tamanho = criar_pdf(
        reader,
        paginas,
        caminho
    )

    try:

        os.remove(
            caminho
        )

    except:

        pass

    return tamanho


# ============================================================
# AGRUPAMENTO CORRETO
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    prefixo,
    pasta_saida,
    pasta_temp,
    progress_bar,
    inicio_progresso,
    fim_progresso
):

    arquivos = []

    grupo_atual = []

    numero_arquivo = 1

    total_paginas = len(
        paginas
    )

    if total_paginas == 0:
        return arquivos

    for indice, numero_pagina in enumerate(
        paginas
    ):

        # ====================================================
        # PRIMEIRA PÁGINA DO GRUPO
        # ====================================================

        if not grupo_atual:

            grupo_atual = [
                numero_pagina
            ]

            continue

        # ====================================================
        # TESTA SE CABE NO GRUPO ATUAL
        # ====================================================

        grupo_teste = (
            grupo_atual
            +
            [numero_pagina]
        )

        tamanho_teste = testar_grupo(
            reader,
            grupo_teste,
            pasta_temp,
            indice
        )

        # ====================================================
        # CABE
        # ====================================================

        if (
            tamanho_teste
            <=
            LIMITE_INTERNO
        ):

            grupo_atual = (
                grupo_teste
            )

        # ====================================================
        # NÃO CABE
        # ====================================================

        else:

            nome_final = (
                f"{prefixo}_"
                f"{numero_arquivo:03d}.pdf"
            )

            caminho_final = os.path.join(
                pasta_saida,
                nome_final
            )

            tamanho_final = criar_pdf(
                reader,
                grupo_atual,
                caminho_final
            )

            arquivos.append({
                "nome":
                    nome_final,

                "caminho":
                    caminho_final,

                "tamanho":
                    tamanho_final,

                "paginas":
                    len(
                        grupo_atual
                    )
            })

            numero_arquivo += 1

            # Começa novo grupo
            grupo_atual = [
                numero_pagina
            ]

        # ====================================================
        # PROGRESSO
        # ====================================================

        progresso = (
            inicio_progresso
            +
            (
                (indice + 1)
                /
                total_paginas
            )
            *
            (
                fim_progresso
                -
                inicio_progresso
            )
        )

        progress_bar.progress(
            min(
                int(progresso),
                100
            )
        )

    # ========================================================
    # SALVA ÚLTIMO GRUPO
    # ========================================================

    if grupo_atual:

        nome_final = (
            f"{prefixo}_"
            f"{numero_arquivo:03d}.pdf"
        )

        caminho_final = os.path.join(
            pasta_saida,
            nome_final
        )

        tamanho_final = criar_pdf(
            reader,
            grupo_atual,
            caminho_final
        )

        arquivos.append({
            "nome":
                nome_final,

            "caminho":
                caminho_final,

            "tamanho":
                tamanho_final,

            "paginas":
                len(
                    grupo_atual
                )
        })

    return arquivos


# ============================================================
# PROCESSA PDF
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar
):

    reader = PdfReader(
        caminho_pdf
    )

    total_paginas = len(
        reader.pages
    )

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    contadores = {}

    diagnostico = []

    # ========================================================
    # ANALISA TODAS AS PÁGINAS
    # ========================================================

    for numero_pagina in range(
        total_paginas
    ):

        pagina = reader.pages[
            numero_pagina
        ]

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except:

            texto = ""

        texto_normalizado = (
            normalizar_texto(
                texto
            )
        )

        tipo = (
            identificar_comprovante(
                texto
            )
        )

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo:

            paginas_comprovantes.append(
                numero_pagina
            )

            contadores[tipo] = (
                contadores.get(
                    tipo,
                    0
                )
                +
                1
            )

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        diagnostico.append({
            "pagina":
                numero_pagina + 1,

            "tipo":
                tipo
                if tipo
                else "NAO_COMPROVANTE",

            "pix":
                "PIX"
                in texto_normalizado,

            "comprovante":
                "COMPROVANTE"
                in texto_normalizado,

            "texto":
                texto_normalizado[
                    :1000
                ]
        })

        # ====================================================
        # PROGRESSO
        # ====================================================

        progresso = int(
            (
                (numero_pagina + 1)
                /
                max(
                    total_paginas,
                    1
                )
            )
            * 40
        )

        progress_bar.progress(
            min(
                progresso,
                40
            )
        )

    # ========================================================
    # PASTAS
    # ========================================================

    pasta_saida = os.path.join(
        pasta_trabalho,
        "resultado"
    )

    pasta_temp = os.path.join(
        pasta_trabalho,
        "temporarios"
    )

    os.makedirs(
        pasta_saida,
        exist_ok=True
    )

    os.makedirs(
        pasta_temp,
        exist_ok=True
    )

    # ========================================================
    # AGRUPA COMPROVANTES
    # ========================================================

    arquivos_comprovantes = (
        agrupar_paginas(
            reader,
            paginas_comprovantes,
            "COMPROVANTES",
            pasta_saida,
            pasta_temp,
            progress_bar,
            40,
            70
        )
    )

    # ========================================================
    # AGRUPA SEM COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = (
        agrupar_paginas(
            reader,
            paginas_sem_comprovantes,
            "SEM_COMPROVANTES",
            pasta_saida,
            pasta_temp,
            progress_bar,
            70,
            100
        )
    )

    progress_bar.progress(
        100
    )

    return {
        "total_paginas":
            total_paginas,

        "total_comprovantes":
            len(
                paginas_comprovantes
            ),

        "total_sem_comprovantes":
            len(
                paginas_sem_comprovantes
            ),

        "contadores":
            contadores,

        "diagnostico":
            diagnostico,

        "arquivos_comprovantes":
            arquivos_comprovantes,

        "arquivos_sem_comprovantes":
            arquivos_sem_comprovantes
    }


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📎 Selecione o arquivo PDF",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo is not None:

    tamanho_upload = len(
        arquivo.getbuffer()
    )

    st.success(
        f"Arquivo: **{arquivo.name}**"
    )

    st.write(
        "Tamanho: "
        f"**{formatar_tamanho(tamanho_upload)}**"
    )

    if st.button(
        "🚀 PROCESSAR PDF",
        type="primary",
        use_container_width=True
    ):

        progress_bar = st.progress(
            0
        )

        status = st.empty()

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_"
        )

        caminho_pdf = os.path.join(
            pasta_trabalho,
            arquivo.name
        )

        try:

            # ------------------------------------------------
            # SALVA UPLOAD
            # ------------------------------------------------

            status.info(
                "Salvando arquivo..."
            )

            with open(
                caminho_pdf,
                "wb"
            ) as f:

                f.write(
                    arquivo.getbuffer()
                )

            # ------------------------------------------------
            # PROCESSA
            # ------------------------------------------------

            status.info(
                "Analisando páginas..."
            )

            resultado = processar_pdf(
                caminho_pdf,
                pasta_trabalho,
                progress_bar
            )

            st.session_state[
                "resultado"
            ] = resultado

            st.session_state[
                "pasta_trabalho"
            ] = pasta_trabalho

            status.success(
                "✅ Processamento concluído!"
            )

        except Exception as erro:

            status.error(
                "❌ Erro no processamento."
            )

            st.exception(
                erro
            )


# ============================================================
# RESULTADO
# ============================================================

if "resultado" in st.session_state:

    resultado = (
        st.session_state[
            "resultado"
        ]
    )

    st.divider()

    st.header(
        "📊 Resultado"
    )

    # ========================================================
    # INDICADORES
    # ========================================================

    col1, col2, col3 = st.columns(3)

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

    # ========================================================
    # TIPOS
    # ========================================================

    contadores = (
        resultado[
            "contadores"
        ]
    )

    if contadores:

        st.subheader(
            "🔎 Tipos encontrados"
        )

        tipos = sorted(
            contadores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        colunas = st.columns(
            min(
                4,
                len(tipos)
            )
        )

        for i, (
            tipo,
            quantidade
        ) in enumerate(
            tipos
        ):

            with colunas[
                i % len(colunas)
            ]:

                st.metric(
                    tipo.replace(
                        "_",
                        " "
                    ),
                    quantidade
                )

    # ========================================================
    # PIX
    # ========================================================

    quantidade_pix = (
        contadores.get(
            "PIX",
            0
        )
    )

    if quantidade_pix > 0:

        st.success(
            f"💚 PIX encontrados: "
            f"**{quantidade_pix}**"
        )

    # ========================================================
    # COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 Arquivos de comprovantes"
    )

    arquivos = (
        resultado[
            "arquivos_comprovantes"
        ]
    )

    for item in arquivos:

        st.write(
            f"📄 **{item['nome']}**"
        )

        st.caption(
            f"Páginas: {item['paginas']} | "
            f"Tamanho: "
            f"{formatar_tamanho(item['tamanho'])}"
        )

        with open(
            item["caminho"],
            "rb"
        ) as f:

            st.download_button(
                label=(
                    f"⬇️ Baixar "
                    f"{item['nome']}"
                ),
                data=f.read(),
                file_name=item[
                    "nome"
                ],
                mime="application/pdf",
                key=(
                    "comp_"
                    +
                    item["nome"]
                ),
                use_container_width=True
            )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 Arquivos sem comprovantes"
    )

    arquivos = (
        resultado[
            "arquivos_sem_comprovantes"
        ]
    )

    for item in arquivos:

        st.write(
            f"📄 **{item['nome']}**"
        )

        st.caption(
            f"Páginas: {item['paginas']} | "
            f"Tamanho: "
            f"{formatar_tamanho(item['tamanho'])}"
        )

        with open(
            item["caminho"],
            "rb"
        ) as f:

            st.download_button(
                label=(
                    f"⬇️ Baixar "
                    f"{item['nome']}"
                ),
                data=f.read(),
                file_name=item[
                    "nome"
                ],
                mime="application/pdf",
                key=(
                    "sem_"
                    +
                    item["nome"]
                ),
                use_container_width=True
            )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    st.divider()

    with st.expander(
        "🔍 Diagnóstico"
    ):

        for item in resultado[
            "diagnostico"
        ]:

            if item["pix"]:

                st.success(
                    f"Página {item['pagina']} "
                    f"→ PIX → "
                    f"{item['tipo']}"
                )

                st.code(
                    item["texto"]
                )

            elif item["comprovante"]:

                st.info(
                    f"Página {item['pagina']} "
                    f"→ {item['tipo']}"
                )
