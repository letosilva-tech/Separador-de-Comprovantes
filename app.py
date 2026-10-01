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
    page_icon="📄"
)


# ============================================================
# FUNÇÕES
# ============================================================

def remover_acentos(texto: str) -> str:
    """
    Remove acentos do texto.
    
    Exemplo:
    TRANSFERÊNCIA -> TRANSFERENCIA
    PAGAMENTO -> PAGAMENTO
    """
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


def normalizar_texto(texto: str) -> str:
    """
    Normaliza o texto para facilitar a identificação.
    """

    texto = texto.upper()

    # Remove acentos
    texto = remover_acentos(texto)

    # Remove quebras de linha e espaços duplicados
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def eh_inicio_comprovante(pagina) -> bool:
    """
    Identifica se a página representa o início
    de um novo comprovante.

    Tipos aceitos:

    - COMPROVANTE PIX
    - COMPROVANTE DE TRANSFERENCIA
    """

    texto = pagina.extract_text() or ""

    texto = normalizar_texto(texto)

    tipos_comprovante = [
        "COMPROVANTE PIX",
        "COMPROVANTE DE TRANSFERENCIA",
    ]

    for tipo in tipos_comprovante:

        if tipo in texto:
            return True

    return False


def is_pagina_em_branco(pagina) -> bool:
    """
    Retorna True se a página não possuir
    texto nem imagens.
    """

    texto = pagina.extract_text() or ""

    tem_imagens = len(pagina.images) > 0

    return not texto.strip() and not tem_imagens


def identificar_tipo_comprovante(pagina) -> str:
    """
    Identifica o tipo do comprovante.
    """

    texto = pagina.extract_text() or ""

    texto = normalizar_texto(texto)

    if "COMPROVANTE PIX" in texto:
        return "PIX"

    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    return "OUTRO"


def separar_comprovantes(leitor, progresso_barra, status_texto):
    """
    Percorre todas as páginas e agrupa as páginas
    pertencentes a cada comprovante.

    Um novo comprovante começa quando a página
    contém:

    COMPROVANTE PIX

    ou

    COMPROVANTE DE TRANSFERENCIA
    """

    comprovantes = []

    comprovante_atual = []

    tipo_atual = None

    paginas_brancas = 0

    total_paginas = len(leitor.pages)

    for idx, pagina in enumerate(leitor.pages):

        numero_pagina = idx + 1

        # ----------------------------------------------------
        # Atualiza progresso
        # ----------------------------------------------------

        percentual = numero_pagina / total_paginas

        progresso_barra.progress(
            percentual
        )

        status_texto.text(
            f"🔍 Analisando página "
            f"{numero_pagina} de {total_paginas}..."
        )

        # ----------------------------------------------------
        # Verifica página em branco
        # ----------------------------------------------------

        if is_pagina_em_branco(pagina):

            paginas_brancas += 1

            continue

        # ----------------------------------------------------
        # Verifica se é início de novo comprovante
        # ----------------------------------------------------

        if eh_inicio_comprovante(pagina):

            # Se já existe comprovante em andamento,
            # salva o comprovante anterior
            if comprovante_atual:

                comprovantes.append({
                    "tipo": tipo_atual,
                    "paginas": comprovante_atual
                })

            # Inicia novo comprovante
            comprovante_atual = [pagina]

            tipo_atual = identificar_tipo_comprovante(
                pagina
            )

        else:

            # Página pertence ao comprovante atual
            if comprovante_atual:

                comprovante_atual.append(
                    pagina
                )

    # --------------------------------------------------------
    # Salva o último comprovante
    # --------------------------------------------------------

    if comprovante_atual:

        comprovantes.append({
            "tipo": tipo_atual,
            "paginas": comprovante_atual
        })

    return comprovantes, paginas_brancas


# ============================================================
# INTERFACE
# ============================================================

st.title("📄 Separador de Comprovantes")

st.write(
    """
    Selecione um único arquivo PDF contendo vários comprovantes.

    O sistema identifica automaticamente os seguintes tipos:

    - **COMPROVANTE PIX**
    - **COMPROVANTE DE TRANSFERÊNCIA**

    Cada comprovante pode possuir uma ou várias páginas.
    """
)


arquivo_pdf = st.file_uploader(
    "Selecione o arquivo PDF",
    type=["pdf"]
)


# ============================================================
# RESET
# ============================================================

if arquivo_pdf is None:

    st.session_state.pop(
        "zip_comprovantes",
        None
    )

    st.session_state.pop(
        "quantidade",
        None
    )

    st.session_state.pop(
        "ignoradas",
        None
    )

    st.session_state.pop(
        "pix",
        None
    )

    st.session_state.pop(
        "transferencias",
        None
    )


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo_pdf is not None:

    try:

        leitor = PdfReader(arquivo_pdf)

        total_paginas = len(leitor.pages)

        st.success(
            f"✅ Arquivo selecionado: "
            f"{arquivo_pdf.name}"
        )

        st.info(
            f"📄 O arquivo original contém "
            f"{total_paginas} páginas."
        )

        if st.button(
            "🔄 Separar Comprovantes",
            type="primary"
        ):

            inicio = time.time()

            st.divider()

            status_texto = st.empty()

            progresso_barra = st.progress(0)

            # ------------------------------------------------
            # Identificação dos comprovantes
            # ------------------------------------------------

            comprovantes, paginas_brancas = (
                separar_comprovantes(
                    leitor,
                    progresso_barra,
                    status_texto
                )
            )

            # ------------------------------------------------
            # Nenhum comprovante encontrado
            # ------------------------------------------------

            if not comprovantes:

                status_texto.empty()

                st.warning(
                    "⚠️ Nenhum comprovante foi identificado."
                )

                st.info(
                    """
                    O sistema procura pelas expressões:

                    • COMPROVANTE PIX

                    • COMPROVANTE DE TRANSFERENCIA

                    Verifique se o PDF permite selecionar
                    o texto. Se o PDF for somente imagem,
                    será necessário utilizar OCR.
                    """
                )

            else:

                # ------------------------------------------------
                # Cria ZIP
                # ------------------------------------------------

                status_texto.text(
                    "📦 Gerando arquivos PDF..."
                )

                zip_buffer = BytesIO()

                quantidade_pix = 0
                quantidade_transferencia = 0

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    for numero, comprovante in enumerate(
                        comprovantes,
                        start=1
                    ):

                        paginas = comprovante[
                            "paginas"
                        ]

                        tipo = comprovante[
                            "tipo"
                        ]

                        # ----------------------------------------
                        # Conta os tipos
                        # ----------------------------------------

                        if tipo == "PIX":

                            quantidade_pix += 1

                        elif tipo == "TRANSFERENCIA":

                            quantidade_transferencia += 1

                        # ----------------------------------------
                        # Cria PDF
                        # ----------------------------------------

                        escritor = PdfWriter()

                        for pagina in paginas:

                            escritor.add_page(
                                pagina
                            )

                        pdf_buffer = BytesIO()

                        escritor.write(
                            pdf_buffer
                        )

                        # ----------------------------------------
                        # Nome do arquivo
                        # ----------------------------------------

                        if tipo == "PIX":

                            nome_pdf = (
                                f"comprovante_PIX_"
                                f"{numero:03d}.pdf"
                            )

                        elif tipo == "TRANSFERENCIA":

                            nome_pdf = (
                                f"comprovante_TRANSFERENCIA_"
                                f"{numero:03d}.pdf"
                            )

                        else:

                            nome_pdf = (
                                f"comprovante_"
                                f"{numero:03d}.pdf"
                            )

                        zip_file.writestr(
                            nome_pdf,
                            pdf_buffer.getvalue()
                        )

                # ------------------------------------------------
                # Salva resultados
                # ------------------------------------------------

                st.session_state[
                    "zip_comprovantes"
                ] = zip_buffer.getvalue()

                st.session_state[
                    "quantidade"
                ] = len(comprovantes)

                st.session_state[
                    "ignoradas"
                ] = paginas_brancas

                st.session_state[
                    "pix"
                ] = quantidade_pix

                st.session_state[
                    "transferencias"
                ] = quantidade_transferencia

                tempo_total = time.time() - inicio

                progresso_barra.progress(
                    1.0
                )

                status_texto.text(
                    "✅ Processamento concluído!"
                )

                # ------------------------------------------------
                # Resultado
                # ------------------------------------------------

                st.success(
                    f"✅ {len(comprovantes)} "
                    f"comprovante(s) identificado(s)."
                )

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.metric(
                        "Total",
                        len(comprovantes)
                    )

                with col2:

                    st.metric(
                        "PIX",
                        quantidade_pix
                    )

                with col3:

                    st.metric(
                        "Transferência",
                        quantidade_transferencia
                    )

                st.info(
                    f"⏱️ Tempo de processamento: "
                    f"{tempo_total:.1f} segundos"
                )

                if paginas_brancas > 0:

                    st.warning(
                        f"🗑️ {paginas_brancas} "
                        f"página(s) em branco foram ignoradas."
                    )

    except Exception as erro:

        st.error(
            f"❌ Erro ao processar o PDF: {erro}"
        )


# ============================================================
# DOWNLOAD
# ============================================================

if (
    arquivo_pdf is not None
    and "zip_comprovantes" in st.session_state
):

    st.divider()

    quantidade = st.session_state[
        "quantidade"
    ]

    pix = st.session_state.get(
        "pix",
        0
    )

    transferencias = st.session_state.get(
        "transferencias",
        0
    )

    st.success(
        f"📦 {quantidade} comprovante(s) "
        f"pronto(s) para download."
    )

    st.write(
        f"""
        **Resumo:**

        - 🔵 PIX: **{pix}**
        - 🟢 Transferências: **{transferencias}**
        - 📄 Total: **{quantidade}**
        """
    )

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state[
            "zip_comprovantes"
        ],
        file_name="comprovantes_separados.zip",
        mime="application/zip"
    )
