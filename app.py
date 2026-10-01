import zipfile
from io import BytesIO
import re

import streamlit as st
from pypdf import PdfReader, PdfWriter


def normalizar_texto(texto: str) -> str:
    """Normaliza o texto para facilitar a identificação do comprovante."""
    texto = texto.upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def eh_inicio_comprovante(pagina) -> bool:
    """
    Identifica se a página marca o início de um novo comprovante.
    """
    texto = pagina.extract_text() or ""
    texto = normalizar_texto(texto)

    return "COMPROVANTE DE PAGAMENTO" in texto


def is_pagina_em_branco(pagina) -> bool:
    """
    Retorna True se a página não possuir texto nem imagens.
    """
    texto = pagina.extract_text() or ""
    tem_imagens = len(pagina.images) > 0

    return not texto.strip() and not tem_imagens


def separar_comprovantes(leitor):
    """
    Agrupa as páginas do PDF em comprovantes.

    Um novo comprovante começa sempre que a página
    contém 'COMPROVANTE DE PAGAMENTO'.
    """

    comprovantes = []
    comprovante_atual = []

    paginas_brancas = 0

    for pagina in leitor.pages:

        # Ignora páginas completamente em branco
        if is_pagina_em_branco(pagina):
            paginas_brancas += 1
            continue

        # Verifica se começa um novo comprovante
        if eh_inicio_comprovante(pagina):

            # Se já existe um comprovante em andamento,
            # salva antes de começar o próximo
            if comprovante_atual:
                comprovantes.append(comprovante_atual)

            comprovante_atual = [pagina]

        else:
            # Continua o comprovante atual
            if comprovante_atual:
                comprovante_atual.append(pagina)

    # Salva o último comprovante
    if comprovante_atual:
        comprovantes.append(comprovante_atual)

    return comprovantes, paginas_brancas


st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄"
)

st.title("📄 Separador de Comprovantes")

st.write(
    """
    Selecione um único arquivo PDF contendo vários comprovantes de pagamento.
    
    O sistema identifica cada ocorrência de **COMPROVANTE DE PAGAMENTO**
    e agrupa todas as páginas pertencentes ao respectivo comprovante.
    """
)

arquivo_pdf = st.file_uploader(
    "Selecione o arquivo PDF",
    type=["pdf"]
)


# Reseta os resultados quando o arquivo é removido
if arquivo_pdf is None:
    st.session_state.pop("zip_comprovantes", None)
    st.session_state.pop("quantidade", None)
    st.session_state.pop("ignoradas", None)


if arquivo_pdf is not None:

    try:

        leitor = PdfReader(arquivo_pdf)

        total_paginas = len(leitor.pages)

        st.success(
            f"✅ Arquivo selecionado: {arquivo_pdf.name}"
        )

        st.info(
            f"📄 O arquivo original contém {total_paginas} páginas."
        )

        if st.button(
            "🔄 Separar Comprovantes",
            type="primary"
        ):

            with st.spinner("Processando comprovantes..."):

                comprovantes, paginas_brancas = separar_comprovantes(
                    leitor
                )

                if not comprovantes:

                    st.warning(
                        "⚠️ Nenhum 'COMPROVANTE DE PAGAMENTO' "
                        "foi identificado no arquivo."
                    )

                    st.info(
                        """
                        Verifique se o texto **COMPROVANTE DE PAGAMENTO**
                        realmente existe no PDF e se o PDF permite
                        seleção/extração de texto.
                        """
                    )

                else:

                    zip_buffer = BytesIO()

                    with zipfile.ZipFile(
                        zip_buffer,
                        "w",
                        zipfile.ZIP_DEFLATED
                    ) as zip_file:

                        for numero, paginas in enumerate(
                            comprovantes,
                            start=1
                        ):

                            escritor = PdfWriter()

                            for pagina in paginas:
                                escritor.add_page(pagina)

                            pdf_buffer = BytesIO()

                            escritor.write(pdf_buffer)

                            nome_pdf = (
                                f"comprovante_{numero:03d}.pdf"
                            )

                            zip_file.writestr(
                                nome_pdf,
                                pdf_buffer.getvalue()
                            )

                    st.session_state[
                        "zip_comprovantes"
                    ] = zip_buffer.getvalue()

                    st.session_state[
                        "quantidade"
                    ] = len(comprovantes)

                    st.session_state[
                        "ignoradas"
                    ] = paginas_brancas

                    st.success(
                        "✅ Processamento concluído!"
                    )

    except Exception as erro:

        st.error(
            f"❌ Erro ao processar o PDF: {erro}"
        )


# Área de download
if (
    arquivo_pdf is not None
    and "zip_comprovantes" in st.session_state
):

    st.divider()

    quantidade = st.session_state["quantidade"]
    ignoradas = st.session_state.get("ignoradas", 0)

    msg = (
        f"📦 {quantidade} comprovante(s) identificado(s) "
        f"e separado(s)."
    )

    if ignoradas > 0:

        msg += (
            f" {ignoradas} página(s) em branco "
            f"foram ignorada(s)."
        )

    st.success(msg)

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state["zip_comprovantes"],
        file_name="comprovantes_separados.zip",
        mime="application/zip"
    )
