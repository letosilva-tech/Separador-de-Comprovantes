import streamlit as st
from pypdf import PdfReader


st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄"
)


st.title("📄 Separador de Comprovantes")

st.write(
    "Selecione um único arquivo PDF contendo todos os comprovantes "
    "de pagamento."
)


arquivo_pdf = st.file_uploader(
    "Selecione o arquivo PDF",
    type=["pdf"]
)


if arquivo_pdf is not None:

    st.success(f"Arquivo selecionado: {arquivo_pdf.name}")

    try:
        leitor = PdfReader(arquivo_pdf)

        quantidade_paginas = len(leitor.pages)

        st.info(
            f"📄 O arquivo possui {quantidade_paginas} páginas."
        )

    except Exception as erro:

        st.error(
            f"Não foi possível ler o arquivo PDF: {erro}"
        )
