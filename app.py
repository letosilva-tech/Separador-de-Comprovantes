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
    page_icon="📄",
    layout="wide"
)


# ============================================================
# NORMALIZAÇÃO DO TEXTO
# ============================================================

def normalizar_texto(texto: str) -> str:
    """
    Normaliza o texto:
    - transforma em maiúsculo
    - remove acentos
    - transforma quebras de linha em espaços
    - remove espaços duplicados
    """

    texto = texto.upper()

    # Remove acentos
    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    # Junta quebras de linha, tabs e espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


# ============================================================
# IDENTIFICA O TIPO DO COMPROVANTE
# ============================================================

def identificar_tipo_comprovante(texto: str):
    """
    Identifica:

    COMPROVANTE PIX

    COMPROVANTE DE TRANSFERENCIA

    COMPROVANTE DE TRANSFERÊNCIA

    Também aceita caso o PDF quebre as palavras
    em linhas diferentes.
    """

    texto = normalizar_texto(texto)

    # --------------------------------------------------------
    # PIX
    # --------------------------------------------------------

    if re.search(
        r"COMPROVANTE\s+PIX",
        texto
    ):
        return "PIX"

    # --------------------------------------------------------
    # TRANSFERÊNCIA
    # --------------------------------------------------------

    if re.search(
        r"COMPROVANTE\s+(DE\s+)?TRANSFERENCIA",
        texto
    ):
        return "TRANSFERENCIA"

    return None


# ============================================================
# VERIFICA SE A PÁGINA ESTÁ EM BRANCO
# ============================================================

def is_pagina_em_branco(pagina):
    """
    Retorna True somente se a página não possuir
    texto nem imagens.
    """

    texto = pagina.extract_text() or ""

    tem_imagens = len(pagina.images) > 0

    return (
        not texto.strip()
        and not tem_imagens
    )


# ============================================================
# SEPARA OS COMPROVANTES
# ============================================================

def separar_comprovantes(
    leitor,
    progresso,
    status
):

    comprovantes = []

    comprovante_atual = []

    tipo_atual = None

    pagina_inicio = None

    paginas_brancas = 0

    paginas_sem_comprovante = []

    total_paginas = len(leitor.pages)

    # ========================================================
    # PERCORRE TODAS AS PÁGINAS
    # ========================================================

    for indice, pagina in enumerate(leitor.pages):

        numero_pagina = indice + 1

        # ----------------------------------------------------
        # Atualiza progresso
        # ----------------------------------------------------

        progresso.progress(
            numero_pagina / total_paginas
        )

        status.text(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )

        # ----------------------------------------------------
        # Extrai texto
        # ----------------------------------------------------

        texto = pagina.extract_text() or ""

        # ----------------------------------------------------
        # Verifica se começa novo comprovante
        # ----------------------------------------------------

        tipo = identificar_tipo_comprovante(
            texto
        )

        # ====================================================
        # NOVO COMPROVANTE
        # ====================================================

        if tipo is not None:

            # Se já havia um comprovante aberto,
            # salva o anterior
            if comprovante_atual:

                comprovantes.append({
                    "tipo": tipo_atual,
                    "paginas": comprovante_atual,
                    "pagina_inicio": pagina_inicio,
                    "pagina_fim": numero_pagina - 1
                })

            # Inicia novo comprovante
            comprovante_atual = [
                pagina
            ]

            tipo_atual = tipo

            pagina_inicio = numero_pagina

            continue

        # ====================================================
        # PÁGINA EM BRANCO
        # ====================================================

        if is_pagina_em_branco(pagina):

            paginas_brancas += 1

            continue

        # ====================================================
        # CONTINUAÇÃO DO COMPROVANTE
        # ====================================================

        if comprovante_atual:

            comprovante_atual.append(
                pagina
            )

        else:

            # Página que apareceu antes de qualquer
            # comprovante ser encontrado
            paginas_sem_comprovante.append(
                numero_pagina
            )

    # ========================================================
    # SALVA O ÚLTIMO COMPROVANTE
    # ========================================================

    if comprovante_atual:

        comprovantes.append({
            "tipo": tipo_atual,
            "paginas": comprovante_atual,
            "pagina_inicio": pagina_inicio,
            "pagina_fim": total_paginas
        })

    return (
        comprovantes,
        paginas_brancas,
        paginas_sem_comprovante
    )


# ============================================================
# TELA
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.write(
    """
    Selecione um único arquivo PDF contendo vários comprovantes.

    O sistema identifica automaticamente:

    🔵 **COMPROVANTE PIX**

    🟢 **COMPROVANTE DE TRANSFERÊNCIA**

    Cada comprovante pode possuir uma ou várias páginas.
    """
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_pdf = st.file_uploader(
    "Selecione o arquivo PDF",
    type=["pdf"]
)


# ============================================================
# LIMPA RESULTADOS QUANDO O ARQUIVO É REMOVIDO
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
        "pix",
        None
    )

    st.session_state.pop(
        "transferencias",
        None
    )

    st.session_state.pop(
        "ignoradas",
        None
    )

    st.session_state.pop(
        "detalhes",
        None
    )


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo_pdf is not None:

    try:

        leitor = PdfReader(
            arquivo_pdf
        )

        total_paginas = len(
            leitor.pages
        )

        st.success(
            f"✅ Arquivo selecionado: "
            f"{arquivo_pdf.name}"
        )

        st.info(
            f"📄 O arquivo possui "
            f"**{total_paginas} páginas**."
        )

        # ====================================================
        # BOTÃO
        # ====================================================

        if st.button(
            "🔄 Separar Comprovantes",
            type="primary",
            use_container_width=True
        ):

            inicio = time.time()

            st.divider()

            status = st.empty()

            progresso = st.progress(0)

            # =================================================
            # ANALISA PDF
            # =================================================

            (
                comprovantes,
                paginas_brancas,
                paginas_sem_comprovante
            ) = separar_comprovantes(
                leitor,
                progresso,
                status
            )

            # =================================================
            # NENHUM ENCONTRADO
            # =================================================

            if not comprovantes:

                status.error(
                    "❌ Nenhum comprovante foi encontrado."
                )

                st.warning(
                    """
                    Não foi possível identificar:

                    • COMPROVANTE PIX

                    • COMPROVANTE DE TRANSFERÊNCIA
                    """
                )

                st.info(
                    """
                    Se o PDF for escaneado como imagem,
                    será necessário utilizar OCR.
                    """
                )

            else:

                # =================================================
                # CRIA ZIP
                # =================================================

                status.text(
                    "📦 Criando arquivos dos comprovantes..."
                )

                zip_buffer = BytesIO()

                quantidade_pix = 0

                quantidade_transferencia = 0

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    # ---------------------------------------------
                    # Percorre cada comprovante
                    # ---------------------------------------------

                    for numero, comprovante in enumerate(
                        comprovantes,
                        start=1
                    ):

                        tipo = comprovante[
                            "tipo"
                        ]

                        paginas = comprovante[
                            "paginas"
                        ]

                        # -----------------------------------------
                        # Contadores
                        # -----------------------------------------

                        if tipo == "PIX":

                            quantidade_pix += 1

                        elif tipo == "TRANSFERENCIA":

                            quantidade_transferencia += 1

                        # -----------------------------------------
                        # Cria PDF
                        # -----------------------------------------

                        escritor = PdfWriter()

                        for pagina in paginas:

                            escritor.add_page(
                                pagina
                            )

                        pdf_buffer = BytesIO()

                        escritor.write(
                            pdf_buffer
                        )

                        # -----------------------------------------
                        # Nome do arquivo
                        # -----------------------------------------

                        if tipo == "PIX":

                            nome = (
                                f"comprovante_PIX_"
                                f"{numero:03d}.pdf"
                            )

                        elif tipo == "TRANSFERENCIA":

                            nome = (
                                f"comprovante_TRANSFERENCIA_"
                                f"{numero:03d}.pdf"
                            )

                        else:

                            nome = (
                                f"comprovante_"
                                f"{numero:03d}.pdf"
                            )

                        # -----------------------------------------
                        # Adiciona ao ZIP
                        # -----------------------------------------

                        zip_file.writestr(
                            nome,
                            pdf_buffer.getvalue()
                        )

                # =================================================
                # SALVA RESULTADOS
                # =================================================

                st.session_state[
                    "zip_comprovantes"
                ] = zip_buffer.getvalue()

                st.session_state[
                    "quantidade"
                ] = len(comprovantes)

                st.session_state[
                    "pix"
                ] = quantidade_pix

                st.session_state[
                    "transferencias"
                ] = quantidade_transferencia

                st.session_state[
                    "ignoradas"
                ] = paginas_brancas

                st.session_state[
                    "detalhes"
                ] = comprovantes

                # =================================================
                # TEMPO
                # =================================================

                tempo = time.time() - inicio

                progresso.progress(1.0)

                status.success(
                    "✅ Processamento concluído!"
                )

                # =================================================
                # RESUMO
                # =================================================

                st.divider()

                st.subheader(
                    "📊 Resultado"
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
                        "Transferências",
                        quantidade_transferencia
                    )

                st.info(
                    f"⏱️ Tempo de processamento: "
                    f"{tempo:.1f} segundos"
                )

                # =================================================
                # PÁGINAS EM BRANCO
                # =================================================

                if paginas_brancas > 0:

                    st.warning(
                        f"⚠️ {paginas_brancas} "
                        f"página(s) em branco foram ignoradas."
                    )

                # =================================================
                # DIAGNÓSTICO
                # =================================================

                st.divider()

                st.subheader(
                    "🔎 Comprovantes identificados"
                )

                dados = []

                for numero, comprovante in enumerate(
                    comprovantes,
                    start=1
                ):

                    dados.append({
                        "Nº": numero,
                        "Tipo": comprovante[
                            "tipo"
                        ],
                        "Página inicial": comprovante[
                            "pagina_inicio"
                        ],
                        "Página final": comprovante[
                            "pagina_fim"
                        ],
                        "Páginas": len(
                            comprovante[
                                "paginas"
                            ]
                        )
                    })

                st.dataframe(
                    dados,
                    use_container_width=True,
                    hide_index=True
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
    and "zip_comprovantes"
    in st.session_state
):

    st.divider()

    st.subheader(
        "📦 Download"
    )

    quantidade = st.session_state[
        "quantidade"
    ]

    pix = st.session_state[
        "pix"
    ]

    transferencias = st.session_state[
        "transferencias"
    ]

    st.success(
        f"✅ {quantidade} comprovante(s) "
        f"foram separados."
    )

    st.write(
        f"🔵 PIX: **{pix}**"
    )

    st.write(
        f"🟢 Transferências: **{transferencias}**"
    )

    st.download_button(
        label="📦 Baixar comprovantes em ZIP",
        data=st.session_state[
            "zip_comprovantes"
        ],
        file_name="comprovantes_separados.zip",
        mime="application/zip",
        use_container_width=True
    )
