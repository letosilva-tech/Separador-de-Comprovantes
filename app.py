import streamlit as st
import os
import re
import unicodedata
import tempfile
import shutil
import gc
import time

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
# CONSTANTES
# ============================================================

# 10 MB por ARQUIVO PDF
LIMITE_PDF = 10 * 1024 * 1024


# ============================================================
# INTERFACE
# ============================================================

st.title("📄 Separador de Comprovantes")

st.write(
    """
    O sistema analisa o PDF página por página e identifica:

    🔵 **COMPROVANTE PIX**

    🟢 **COMPROVANTE DE TRANSFERENCIA**

    🟣 **COMPROVANTE DE TRANSACAO BANCARIA**

    Os comprovantes identificados são agrupados em **arquivos PDF
    consolidados de até 10 MB**.

    As páginas que não forem comprovantes também são agrupadas em
    **arquivos PDF consolidados de até 10 MB**.
    """
)

st.info(
    """
    💡 O limite de 10 MB é aplicado diretamente sobre cada arquivo PDF
    consolidado. Não são criados ZIPs.
    """
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = texto.upper()

    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# IDENTIFICA COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    if not texto:
        return None


    # ========================================================
    # 1 - COMPROVANTE PIX
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+PIX\b",
        texto
    ):
        return "PIX"


    if re.search(
        r"\bCOMPROVANTE\s+DE\s+PIX\b",
        texto
    ):
        return "PIX"


    # ========================================================
    # 2 - COMPROVANTE DE TRANSFERENCIA
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+DE\s+TRANSFERENCIA\b",
        texto
    ):
        return "TRANSFERENCIA"


    if re.search(
        r"\bCOMPROVANTE\s+TRANSFERENCIA\b",
        texto
    ):
        return "TRANSFERENCIA"


    # ========================================================
    # 3 - COMPROVANTE DE TRANSACAO BANCARIA
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+DE\s+TRANSACAO\s+BANCARIA\b",
        texto
    ):
        return "TRANSACAO_BANCARIA"


    if re.search(
        r"\bCOMPROVANTE\s+TRANSACAO\s+BANCARIA\b",
        texto
    ):
        return "TRANSACAO_BANCARIA"


    # ========================================================
    # NÃO É COMPROVANTE
    # ========================================================

    return None


# ============================================================
# FORMATA TAMANHO
# ============================================================

def formatar_tamanho(tamanho):

    if tamanho < 1024:

        return f"{tamanho} B"


    if tamanho < 1024 * 1024:

        return (
            f"{tamanho / 1024:.2f} KB"
        )


    return (
        f"{tamanho / (1024 * 1024):.2f} MB"
    )


# ============================================================
# CLASSE PARA CRIAR PDFs CONSOLIDADOS
# ============================================================

class GerenciadorPDF:

    def __init__(
        self,
        pasta_saida,
        prefixo
    ):

        self.pasta_saida = pasta_saida

        self.prefixo = prefixo

        self.numero = 1

        self.writer = PdfWriter()

        self.paginas = 0

        self.arquivos = []

        self.tamanho_atual = 0

        self.caminho_teste = None


    # ========================================================
    # NOME DO PRÓXIMO PDF
    # ========================================================

    def _nome_pdf(self):

        return (
            f"{self.prefixo}_"
            f"{self.numero:03d}.pdf"
        )


    # ========================================================
    # CAMINHO DO PRÓXIMO PDF
    # ========================================================

    def _caminho_pdf(self):

        return os.path.join(
            self.pasta_saida,
            self._nome_pdf()
        )


    # ========================================================
    # TESTA O TAMANHO REAL
    #
    # Cria temporariamente o PDF com as páginas atuais
    # + a nova página.
    #
    # Assim o limite de 10 MB é aplicado ao PDF REAL.
    # ========================================================

    def _testar_writer(
        self,
        writer
    ):

        caminho_teste = os.path.join(
            self.pasta_saida,
            (
                f".teste_{self.prefixo}_"
                f"{os.getpid()}_"
                f"{time.time_ns()}.pdf"
            )
        )


        try:

            with open(
                caminho_teste,
                "wb"
            ) as arquivo:

                writer.write(
                    arquivo
                )


            tamanho = os.path.getsize(
                caminho_teste
            )


            return (
                tamanho,
                caminho_teste
            )


        except Exception:

            if os.path.exists(
                caminho_teste
            ):

                try:

                    os.remove(
                        caminho_teste
                    )

                except Exception:

                    pass

            raise


    # ========================================================
    # REMOVE ARQUIVO TEMPORÁRIO
    # ========================================================

    def _remover_teste(
        self,
        caminho
    ):

        if caminho and os.path.exists(
            caminho
        ):

            try:

                os.remove(
                    caminho
                )

            except Exception:

                pass


    # ========================================================
    # SALVA PDF ATUAL
    # ========================================================

    def _salvar_atual(self):

        if self.paginas == 0:

            return


        caminho_saida = (
            self._caminho_pdf()
        )


        # ----------------------------------------------------
        # O writer atual já foi testado.
        # Escrevemos definitivamente.
        # ----------------------------------------------------

        with open(
            caminho_saida,
            "wb"
        ) as arquivo:

            self.writer.write(
                arquivo
            )


        tamanho = os.path.getsize(
            caminho_saida
        )


        self.arquivos.append(
            {
                "nome":
                    os.path.basename(
                        caminho_saida
                    ),

                "caminho":
                    caminho_saida,

                "tamanho":
                    tamanho,

                "quantidade":
                    self.paginas
            }
        )


        # ----------------------------------------------------
        # Prepara próximo PDF
        # ----------------------------------------------------

        self.numero += 1

        self.writer = PdfWriter()

        self.paginas = 0

        self.tamanho_atual = 0

        gc.collect()


    # ========================================================
    # ADICIONA UMA PÁGINA
    # ========================================================

    def adicionar_pagina(
        self,
        pagina
    ):

        # ----------------------------------------------------
        # Cria um writer candidato
        # ----------------------------------------------------

        writer_teste = PdfWriter()


        # ----------------------------------------------------
        # Copia as páginas que já estão no PDF atual
        # ----------------------------------------------------

        for pagina_atual in self.writer.pages:

            writer_teste.add_page(
                pagina_atual
            )


        # ----------------------------------------------------
        # Adiciona a nova página
        # ----------------------------------------------------

        writer_teste.add_page(
            pagina
        )


        # ----------------------------------------------------
        # Mede o PDF REAL
        # ----------------------------------------------------

        tamanho_teste, caminho_teste = (
            self._testar_writer(
                writer_teste
            )
        )


        # ----------------------------------------------------
        # A NOVA PÁGINA CABE
        # ----------------------------------------------------

        if (
            tamanho_teste
            <=
            LIMITE_PDF
        ):

            self._remover_teste(
                caminho_teste
            )


            # ----------------------------------------------
            # Usa o writer candidato como writer atual
            # ----------------------------------------------

            self.writer = writer_teste

            self.paginas += 1

            self.tamanho_atual = (
                tamanho_teste
            )

            return


        # ----------------------------------------------------
        # NÃO CABE NO PDF ATUAL
        # ----------------------------------------------------

        self._remover_teste(
            caminho_teste
        )


        # ----------------------------------------------------
        # Se já existem páginas:
        # salva o PDF atual
        # e começa outro.
        # ----------------------------------------------------

        if self.paginas > 0:

            self._salvar_atual()


        # ----------------------------------------------------
        # Agora a página entra no NOVO PDF
        # ----------------------------------------------------

        self.writer = PdfWriter()

        self.writer.add_page(
            pagina
        )

        self.paginas = 1


        # ----------------------------------------------------
        # Mede o tamanho dessa página sozinha
        # ----------------------------------------------------

        tamanho_individual, caminho_teste = (
            self._testar_writer(
                self.writer
            )
        )


        self._remover_teste(
            caminho_teste
        )


        self.tamanho_atual = (
            tamanho_individual
        )


    # ========================================================
    # FINALIZA
    # ========================================================

    def finalizar(self):

        if self.paginas > 0:

            self._salvar_atual()


        return self.arquivos


# ============================================================
# PROCESSAMENTO
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar,
    status
):

    inicio = time.time()


    # ========================================================
    # ABRE PDF
    # ========================================================

    status.info(
        "📖 Abrindo PDF..."
    )


    reader = PdfReader(
        caminho_pdf,
        strict=False
    )


    total_paginas = len(
        reader.pages
    )


    # ========================================================
    # PASTA DE SAÍDA
    # ========================================================

    pasta_saida = os.path.join(
        pasta_trabalho,
        "saida"
    )


    os.makedirs(
        pasta_saida,
        exist_ok=True
    )


    # ========================================================
    # GERENCIADORES
    #
    # UM para comprovantes
    # UM para páginas sem comprovantes
    # ========================================================

    pdf_comprovantes = GerenciadorPDF(
        pasta_saida,
        "COMPROVANTES"
    )


    pdf_sem_comprovantes = GerenciadorPDF(
        pasta_saida,
        "SEM_COMPROVANTES"
    )


    # ========================================================
    # CONTADORES
    # ========================================================

    total_comprovantes = 0

    total_sem_comprovantes = 0

    quantidade_pix = 0

    quantidade_transferencia = 0

    quantidade_transacao = 0

    diagnostico = []


    # ========================================================
    # PROCESSA PÁGINA POR PÁGINA
    # ========================================================

    for indice in range(
        total_paginas
    ):

        numero_pagina = (
            indice + 1
        )


        status.info(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )


        # ====================================================
        # PEGA PÁGINA
        # ====================================================

        pagina = reader.pages[
            indice
        ]


        # ====================================================
        # EXTRAI TEXTO
        # ====================================================

        try:

            texto = (
                pagina.extract_text()
            )

        except Exception as erro:

            texto = ""

            diagnostico.append(
                {
                    "pagina":
                        numero_pagina,

                    "tipo":
                        "ERRO_EXTRACAO",

                    "detalhe":
                        str(erro)
                }
            )


        # ====================================================
        # IDENTIFICA TIPO
        # ====================================================

        tipo_comprovante = (
            identificar_comprovante(
                texto
            )
        )


        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo_comprovante:

            total_comprovantes += 1


            if tipo_comprovante == "PIX":

                quantidade_pix += 1


            elif tipo_comprovante == "TRANSFERENCIA":

                quantidade_transferencia += 1


            elif tipo_comprovante == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1


            # ------------------------------------------------
            # ADICIONA A PÁGINA AO PDF CONSOLIDADO
            # ------------------------------------------------

            pdf_comprovantes.adicionar_pagina(
                pagina
            )


            diagnostico.append(
                {
                    "pagina":
                        numero_pagina,

                    "tipo":
                        tipo_comprovante,

                    "arquivo":
                        (
                            pdf_comprovantes
                            ._nome_pdf()
                        ),

                    "tamanho_atual":
                        pdf_comprovantes
                        .tamanho_atual
                }
            )


        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            total_sem_comprovantes += 1


            # ------------------------------------------------
            # ADICIONA AO PDF CONSOLIDADO
            # ------------------------------------------------

            pdf_sem_comprovantes.adicionar_pagina(
                pagina
            )


            diagnostico.append(
                {
                    "pagina":
                        numero_pagina,

                    "tipo":
                        "SEM_COMPROVANTE",

                    "arquivo":
                        (
                            pdf_sem_comprovantes
                            ._nome_pdf()
                        ),

                    "tamanho_atual":
                        pdf_sem_comprovantes
                        .tamanho_atual
                }
            )


        # ====================================================
        # PROGRESSO
        # ====================================================

        progresso = (
            numero_pagina
            /
            total_paginas
        )


        progress_bar.progress(
            progresso
        )


        gc.collect()


    # ========================================================
    # FINALIZA PDFS
    # ========================================================

    arquivos_comprovantes = (
        pdf_comprovantes.finalizar()
    )


    arquivos_sem_comprovantes = (
        pdf_sem_comprovantes.finalizar()
    )


    # ========================================================
    # LIBERA LEITOR
    # ========================================================

    del reader

    gc.collect()


    # ========================================================
    # TEMPO
    # ========================================================

    tempo_total = (
        time.time()
        -
        inicio
    )


    # ========================================================
    # RESULTADO
    # ========================================================

    return {

        "arquivos_comprovantes":
            arquivos_comprovantes,

        "arquivos_sem_comprovantes":
            arquivos_sem_comprovantes,

        "total_paginas":
            total_paginas,

        "total_comprovantes":
            total_comprovantes,

        "total_sem_comprovantes":
            total_sem_comprovantes,

        "quantidade_pix":
            quantidade_pix,

        "quantidade_transferencia":
            quantidade_transferencia,

        "quantidade_transacao":
            quantidade_transacao,

        "diagnostico":
            diagnostico,

        "tempo":
            tempo_total,

        "pasta_saida":
            pasta_saida
    }


# ============================================================
# UPLOAD
# ============================================================

st.subheader(
    "📤 Selecione o PDF"
)


arquivo_upload = st.file_uploader(
    "Envie o PDF para processamento",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo_upload is not None:

    st.success(
        f"Arquivo selecionado: "
        f"**{arquivo_upload.name}**"
    )


    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        # ====================================================
        # CRIA PASTA TEMPORÁRIA
        # ====================================================

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )


        caminho_pdf_original = os.path.join(
            pasta_trabalho,
            arquivo_upload.name
        )


        try:

            # ==================================================
            # SALVA ORIGINAL
            # ==================================================

            with open(
                caminho_pdf_original,
                "wb"
            ) as arquivo:

                arquivo.write(
                    arquivo_upload.getbuffer()
                )


            # ==================================================
            # PROGRESSO
            # ==================================================

            progress_bar = st.progress(
                0
            )


            status = st.empty()


            # ==================================================
            # PROCESSA
            # ==================================================

            resultado = processar_pdf(
                caminho_pdf_original,
                pasta_trabalho,
                progress_bar,
                status
            )


            progress_bar.progress(
                1.0
            )


            status.success(
                "✅ Processamento concluído!"
            )


            # ==================================================
            # RESUMO
            # ==================================================

            st.subheader(
                "📊 Resultado"
            )


            col1, col2, col3, col4 = (
                st.columns(4)
            )


            with col1:

                st.metric(
                    "Total de páginas",
                    resultado[
                        "total_paginas"
                    ]
                )


            with col2:

                st.metric(
                    "Comprovantes",
                    resultado[
                        "total_comprovantes"
                    ]
                )


            with col3:

                st.metric(
                    "Sem comprovantes",
                    resultado[
                        "total_sem_comprovantes"
                    ]
                )


            with col4:

                st.metric(
                    "Tempo",
                    f"{resultado['tempo']:.1f}s"
                )


            # ==================================================
            # TIPOS
            # ==================================================

            st.subheader(
                "📄 Comprovantes identificados"
            )


            col1, col2, col3 = (
                st.columns(3)
            )


            with col1:

                st.metric(
                    "PIX",
                    resultado[
                        "quantidade_pix"
                    ]
                )


            with col2:

                st.metric(
                    "Transferência",
                    resultado[
                        "quantidade_transferencia"
                    ]
                )


            with col3:

                st.metric(
                    "Transação bancária",
                    resultado[
                        "quantidade_transacao"
                    ]
                )


            # ==================================================
            # PDFS DE COMPROVANTES
            # ==================================================

            st.subheader(
                "📘 PDFs de COMPROVANTES"
            )


            arquivos_comprovantes = (
                resultado[
                    "arquivos_comprovantes"
                ]
            )


            if arquivos_comprovantes:

                for arquivo in (
                    arquivos_comprovantes
                ):

                    st.write(
                        f"**{arquivo['nome']}** — "
                        f"{arquivo['quantidade']} "
                        f"comprovante(s) — "
                        f"{formatar_tamanho(arquivo['tamanho'])}"
                    )


                    with open(
                        arquivo["caminho"],
                        "rb"
                    ) as arquivo_pdf:

                        st.download_button(
                            label=(
                                f"⬇️ Baixar "
                                f"{arquivo['nome']}"
                            ),

                            data=arquivo_pdf.read(),

                            file_name=arquivo[
                                "nome"
                            ],

                            mime="application/pdf",

                            key=(
                                "download_comp_"
                                +
                                arquivo["nome"]
                            ),

                            use_container_width=True
                        )


            else:

                st.warning(
                    "Nenhum comprovante foi identificado."
                )


            # ==================================================
            # PDFS SEM COMPROVANTES
            # ==================================================

            st.subheader(
                "📗 PDFs de SEM COMPROVANTES"
            )


            arquivos_sem_comprovantes = (
                resultado[
                    "arquivos_sem_comprovantes"
                ]
            )


            if arquivos_sem_comprovantes:

                for arquivo in (
                    arquivos_sem_comprovantes
                ):

                    st.write(
                        f"**{arquivo['nome']}** — "
                        f"{arquivo['quantidade']} "
                        f"página(s) — "
                        f"{formatar_tamanho(arquivo['tamanho'])}"
                    )


                    with open(
                        arquivo["caminho"],
                        "rb"
                    ) as arquivo_pdf:

                        st.download_button(
                            label=(
                                f"⬇️ Baixar "
                                f"{arquivo['nome']}"
                            ),

                            data=arquivo_pdf.read(),

                            file_name=arquivo[
                                "nome"
                            ],

                            mime="application/pdf",

                            key=(
                                "download_sem_"
                                +
                                arquivo["nome"]
                            ),

                            use_container_width=True
                        )


            else:

                st.info(
                    "Não existem páginas sem comprovantes."
                )


            # ==================================================
            # RESUMO DOS ARQUIVOS
            # ==================================================

            st.subheader(
                "📦 Resumo dos arquivos gerados"
            )


            total_arquivos = (
                len(
                    arquivos_comprovantes
                )
                +
                len(
                    arquivos_sem_comprovantes
                )
            )


            st.write(
                f"**Total de PDFs gerados:** "
                f"{total_arquivos}"
            )


            # ==================================================
            # DETALHAMENTO
            # ==================================================

            with st.expander(
                "🔎 Ver detalhes dos PDFs gerados"
            ):

                st.write(
                    "### COMPROVANTES"
                )


                for arquivo in (
                    arquivos_comprovantes
                ):

                    st.write(
                        f"📄 {arquivo['nome']} | "
                        f"{arquivo['quantidade']} "
                        f"comprovante(s) | "
                        f"{formatar_tamanho(arquivo['tamanho'])}"
                    )


                st.write(
                    "### SEM COMPROVANTES"
                )


                for arquivo in (
                    arquivos_sem_comprovantes
                ):

                    st.write(
                        f"📄 {arquivo['nome']} | "
                        f"{arquivo['quantidade']} "
                        f"página(s) | "
                        f"{formatar_tamanho(arquivo['tamanho'])}"
                    )


        except Exception as erro:

            st.error(
                "❌ Ocorreu um erro durante o processamento."
            )

            st.exception(
                erro
            )


        finally:

            gc.collect()
