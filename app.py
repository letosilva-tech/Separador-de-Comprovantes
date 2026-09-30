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

    try:
        # Guarda o arquivo original em memória
        arquivo_bytes = arquivo_pdf.getvalue()

        leitor = PdfReader(BytesIO(arquivo_bytes))

        quantidade_paginas = len(leitor.pages)

        st.success(
            f"✅ Arquivo selecionado: {arquivo_pdf.name}"
        )

        st.info(
            f"📄 O arquivo possui {quantidade_paginas} páginas."
        )

        st.write("")

        if st.button(
            "🔄 Separar comprovantes",
            type="primary"
        ):

            zip_buffer = BytesIO()

            with zipfile.ZipFile(
                zip_buffer,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zip_file:

                progresso = st.progress(0)

                for numero in range(quantidade_paginas):

                    pagina = leitor.pages[numero]

                    escritor = PdfWriter()

                    escritor.add_page(pagina)

                    pdf_buffer = BytesIO()

                    escritor.write(pdf_buffer)

                    pdf_buffer.seek(0)

                    nome_pdf = (
                        f"comprovante_{numero + 1:03d}.pdf"
                    )

                    zip_file.writestr(
                        nome_pdf,
                        pdf_buffer.getvalue()
                    )

                    progresso.progress(
                        (numero + 1) / quantidade_paginas
                    )

            # Guarda o ZIP para ele não desaparecer
            st.session_state["zip_comprovantes"] = (
                zip_buffer.getvalue()
            )

            st.session_state["quantidade"] = (
                quantidade_paginas
            )

            st.success(
                f"✅ {quantidade_paginas} comprovantes "
                "foram separados!"
            )

    except Exception as erro:

        st.error(
            f"❌ Erro ao processar o PDF: {erro}"
        )


# Mostra o botão de download mesmo depois da atualização
if "zip_comprovantes" in st.session_state:

    st.success(
        f"📦 {st.session_state['quantidade']} "
        "comprovantes estão prontos."
    )

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state["zip_comprovantes"],
        file_name="comprovantes_separados.zip",
        mime="application/zip"
    )
