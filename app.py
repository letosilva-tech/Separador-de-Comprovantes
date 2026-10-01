import streamlit as st
import os
import re
import unicodedata
import tempfile
import shutil
import gc

from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# TÍTULO
# ============================================================

st.title("📄 Separador de Comprovantes")

st.write(
    "Envie o PDF e o sistema irá identificar os comprovantes "
    "PIX, transferências, pagamentos e demais comprovantes."
)

st.info(
    "Nesta versão, TODAS as páginas do PDF são analisadas. "
    "A regra do ANEXO foi retirada para garantir que nenhum "
    "comprovante PIX seja ignorado."
)


# ============================================================
# NORMALIZA TEXTO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    # Remove acentos
    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    # Maiúsculo
    texto = texto.upper()

    # Mantém apenas letras/números/espaços
    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto
    )

    # Remove espaços duplicados
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

    # ========================================================
    # FLAGS
    # ========================================================

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

    # ========================================================
    # PIX
    # ========================================================

    # Exemplos:
    #
    # COMPROVANTE PIX
    # COMPROVANTE DE PIX
    # COMPROVANTE DE PAGAMENTO PIX
    # PIX COMPROVANTE
    # PAGAMENTO PIX
    #
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

    # ========================================================
    # TRANSFERÊNCIA
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSFERENCIA\b",
            texto
        )
    ):
        return "TRANSFERENCIA"

    # ========================================================
    # TRANSAÇÃO BANCÁRIA
    # ========================================================

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

    # ========================================================
    # PAGAMENTO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bPAGAMENTO\b",
            texto
        )
    ):
        return "PAGAMENTO"

    # ========================================================
    # DEPÓSITO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bDEPOSITO\b",
            texto
        )
    ):
        return "DEPOSITO"

    # ========================================================
    # TED
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTED\b",
            texto
        )
    ):
        return "TED"

    # ========================================================
    # DOC
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bDOC\b",
            texto
        )
    ):
        return "DOC"

    # ========================================================
    # BOLETO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bBOLETO\b",
            texto
        )
    ):
        return "BOLETO"

    # ========================================================
    # AGENDAMENTO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bAGENDAMENTO\b",
            texto
        )
    ):
        return "AGENDAMENTO"

    # ========================================================
    # TRANSFERÊNCIA ELETRÔNICA
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSFERENCIA\b",
            texto
        )
        and re.search(
            r"\bELETRONICA\b",
            texto
        )
    ):
        return "TRANSFERENCIA_ELETRONICA"

    # ========================================================
    # TRANSFERÊNCIA BANCÁRIA
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSFERENCIA\b",
            texto
        )
        and re.search(
            r"\bBANCARIA\b",
            texto
        )
    ):
        return "TRANSFERENCIA_BANCARIA"

    # ========================================================
    # QUALQUER OUTRO COMPROVANTE
    # ========================================================

    if possui_comprovante:
        return "OUTRO_COMPROVANTE"

    return None


# ============================================================
# FORMATA TAMANHO
# ============================================================

def formatar_tamanho(tamanho):

    if tamanho < 1024:

        return (
            f"{tamanho} B"
        )

    if tamanho < 1024 * 1024:

        return (
            f"{tamanho / 1024:.2f} KB"
        )

    return (
        f"{tamanho / (1024 * 1024):.2f} MB"
    )


# ============================================================
# SALVA PDF
# ============================================================

def salvar_writer(
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
# CRIA PDF TEMPORÁRIO
# ============================================================

def gerar_pdf_temporario(
    reader,
    paginas,
    pasta_temp,
    nome
):

    caminho = os.path.join(
        pasta_temp,
        nome
    )

    writer = PdfWriter()

    for numero_pagina in paginas:

        writer.add_page(
            reader.pages[
                numero_pagina
            ]
        )

    salvar_writer(
        writer,
        caminho
    )

    tamanho = os.path.getsize(
        caminho
    )

    del writer

    gc.collect()

    return (
        caminho,
        tamanho
    )


# ============================================================
# SALVA GRUPO FINAL
# ============================================================

def salvar_grupo_final(
    reader,
    paginas,
    pasta_saida,
    prefixo,
    numero
):

    nome = (
        f"{prefixo}_{numero:03d}.pdf"
    )

    caminho = os.path.join(
        pasta_saida,
        nome
    )

    writer = PdfWriter()

    for numero_pagina in paginas:

        writer.add_page(
            reader.pages[
                numero_pagina
            ]
        )

    salvar_writer(
        writer,
        caminho
    )

    tamanho = os.path.getsize(
        caminho
    )

    del writer

    gc.collect()

    return (
        caminho,
        tamanho
    )


# ============================================================
# AGRUPA PÁGINAS
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    prefixo,
    pasta_saida,
    pasta_temp,
    progress_bar,
    inicio,
    fim
):

    # --------------------------------------------------------
    # LIMITE INTERNO
    # --------------------------------------------------------
    # 9,5 MB para manter margem abaixo de 10 MB.
    # --------------------------------------------------------

    LIMITE_BYTES = 9_500_000

    arquivos = []

    grupo_atual = []

    numero_arquivo = 1

    total = len(
        paginas
    )

    for indice, numero_pagina in enumerate(
        paginas
    ):

        # Adiciona nova página ao grupo
        grupo_teste = (
            grupo_atual
            +
            [numero_pagina]
        )

        # Cria PDF temporário
        caminho_teste, tamanho_teste = (
            gerar_pdf_temporario(
                reader,
                grupo_teste,
                pasta_temp,
                f"teste_{prefixo}_{indice}.pdf"
            )
        )

        # ====================================================
        # PASSOU DO LIMITE
        # ====================================================

        if (
            tamanho_teste > LIMITE_BYTES
            and grupo_atual
        ):

            # Salva grupo anterior
            caminho_final, tamanho_final = (
                salvar_grupo_final(
                    reader,
                    grupo_atual,
                    pasta_saida,
                    prefixo,
                    numero_arquivo
                )
            )

            arquivos.append({
                "nome":
                    os.path.basename(
                        caminho_final
                    ),

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

            # Nova página inicia novo grupo
            grupo_atual = [
                numero_pagina
            ]

        else:

            grupo_atual = (
                grupo_teste
            )

        # Remove teste
        try:

            os.remove(
                caminho_teste
            )

        except:

            pass

        # ====================================================
        # PROGRESSO
        # ====================================================

        if total > 0:

            progresso = (
                inicio
                +
                (
                    (indice + 1)
                    /
                    total
                )
                *
                (
                    fim
                    -
                    inicio
                )
            )

            progress_bar.progress(
                min(
                    int(progresso),
                    100
                )
            )

    # ========================================================
    # ÚLTIMO GRUPO
    # ========================================================

    if grupo_atual:

        caminho_final, tamanho_final = (
            salvar_grupo_final(
                reader,
                grupo_atual,
                pasta_saida,
                prefixo,
                numero_arquivo
            )
        )

        arquivos.append({
            "nome":
                os.path.basename(
                    caminho_final
                ),

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
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar
):

    # ========================================================
    # ABRE PDF
    # ========================================================

    reader = PdfReader(
        caminho_pdf
    )

    total_paginas = len(
        reader.pages
    )

    # ========================================================
    # LISTAS
    # ========================================================

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

        # ----------------------------------------------------
        # EXTRAI TEXTO
        # ----------------------------------------------------

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except Exception:

            texto = ""

        texto_normalizado = (
            normalizar_texto(
                texto
            )
        )

        # ----------------------------------------------------
        # IDENTIFICA
        # ----------------------------------------------------

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
        # NÃO COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        contem_pix = (
            "PIX"
            in
            texto_normalizado
        )

        contem_comprovante = (
            "COMPROVANTE"
            in
            texto_normalizado
        )

        diagnostico.append({

            "pagina":
                numero_pagina + 1,

            "tipo":
                tipo
                if tipo
                else "NAO_COMPROVANTE",

            "tem_pix":
                contem_pix,

            "tem_comprovante":
                contem_comprovante,

            "texto":
                texto_normalizado[
                    :1000
                ]
        })

        # ====================================================
        # MOSTRA PIX DURANTE O PROCESSAMENTO
        # ====================================================

        if contem_pix:

            st.write(
                f"🔎 Página "
                f"**{numero_pagina + 1}** "
                f"contém PIX"
            )

            st.caption(
                f"Tipo identificado: "
                f"**{tipo}**"
            )

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
            * 50
        )

        progress_bar.progress(
            min(
                progresso,
                50
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
    # GERA COMPROVANTES
    # ========================================================

    arquivos_comprovantes = (
        agrupar_paginas(
            reader=reader,
            paginas=paginas_comprovantes,
            prefixo="COMPROVANTES",
            pasta_saida=pasta_saida,
            pasta_temp=pasta_temp,
            progress_bar=progress_bar,
            inicio=50,
            fim=75
        )
    )

    # ========================================================
    # GERA SEM COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = (
        agrupar_paginas(
            reader=reader,
            paginas=paginas_sem_comprovantes,
            prefixo="SEM_COMPROVANTES",
            pasta_saida=pasta_saida,
            pasta_temp=pasta_temp,
            progress_bar=progress_bar,
            inicio=75,
            fim=100
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
    type=["pdf"],
    help="Selecione o PDF mensal."
)


# ============================================================
# ARQUIVO FOI SELECIONADO
# ============================================================

if arquivo is not None:

    tamanho = len(
        arquivo.getbuffer()
    )

    st.success(
        f"Arquivo selecionado: "
        f"**{arquivo.name}**"
    )

    st.write(
        "Tamanho: "
        f"**{formatar_tamanho(tamanho)}**"
    )

    # ========================================================
    # BOTÃO
    # ========================================================

    if st.button(
        "🚀 PROCESSAR PDF",
        type="primary",
        use_container_width=True
    ):

        progress_bar = st.progress(
            0
        )

        status = st.empty()

        # ----------------------------------------------------
        # PASTA TEMPORÁRIA
        # ----------------------------------------------------

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_"
        )

        caminho_pdf = os.path.join(
            pasta_trabalho,
            arquivo.name
        )

        try:

            # ------------------------------------------------
            # SALVA PDF
            # ------------------------------------------------

            status.info(
                "Salvando PDF..."
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
                "Analisando todas as páginas..."
            )

            resultado = (
                processar_pdf(
                    caminho_pdf,
                    pasta_trabalho,
                    progress_bar
                )
            )

            # ------------------------------------------------
            # GUARDA RESULTADO
            # ------------------------------------------------

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

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except:

                pass


# ============================================================
# MOSTRA RESULTADO
# ============================================================

if (
    "resultado"
    in
    st.session_state
):

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

    col1, col2, col3 = (
        st.columns(3)
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

        quantidade_colunas = min(
            4,
            len(tipos)
        )

        colunas = st.columns(
            quantidade_colunas
        )

        for i, (
            tipo,
            quantidade
        ) in enumerate(
            tipos
        ):

            with colunas[
                i % quantidade_colunas
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

    if quantidade_pix:

        st.success(
            f"💚 PIX encontrados: "
            f"**{quantidade_pix}**"
        )

    else:

        st.warning(
            "⚠️ Nenhum PIX foi identificado."
        )

    # ========================================================
    # ARQUIVOS DE COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 COMPROVANTES"
    )

    arquivos = (
        resultado[
            "arquivos_comprovantes"
        ]
    )

    if arquivos:

        for item in arquivos:

            st.write(
                f"📄 **{item['nome']}**"
            )

            st.caption(
                f"{item['paginas']} páginas | "
                f"{formatar_tamanho(item['tamanho'])}"
            )

            try:

                with open(
                    item["caminho"],
                    "rb"
                ) as arquivo_pdf:

                    st.download_button(
                        label=(
                            f"⬇️ Baixar "
                            f"{item['nome']}"
                        ),

                        data=arquivo_pdf.read(),

                        file_name=item[
                            "nome"
                        ],

                        mime="application/pdf",

                        key=(
                            "comp_"
                            +
                            item[
                                "nome"
                            ]
                        ),

                        use_container_width=True
                    )

            except Exception as erro:

                st.error(
                    str(erro)
                )

    else:

        st.warning(
            "Nenhum comprovante foi gerado."
        )

    # ========================================================
    # ARQUIVOS SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 SEM COMPROVANTES"
    )

    arquivos = (
        resultado[
            "arquivos_sem_comprovantes"
        ]
    )

    if arquivos:

        for item in arquivos:

            st.write(
                f"📄 **{item['nome']}**"
            )

            st.caption(
                f"{item['paginas']} páginas | "
                f"{formatar_tamanho(item['tamanho'])}"
            )

            try:

                with open(
                    item["caminho"],
                    "rb"
                ) as arquivo_pdf:

                    st.download_button(
                        label=(
                            f"⬇️ Baixar "
                            f"{item['nome']}"
                        ),

                        data=arquivo_pdf.read(),

                        file_name=item[
                            "nome"
                        ],

                        mime="application/pdf",

                        key=(
                            "sem_"
                            +
                            item[
                                "nome"
                            ]
                        ),

                        use_container_width=True
                    )

            except Exception as erro:

                st.error(
                    str(erro)
                )

    else:

        st.info(
            "Não existem páginas sem comprovantes."
        )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    st.divider()

    with st.expander(
        "🔍 DIAGNÓSTICO — VER O QUE FOI LIDO EM CADA PÁGINA"
    ):

        diagnostico = (
            resultado[
                "diagnostico"
            ]
        )

        for item in diagnostico:

            pagina = item[
                "pagina"
            ]

            tipo = item[
                "tipo"
            ]

            tem_pix = item[
                "tem_pix"
            ]

            tem_comprovante = item[
                "tem_comprovante"
            ]

            texto = item[
                "texto"
            ]

            if tem_pix:

                st.success(
                    f"Página {pagina} "
                    f"→ PIX detectado "
                    f"→ tipo: {tipo}"
                )

                st.code(
                    texto
                )

            elif tem_comprovante:

                st.info(
                    f"Página {pagina} "
                    f"→ COMPROVANTE "
                    f"→ tipo: {tipo}"
                )

                st.code(
                    texto
                )
