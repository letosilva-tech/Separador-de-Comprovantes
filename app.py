import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import zipfile


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

    st.success(f"✅ Arquivo selecionado: {arquivo_pdf.name}")

    try:
        leitor = PdfReader(arquivo_pdf)

        quantidade_paginas = len(leitor.pages)

        st.info(
            f"📄 O arquivo possui {quantidade_paginas} páginas."
        )

        st.write("")

        if st.button("🔄 Separar comprovantes", type="primary"):

            zip_buffer = BytesIO()

            with zipfile.ZipFile(
                zip_buffer,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zip_file:

                barra = st.progress(0)

                for numero, pagina in enumerate(
                    leitor.pages,
                    start=1
                ):

                    escritor = PdfWriter()

                    escritor.add_page(pagina)

                    pdf_buffer = BytesIO()

                    escritor.write(pdf_buffer)

                    pdf_buffer.seek(0)

                    nome_pdf = f"comprovante_{numero:03d}.pdf"

                    zip_file.writestr(
                        nome_pdf,
                        pdf_buffer.read()
                    )

                    progresso = numero / quantidade_paginas

                    barra.progress(progresso)

            zip_buffer.seek(0)

            st.success(
                f"✅ {quantidade_paginas} comprovantes foram separados!"
            )

            st.download_button(
                label="📦 Baixar comprovantes em ZIP",
                data=zip_buffer,
                file_name="comprovantes_separados.zip",
                mime="application/zip"
            )

    except Exception as erro:

        st.error(
            f"❌ Não foi possível processar o PDF: {erro}"
        )
