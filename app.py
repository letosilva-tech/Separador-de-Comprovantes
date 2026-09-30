import zipfile
from io import BytesIO
import streamlit as st
from pypdf import PdfReader, PdfWriter


def is_pagina_em_branco(pagina) -> bool:
    """Verifica se a página não possui texto legível nem imagens."""
    texto = pagina.extract_text() or ""
    tem_imagens = len(pagina.images) > 0
    
    # Se não tem texto significativo nem imagens, considera em branco
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

# Limpa o estado quando o arquivo é removido pelo usuário
if arquivo_pdf is None:
    st.session_state.pop("zip_comprovantes", None)
    st.session_state.pop("quantidade", None)
    st.session_state.pop("ignoradas", None)

if arquivo_pdf is not None:
    try:
        leitor = PdfReader(arquivo_pdf)
        total_paginas = len(leitor.pages)

        st.success(f"✅ Arquivo selecionado: {arquivo_pdf.name}")
        st.info(f"📄 O arquivo possui {total_paginas} páginas no total.")

        # Opção para o usuário escolher se quer descartar páginas em branco
        ignorar_em_branco = st.checkbox(
            "Ignorar páginas em branco automaticamente", 
            value=True
        )

        if st.button("🔄 Separar comprovantes", type="primary"):
            zip_buffer = BytesIO()
            comprovantes_gerados = 0
            paginas_ignoradas = 0

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                progresso = st.progress(0.0)

                for idx, pagina in enumerate(leitor.pages):
                    # Valida se a página deve ser ignorada
                    if ignorar_em_branco and is_pagina_em_branco(pagina):
                        paginas_ignoradas += 1
                    else:
                        comprovantes_gerados += 1
                        
                        escritor = PdfWriter()
                        escritor.add_page(pagina)

                        pdf_buffer = BytesIO()
                        escritor.write(pdf_buffer)

                        nome_pdf = f"comprovante_{comprovantes_gerados:03d}.pdf"
                        zip_file.writestr(nome_pdf, pdf_buffer.getvalue())

                    progresso.progress((idx + 1) / total_paginas)

            if comprovantes_gerados == 0:
                st.warning("⚠️ Nenhuma página válida encontrada. Todas parecem estar em branco.")
            else:
                st.session_state["zip_comprovantes"] = zip_buffer.getvalue()
                st.session_state["quantidade"] = comprovantes_gerados
                st.session_state["ignoradas"] = paginas_ignoradas
                
                st.success(
                    f"✅ Processamento concluído! {comprovantes_gerados} comprovantes gerados."
                )

    except Exception as erro:
        st.error(f"❌ Erro ao processar o PDF: {erro}")

# Exibe a área de download caso o arquivo ZIP tenha sido gerado
if arquivo_pdf is not None and "zip_comprovantes" in st.session_state:
    st.divider()
    
    msg_status = f"📦 {st.session_state['quantidade']} comprovante(s) pronto(s) para download."
    if st.session_state.get("ignoradas", 0) > 0:
        msg_status += f" ({st.session_state['ignoradas']} página(s) em branco ignorada(s))"
        
    st.success(msg_status)

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state["zip_comprovantes"],
        file_name="comprovantes_separados.zip",
        mime="application/zip"
    )
