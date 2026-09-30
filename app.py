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

        # Lê o PDF original
        arquivo_bytes = arquivo_pdf.getvalue()

        leitor = PdfReader(
            BytesIO(arquivo_bytes)
        )

        quantidade_paginas = len(leitor.pages)

        st.success(
            f"✅ Arquivo selecionado: {arquivo_pdf.name}"
        )

        st.info(
            f"📄 O arquivo possui {quantidade_paginas} páginas."
        )

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

                    # Cria um novo PDF
                    escritor = PdfWriter()

                    # Copia a página diretamente do PDF original
                    escritor.add_page(
                        leitor.pages[numero]
                    )

                    # Salva o PDF individual
                    pdf_buffer = BytesIO()

                    escritor.write(
                        pdf_buffer
                    )

                    pdf_buffer.seek(0)

                    nome_pdf = (
                        f"comprovante_{numero + 1:03d}.pdf"
                    )

                    zip_file.writestr(
                        nome_pdf,
                        pdf_buffer.getvalue()
                    )

                    progresso.progress(
                        (numero + 1) /
                        quantidade_paginas
                    )

            # Salva o ZIP na sessão
            st.session_state[
                "zip_comprovantes"
            ] = zip_buffer.getvalue()

            st.session_state[
                "quantidade"
            ] = quantidade_paginas

            st.success(
                f"✅ {quantidade_paginas} páginas "
                "foram separadas."
            )

    except Exception as erro:

        st.error(
            f"❌ Erro ao processar o PDF: {erro}"
        )


if "zip_comprovantes" in st.session_state:

    st.success(
        f"📦 {st.session_state['quantidade']} "
        "arquivos estão prontos."
    )

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state[
            "zip_comprovantes"
        ],
        file_name="comprovantes_separados.zip",
        mime="application/zip"
    )
