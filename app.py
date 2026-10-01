import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile
import re
import unicodedata


# ============================================================
# CONFIGURAÇÃO
# ============================================================

LIMITE_ZIP = 10 * 1024 * 1024  # 10 MB


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """Remove acentos e normaliza o texto para facilitar a identificação."""
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


def identificar_comprovante(texto):
    """
    Identifica se a página contém o início de um comprovante.
    Retorna o tipo ou None.
    """

    texto = normalizar_texto(texto)

    # PIX
    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # TRANSFERÊNCIA
    if (
        "COMPROVANTE DE TRANSFERENCIA" in texto
        or "COMPROVANTE TRANSFERENCIA" in texto
    ):
        return "TRANSFERENCIA"

    # TRANSAÇÃO BANCÁRIA
    if (
        "COMPROVANTE DE TRANSACAO BANCARIA" in texto
        or "COMPROVANTE TRANSACAO BANCARIA" in texto
    ):
        return "TRANSACAO_BANCARIA"

    return None


def criar_pdf_paginas(reader, paginas):
    """
    Cria um PDF somente com as páginas informadas.
    """

    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(reader.pages[pagina])

    buffer = BytesIO()
    writer.write(buffer)

    return buffer.getvalue()


def criar_zip_10mb(arquivos):
    """
    Recebe uma lista:
        [(nome_arquivo, bytes), ...]

    e cria vários ZIPs, cada um com no máximo 10 MB,
    quando possível.
    """

    zips = []
    arquivos_atual = []

    def gerar_zip(lista_arquivos):
        buffer = BytesIO()

        with zipfile.ZipFile(
            buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6
        ) as zip_file:

            for nome, dados in lista_arquivos:
                zip_file.writestr(nome, dados)

        return buffer.getvalue()

    for nome, dados in arquivos:

        # Testa se o arquivo sozinho já ultrapassa 10 MB
        zip_teste = gerar_zip([(nome, dados)])

        if len(zip_teste) > LIMITE_ZIP:
            # Se um comprovante individual já for maior que 10 MB,
            # ele será colocado sozinho.
            if arquivos_atual:
                zips.append(gerar_zip(arquivos_atual))
                arquivos_atual = []

            zips.append(zip_teste)
            continue

        # Testa adicionar o arquivo ao ZIP atual
        tentativa = arquivos_atual + [(nome, dados)]

        zip_teste = gerar_zip(tentativa)

        if len(zip_teste) <= LIMITE_ZIP:
            arquivos_atual.append((nome, dados))

        else:
            # Fecha o ZIP atual
            if arquivos_atual:
                zips.append(gerar_zip(arquivos_atual))

            # Começa um novo ZIP
            arquivos_atual = [(nome, dados)]

    # Fecha o último ZIP
    if arquivos_atual:
        zips.append(gerar_zip(arquivos_atual))

    return zips


# ============================================================
# EXTRAÇÃO DOS COMPROVANTES
# ============================================================

def extrair_comprovantes(arquivo_pdf):
    """
    Percorre o PDF e extrai somente os comprovantes.

    Regra:
    - Uma página contendo o cabeçalho de um comprovante inicia um comprovante.
    - As páginas seguintes pertencem ao comprovante até encontrar
      o próximo cabeçalho de comprovante.
    - Páginas antes do primeiro comprovante são ignoradas.
    """

    reader = PdfReader(arquivo_pdf)

    comprovantes = []

    comprovante_atual = None
    paginas_atual = []

    for numero_pagina, pagina in enumerate(reader.pages):

        try:
            texto = pagina.extract_text() or ""
        except Exception:
            texto = ""

        tipo = identificar_comprovante(texto)

        # ----------------------------------------------------
        # Encontrou o início de um novo comprovante
        # ----------------------------------------------------
        if tipo:

            # Salva o comprovante anterior
            if comprovante_atual is not None and paginas_atual:
                comprovantes.append({
                    "tipo": comprovante_atual,
                    "paginas": paginas_atual.copy()
                })

            # Inicia novo comprovante
            comprovante_atual = tipo
            paginas_atual = [numero_pagina]

        # ----------------------------------------------------
        # Página de continuação de um comprovante
        # ----------------------------------------------------
        elif comprovante_atual is not None:
            paginas_atual.append(numero_pagina)

        # ----------------------------------------------------
        # Antes do primeiro comprovante:
        # IGNORA
        # ----------------------------------------------------
        else:
            continue

    # Salva o último comprovante
    if comprovante_atual is not None and paginas_atual:
        comprovantes.append({
            "tipo": comprovante_atual,
            "paginas": paginas_atual.copy()
        })

    return reader, comprovantes


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Extrator de Comprovantes",
    page_icon="📄",
    layout="centered"
)

st.title("📄 Extrator de Comprovantes")

st.write(
    "Envie o PDF e o sistema irá extrair **somente os comprovantes** "
    "encontrados no documento."
)

arquivo = st.file_uploader(
    "Selecione o PDF",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo is not None:

    if st.button("🔎 Extrair somente os comprovantes", type="primary"):

        with st.spinner("Analisando o PDF..."):

            try:

                # Lê o PDF
                reader, comprovantes = extrair_comprovantes(arquivo)

                if not comprovantes:
                    st.error(
                        "Nenhum comprovante foi identificado no PDF."
                    )
                    st.stop()

                arquivos_saida = []

                contadores = {
                    "PIX": 0,
                    "TRANSFERENCIA": 0,
                    "TRANSACAO_BANCARIA": 0
                }

                # ------------------------------------------------
                # CRIA CADA COMPROVANTE INDIVIDUALMENTE
                # ------------------------------------------------

                for indice, comprovante in enumerate(comprovantes, start=1):

                    tipo = comprovante["tipo"]
                    paginas = comprovante["paginas"]

                    contadores[tipo] += 1

                    numero_tipo = contadores[tipo]

                    pdf_bytes = criar_pdf_paginas(
                        reader,
                        paginas
                    )

                    # Nome do arquivo
                    nome_pdf = (
                        f"{tipo}_{numero_tipo:04d}.pdf"
                    )

                    arquivos_saida.append(
                        (nome_pdf, pdf_bytes)
                    )

                # ------------------------------------------------
                # CRIA OS ZIPS DE ATÉ 10 MB
                # ------------------------------------------------

                zips = criar_zip_10mb(arquivos_saida)

                # Guarda no session state
                st.session_state["zips_comprovantes"] = zips
                st.session_state["total_comprovantes"] = len(
                    comprovantes
                )
                st.session_state["contadores"] = contadores

            except Exception as e:

                st.error(
                    f"Erro ao processar o arquivo: {e}"
                )


# ============================================================
# RESULTADO
# ============================================================

if "total_comprovantes" in st.session_state:

    st.success(
        f"✅ {st.session_state['total_comprovantes']} "
        f"comprovante(s) encontrado(s)."
    )

    contadores = st.session_state["contadores"]

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
            contadores["TRANSACAO_BANCARIA"]
        )

    st.divider()

    st.subheader("📦 Arquivos para download")

    zips = st.session_state["zips_comprovantes"]

    for indice, zip_bytes in enumerate(zips, start=1):

        tamanho_mb = len(zip_bytes) / (1024 * 1024)

        st.download_button(
            label=(
                f"⬇️ Baixar COMPROVANTES_{indice:03d}.zip "
                f"({tamanho_mb:.2f} MB)"
            ),
            data=zip_bytes,
            file_name=f"COMPROVANTES_{indice:03d}.zip",
            mime="application/zip",
            key=f"download_zip_{indice}"
        )

    st.info(
        f"Foram gerados {len(zips)} arquivo(s) ZIP. "
        "Cada ZIP possui até aproximadamente 10 MB."
    )
