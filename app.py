import zipfile
from io import BytesIO
import streamlit as st
from pypdf import PdfReader, PdfWriter


def is_pagina_em_branco(pagina) -> bool:
    """Retorna True se a página não contiver texto visível nem imagens."""
    texto = pagina.extract_text() or ""
    tem_imagens = len(pagina.images) > 0
    return not texto.strip() and not tem_imagens


st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄"
)

st.title("📄 Separador de Comprovantes")

st.write(
    "Selecione um único arquivo PDF contendo todos os comprovantes de pagamento."
)

arquivo_pdf = st.file_uploader(
    "Selecione o arquivo PDF",
    type=["pdf"]
)

# Reseta as variáveis quando o arquivo é removido
if arquivo_pdf is None:
    st.session_state.pop("zip_comprovantes", None)
    st.session_state.pop("quantidade", None)
    st.session_state.pop("ignoradas", None)

if arquivo_pdf is not None:
    try:
        leitor = PdfReader(arquivo_pdf)
        total_paginas = len(leitor.pages)

        st.success(f"✅ Arquivo selecionado: {arquivo_pdf.name}")
        st.info(f"📄 O arquivo original contém {total_paginas} páginas.")

        if st.button("🔄 Separar e Excluir Em Branco", type="primary"):
            zip_buffer = BytesIO()
            comprovantes_validos = 0
            paginas_excluidas = 0

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                progresso = st.progress(0.0)

                for idx, pagina in enumerate(leitor.pages):
                    # Se a página for em branco, ignora a geração do arquivo
                    if is_pagina_em_branco(pagina):
                        paginas_excluidas += 1
                        progresso.progress((idx + 1) / total_paginas)
                        continue

                    comprovantes_validos += 1

                    escritor = PdfWriter()
                    escritor.add_page(pagina)

                    pdf_buffer = BytesIO()
                    escritor.write(pdf_buffer)

                    nome_pdf = f"comprovante_{comprovantes_validos:03d}.pdf"
                    zip_file.writestr(nome_pdf, pdf_buffer.getvalue())

                    progresso.progress((idx + 1) / total_paginas)

            if comprovantes_validos == 0:
                st.warning("⚠️ Todas as páginas do arquivo foram identificadas como em branco.")
            else:
                st.session_state["zip_comprovantes"] = zip_buffer.getvalue()
                st.session_state["quantidade"] = comprovantes_validos
                st.session_state["ignoradas"] = paginas_excluidas

                st.success("✅ Processamento concluído!")

    except Exception as erro:
        st.error(f"❌ Erro ao processar o PDF: {erro}")

if arquivo_pdf is not None and "zip_comprovantes" in st.session_state:
    st.divider()

    msg = f"📦 {st.session_state['quantidade']} comprovante(s) gerado(s)."
    if st.session_state.get("ignoradas", 0) > 0:
        msg += f" ({st.session_state['ignoradas']} página(s) em branco foram excluída(s))."

    st.success(msg)

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state["zip_comprovantes"],
        file_name="comprovantes_separados.zip",
        mime="application/zip"
    )
