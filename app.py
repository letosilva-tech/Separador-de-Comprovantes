import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import unicodedata
import re
import gc


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# 10 MB = 10.000.000 bytes
LIMITE_BYTES = 10_000_000

LIMITE_MB = 10


# ============================================================
# CONFIGURAÇÃO STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide"
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
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICA COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    # 1 - PIX
    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # 2 - TRANSFERÊNCIA
    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # 3 - TRANSAÇÃO BANCÁRIA
    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# IDENTIFICA ANEXO
# ============================================================

def identificar_anexo(texto):

    texto = normalizar_texto(texto)

    return bool(
        re.search(
            r"\bANEXO\b",
            texto
        )
    )


# ============================================================
# GERA PDF
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
# AGRUPA PÁGINAS ATÉ 10 MB
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    prefixo,
    progress_bar=None,
    progresso_inicio=0.0,
    progresso_fim=1.0
):

    arquivos = []

    paginas_atual = []

    numero_arquivo = 1

    total_paginas = len(paginas)

    if total_paginas == 0:
        return arquivos

    for posicao, numero_pagina in enumerate(paginas):

        # ====================================================
        # ATUALIZA PROGRESSO
        # ====================================================

        if progress_bar:

            progresso = (
                progresso_inicio
                +
                (
                    (posicao + 1)
                    / total_paginas
                )
                *
                (
                    progresso_fim
                    - progresso_inicio
                )
            )

            progress_bar.progress(
                min(progresso, 1.0)
            )

        # ====================================================
        # TENTA ADICIONAR A PÁGINA AO GRUPO ATUAL
        # ====================================================

        tentativa = (
            paginas_atual
            +
            [numero_pagina]
        )

        pdf_teste = gerar_pdf(
            reader,
            tentativa
        )

        tamanho_teste = len(
            pdf_teste
        )

        # ====================================================
        # CABE NO LIMITE
        # ====================================================

        if tamanho_teste <= LIMITE_BYTES:

            paginas_atual.append(
                numero_pagina
            )

            continue

        # ====================================================
        # NÃO CABE
        # ====================================================

        # Primeiro salva o grupo atual
        if paginas_atual:

            pdf_final = gerar_pdf(
                reader,
                paginas_atual
            )

            tamanho_final = len(
                pdf_final
            )

            nome_arquivo = (
                f"{prefixo}_"
                f"{numero_arquivo:03d}.pdf"
            )

            arquivos.append(
                {
                    "nome": nome_arquivo,
                    "dados": pdf_final,
                    "tamanho": tamanho_final
                }
            )

            numero_arquivo += 1

            # Libera memória
            del pdf_final

            gc.collect()

        # ====================================================
        # TESTA A PÁGINA SOZINHA
        # ====================================================

        pdf_pagina = gerar_pdf(
            reader,
            [numero_pagina]
        )

        tamanho_pagina = len(
            pdf_pagina
        )

        # ====================================================
        # PÁGINA SOZINHA > 10 MB
        # ====================================================

        if tamanho_pagina > LIMITE_BYTES:

            nome_arquivo = (
                f"{prefixo}_"
                f"{numero_arquivo:03d}_"
                f"ACIMA_DE_10MB.pdf"
            )

            arquivos.append(
                {
                    "nome": nome_arquivo,
                    "dados": pdf_pagina,
                    "tamanho": tamanho_pagina
                }
            )

            numero_arquivo += 1

            paginas_atual = []

            del pdf_pagina

            gc.collect()

        else:

            # =================================================
            # COMEÇA NOVO GRUPO
            # =================================================

            paginas_atual = [
                numero_pagina
            ]

            del pdf_pagina

            gc.collect()

        del pdf_teste

        gc.collect()

    # ========================================================
    # SALVA ÚLTIMO GRUPO
    # ========================================================

    if paginas_atual:

        pdf_final = gerar_pdf(
            reader,
            paginas_atual
        )

        tamanho_final = len(
            pdf_final
        )

        nome_arquivo = (
            f"{prefixo}_"
            f"{numero_arquivo:03d}.pdf"
        )

        arquivos.append(
            {
                "nome": nome_arquivo,
                "dados": pdf_final,
                "tamanho": tamanho_final
            }
        )

        del pdf_final

        gc.collect()

    return arquivos


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar_pdf(
    arquivo,
    progress_bar=None
):

    # ========================================================
    # ABRE O PDF
    # ========================================================

    arquivo.seek(0)

    reader = PdfReader(
        arquivo
    )

    total_paginas_pdf = len(
        reader.pages
    )

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    contadores = {
        "PIX": 0,
        "TRANSFERENCIA": 0,
        "TRANSACAO_BANCARIA": 0
    }

    encontrou_anexo = False

    # ========================================================
    # LEITURA DAS PÁGINAS
    # ========================================================

    if progress_bar:
        progress_bar.progress(0)

    for numero_pagina, pagina in enumerate(
        reader.pages
    ):

        try:

            texto = pagina.extract_text() or ""

        except Exception:

            texto = ""

        # ====================================================
        # PROGRESSO DA LEITURA
        # ====================================================

        if progress_bar:

            progresso = (
                (numero_pagina + 1)
                / total_paginas_pdf
            ) * 0.30

            progress_bar.progress(
                min(progresso, 0.30)
            )

        # ====================================================
        # PROCURA ANEXO
        # ====================================================

        if not encontrou_anexo:

            if identificar_anexo(texto):

                encontrou_anexo = True

            # Não inclui a própria página do ANEXO
            continue

        # ====================================================
        # IDENTIFICA COMPROVANTE
        # ====================================================

        tipo = identificar_comprovante(
            texto
        )

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo:

            paginas_comprovantes.append(
                numero_pagina
            )

            contadores[tipo] += 1

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

    # ========================================================
    # LIBERA PROGRESSO
    # ========================================================

    if progress_bar:
        progress_bar.progress(0.30)

    # ========================================================
    # AGRUPA COMPROVANTES
    # ========================================================

    arquivos_comprovantes = agrupar_paginas(
        reader=reader,
        paginas=paginas_comprovantes,
        prefixo="COMPROVANTES",
        progress_bar=progress_bar,
        progresso_inicio=0.30,
        progresso_fim=0.65
    )

    # ========================================================
    # AGRUPA SEM COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = agrupar_paginas(
        reader=reader,
        paginas=paginas_sem_comprovantes,
        prefixo="SEM_COMPROVANTES",
        progress_bar=progress_bar,
        progresso_inicio=0.65,
        progresso_fim=1.0
    )

    if progress_bar:
        progress_bar.progress(1.0)

    return (
        arquivos_comprovantes,
        arquivos_sem_comprovantes,
        contadores,
        encontrou_anexo
    )


# ============================================================
# FUNÇÃO PARA FORMATAR TAMANHO
# ============================================================

def formatar_tamanho(tamanho_bytes):

    tamanho_mb = (
        tamanho_bytes
        / 1_000_000
    )

    return f"{tamanho_mb:.2f} MB"


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador e Agrupador de Comprovantes"
)

st.write(
    "Selecione o PDF mensal. O sistema localizará o ANEXO, "
    "separará os comprovantes das demais páginas e "
    "agrupará os PDFs até o limite de 10 MB."
)


# ============================================================
# INFORMAÇÕES
# ============================================================

with st.expander(
    "🔎 Regras utilizadas"
):

    st.write(
        "O sistema identifica:"
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
        "Cada arquivo gerado terá no máximo "
        "10.000.000 bytes (10 MB)."
    )

    st.write(
        "O sistema não cria um PDF para cada página. "
        "Ele junta várias páginas no mesmo PDF até atingir "
        "o limite."
    )


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "Selecione o PDF mensal",
    type=["pdf"]
)


# ============================================================
# PROCESSAR
# ============================================================

if arquivo is not None:

    tamanho_upload = len(
        arquivo.getvalue()
    )

    st.info(
        "📄 Arquivo selecionado: "
        f"{arquivo.name} — "
        f"{formatar_tamanho(tamanho_upload)}"
    )

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        progress_bar = st.progress(
            0
        )

        status = st.empty()

        status.info(
            "🔎 Lendo o PDF..."
        )

        try:

            (
                arquivos_comprovantes,
                arquivos_sem_comprovantes,
                contadores,
                encontrou_anexo
            ) = processar_pdf(
                arquivo,
                progress_bar
            )

            # =================================================
            # SALVA RESULTADO
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
                "encontrou_anexo"
            ] = encontrou_anexo

            status.success(
                "✅ Processamento concluído!"
            )

        except Exception as erro:

            status.error(
                "❌ Ocorreu um erro durante o processamento."
            )

            st.exception(
                erro
            )

        finally:

            gc.collect()


# ============================================================
# RESULTADOS
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
    # ANEXO
    # ========================================================

    if encontrou_anexo:

        st.success(
            "✅ ANEXO localizado."
        )

    else:

        st.warning(
            "⚠️ A palavra ANEXO não foi encontrada."
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
        "📦 COMPROVANTES"
    )

    if arquivos_comprovantes:

        st.write(
            f"Total de arquivos: "
            f"**{len(arquivos_comprovantes)}**"
        )

        for arquivo_info in (
            arquivos_comprovantes
        ):

            nome = arquivo_info[
                "nome"
            ]

            dados = arquivo_info[
                "dados"
            ]

            tamanho = arquivo_info[
                "tamanho"
            ]

            tamanho_mb = (
                tamanho
                / 1_000_000
            )

            # -----------------------------------------------
            # Verifica limite
            # -----------------------------------------------

            if tamanho <= LIMITE_BYTES:

                st.success(
                    f"✅ {nome} — "
                    f"{tamanho_mb:.2f} MB "
                    f"/ 10,00 MB"
                )

            else:

                st.warning(
                    f"⚠️ {nome} — "
                    f"{tamanho_mb:.2f} MB "
                    f"/ 10,00 MB"
                )

            st.download_button(
                label=f"⬇️ Baixar {nome}",
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"download_comp_{nome}",
                use_container_width=True
            )

    else:

        st.info(
            "Nenhum comprovante encontrado."
        )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 SEM COMPROVANTES"
    )

    if arquivos_sem_comprovantes:

        st.write(
            f"Total de arquivos: "
            f"**{len(arquivos_sem_comprovantes)}**"
        )

        for arquivo_info in (
            arquivos_sem_comprovantes
        ):

            nome = arquivo_info[
                "nome"
            ]

            dados = arquivo_info[
                "dados"
            ]

            tamanho = arquivo_info[
                "tamanho"
            ]

            tamanho_mb = (
                tamanho
                / 1_000_000
            )

            # -----------------------------------------------
            # Verifica limite
            # -----------------------------------------------

            if tamanho <= LIMITE_BYTES:

                st.success(
                    f"✅ {nome} — "
                    f"{tamanho_mb:.2f} MB "
                    f"/ 10,00 MB"
                )

            else:

                st.warning(
                    f"⚠️ {nome} — "
                    f"{tamanho_mb:.2f} MB "
                    f"/ 10,00 MB"
                )

            st.download_button(
                label=f"⬇️ Baixar {nome}",
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"download_sem_{nome}",
                use_container_width=True
            )

    else:

        st.success(
            "Não existem páginas sem comprovantes."
        )
