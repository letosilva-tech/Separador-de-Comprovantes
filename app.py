import streamlit as st
import os
import re
import unicodedata
import tempfile
import shutil
import zipfile
import gc
import time

from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# CONSTANTES
# ============================================================

LIMITE_ZIP = 10 * 1024 * 1024
LIMITE_SEGURANCA = 9_500_000


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """Remove acentos, padroniza maiúsculas e espaços."""

    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)

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


def identificar_comprovante(texto):
    """Identifica o tipo de comprovante pelo texto extraído."""

    texto = normalizar_texto(texto)

    if not texto:
        return None

    # ========================================================
    # 1 - COMPROVANTE PIX
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+(?:DE\s+)?PIX\b",
        texto
    ):
        return "PIX"

    # ========================================================
    # 2 - COMPROVANTE DE TRANSFERÊNCIA
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+(?:DE\s+)?TRANSFERENCIA\b",
        texto
    ):
        return "TRANSFERENCIA"

    # ========================================================
    # 3 - COMPROVANTE DE TRANSAÇÃO BANCÁRIA
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+(?:DE\s+)?TRANSACAO\s+BANCARIA\b",
        texto
    ):
        return "TRANSACAO_BANCARIA"

    return None


def formatar_tamanho(tamanho):

    if tamanho < 1024:
        return f"{tamanho} B"

    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.2f} KB"

    return f"{tamanho / (1024 * 1024):.2f} MB"


def nome_seguro(nome):
    """Remove caracteres problemáticos de nomes de arquivos."""

    nome = unicodedata.normalize(
        "NFKD",
        nome
    )

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nome
    )

    return nome.strip("._") or "arquivo"


def criar_pdf_pagina(
    reader,
    numero_pagina,
    caminho_saida
):
    """Cria um PDF contendo somente uma página."""

    writer = PdfWriter()

    writer.add_page(
        reader.pages[numero_pagina]
    )

    with open(
        caminho_saida,
        "wb"
    ) as arquivo:

        writer.write(
            arquivo
        )

    del writer

    gc.collect()


# ============================================================
# CLASSE PARA CONTROLAR ZIP
# ============================================================

class GerenciadorZIP:

    def __init__(
        self,
        pasta_saida,
        prefixo
    ):

        self.pasta_saida = pasta_saida

        self.prefixo = prefixo

        self.numero = 1

        self.zip_file = None

        self.caminho_zip = None

        self.arquivos = []

        self.tamanho_atual = 0

        self.quantidade_arquivos = 0

        self._abrir_novo_zip()


    # ========================================================
    # ABRE NOVO ZIP
    # ========================================================

    def _abrir_novo_zip(self):

        nome = (
            f"{self.prefixo}_"
            f"{self.numero:03d}.zip"
        )

        self.caminho_zip = os.path.join(
            self.pasta_saida,
            nome
        )

        self.zip_file = zipfile.ZipFile(
            self.caminho_zip,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        )

        self.tamanho_atual = 0

        self.quantidade_arquivos = 0


    # ========================================================
    # FECHA ZIP ATUAL
    # ========================================================

    def _fechar_zip(self):

        if self.zip_file is not None:

            self.zip_file.close()

            self.zip_file = None

        if (
            self.caminho_zip
            and os.path.exists(
                self.caminho_zip
            )
        ):

            tamanho = os.path.getsize(
                self.caminho_zip
            )

            if self.quantidade_arquivos > 0:

                self.arquivos.append(
                    {
                        "nome":
                            os.path.basename(
                                self.caminho_zip
                            ),

                        "caminho":
                            self.caminho_zip,

                        "tamanho":
                            tamanho,

                        "quantidade":
                            self.quantidade_arquivos,
                    }
                )

            else:

                try:

                    os.remove(
                        self.caminho_zip
                    )

                except OSError:

                    pass


    # ========================================================
    # ADICIONA PDF AO ZIP
    # ========================================================

    def adicionar(
        self,
        caminho_pdf,
        nome_pdf,
        tamanho_pdf
    ):

        if os.path.exists(
            self.caminho_zip
        ):

            tamanho_atual_disco = os.path.getsize(
                self.caminho_zip
            )

        else:

            tamanho_atual_disco = 0


        precisa_novo_zip = (

            self.quantidade_arquivos > 0

            and

            tamanho_atual_disco
            +
            tamanho_pdf
            +
            4096
            >
            LIMITE_SEGURANCA
        )


        if precisa_novo_zip:

            self._fechar_zip()

            self.numero += 1

            self._abrir_novo_zip()


        self.zip_file.write(
            caminho_pdf,
            arcname=nome_pdf
        )

        self.quantidade_arquivos += 1


        self.zip_file.fp.flush()

        self.tamanho_atual = os.path.getsize(
            self.caminho_zip
        )


    # ========================================================
    # FINALIZA
    # ========================================================

    def finalizar(self):

        self._fechar_zip()

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
    # LEITOR
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
    # PASTAS
    # ========================================================

    pasta_saida = os.path.join(
        pasta_trabalho,
        "saida"
    )

    pasta_temp = os.path.join(
        pasta_trabalho,
        "temp"
    )

    os.makedirs(
        pasta_saida,
        exist_ok=True
    )

    os.makedirs(
        pasta_temp,
        exist_ok=True
    )


    # ========================================================
    # GERENCIADORES
    # ========================================================

    zip_comprovantes = GerenciadorZIP(
        pasta_saida,
        "COMPROVANTES"
    )

    zip_sem_comprovantes = GerenciadorZIP(
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
    # ANALISA PÁGINA POR PÁGINA
    # ========================================================

    for indice in range(
        total_paginas
    ):

        numero_pagina = indice + 1


        status.info(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )


        progress_bar.progress(
            numero_pagina / total_paginas
        )


        pagina = reader.pages[
            indice
        ]


        # ----------------------------------------------------
        # EXTRAÇÃO DO TEXTO
        # ----------------------------------------------------

        try:

            texto = pagina.extract_text() or ""

        except Exception as erro:

            texto = ""

            diagnostico.append(
                f"Página {numero_pagina}: "
                f"erro ao extrair texto: {erro}"
            )


        tipo = identificar_comprovante(
            texto
        )


        # ====================================================
        # COMPROVANTE IDENTIFICADO
        # ====================================================

        if tipo:

            total_comprovantes += 1


            if tipo == "PIX":

                quantidade_pix += 1

                prefixo_nome = "PIX"


            elif tipo == "TRANSFERENCIA":

                quantidade_transferencia += 1

                prefixo_nome = "TRANSFERENCIA"


            else:

                quantidade_transacao += 1

                prefixo_nome = "TRANSACAO_BANCARIA"


            nome_pdf = (
                f"{prefixo_nome}_"
                f"PAGINA_{numero_pagina:04d}.pdf"
            )


            caminho_pdf = os.path.join(
                pasta_temp,
                nome_pdf
            )


            criar_pdf_pagina(
                reader,
                indice,
                caminho_pdf
            )


            tamanho_pdf = os.path.getsize(
                caminho_pdf
            )


            zip_comprovantes.adicionar(
                caminho_pdf,
                nome_pdf,
                tamanho_pdf
            )


        # ====================================================
        # NÃO É COMPROVANTE
        # ====================================================

        else:

            total_sem_comprovantes += 1


            nome_pdf = (
                "SEM_COMPROVANTE_"
                f"PAGINA_{numero_pagina:04d}.pdf"
            )


            caminho_pdf = os.path.join(
                pasta_temp,
                nome_pdf
            )


            criar_pdf_pagina(
                reader,
                indice,
                caminho_pdf
            )


            tamanho_pdf = os.path.getsize(
                caminho_pdf
            )


            zip_sem_comprovantes.adicionar(
                caminho_pdf,
                nome_pdf,
                tamanho_pdf
            )


        gc.collect()


    # ========================================================
    # FINALIZA ZIPs
    # ========================================================

    arquivos_comprovantes = (
        zip_comprovantes.finalizar()
    )

    arquivos_sem_comprovantes = (
        zip_sem_comprovantes.finalizar()
    )


    tempo_total = (
        time.time() - inicio
    )


    return {
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

        "arquivos_comprovantes":
            arquivos_comprovantes,

        "arquivos_sem_comprovantes":
            arquivos_sem_comprovantes,

        "diagnostico":
            diagnostico,

        "tempo_total":
            tempo_total,
    }


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)


st.write(
    """
    O sistema analisa o PDF página por página e identifica somente
    páginas que contenham os seguintes comprovantes:

    🔵 **COMPROVANTE PIX**

    🟢 **COMPROVANTE DE TRANSFERENCIA**

    🟣 **COMPROVANTE DE TRANSACAO BANCARIA**

    Cada comprovante identificado é extraído como uma página
    independente.

    Depois os PDFs são agrupados em arquivos ZIP de até
    aproximadamente **10 MB**.
    """
)


st.info(
    """
    💡 Para reduzir o consumo de memória, o sistema trabalha com
    arquivos temporários no disco e não mantém todos os PDFs
    simultaneamente na memória.
    """
)


# ============================================================
# UPLOAD
# ============================================================

arquivo_enviado = st.file_uploader(
    "Selecione o PDF que deseja processar",
    type=["pdf"]
)


if arquivo_enviado is not None:

    st.success(
        f"Arquivo selecionado: **{arquivo_enviado.name}** "
        f"({formatar_tamanho(arquivo_enviado.size)})"
    )


    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )


        caminho_pdf_original = os.path.join(
            pasta_trabalho,
            nome_seguro(
                arquivo_enviado.name
            )
        )


        try:

            # ------------------------------------------------
            # SALVA PDF ORIGINAL
            # ------------------------------------------------

            with open(
                caminho_pdf_original,
                "wb"
            ) as arquivo:

                arquivo.write(
                    arquivo_enviado.getbuffer()
                )


            progress_bar = st.progress(
                0
            )

            status = st.empty()


            # ------------------------------------------------
            # PROCESSA
            # ------------------------------------------------

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


            # =================================================
            # RESULTADO
            # =================================================

            st.divider()

            st.subheader(
                "📊 Resultado"
            )


            col1, col2, col3, col4 = st.columns(
                4
            )


            col1.metric(
                "Total de páginas",
                resultado["total_paginas"]
            )


            col2.metric(
                "Comprovantes",
                resultado["total_comprovantes"]
            )


            col3.metric(
                "Sem comprovante",
                resultado["total_sem_comprovantes"]
            )


            col4.metric(
                "Tempo",
                f"{resultado['tempo_total']:.1f}s"
            )


            # =================================================
            # TIPOS
            # =================================================

            st.subheader(
                "🔎 Tipos identificados"
            )


            c1, c2, c3 = st.columns(
                3
            )


            c1.metric(
                "🔵 PIX",
                resultado["quantidade_pix"]
            )


            c2.metric(
                "🟢 Transferência",
                resultado[
                    "quantidade_transferencia"
                ]
            )


            c3.metric(
                "🟣 Transação bancária",
                resultado[
                    "quantidade_transacao"
                ]
            )


            # =================================================
            # DOWNLOADS
            # =================================================

            def mostrar_downloads(
                titulo,
                arquivos
            ):

                if not arquivos:
                    return


                st.subheader(
                    titulo
                )


                for item in arquivos:

                    tamanho_real = os.path.getsize(
                        item["caminho"]
                    )


                    st.write(
                        f"**{item['nome']}** — "
                        f"{item['quantidade']} arquivo(s) — "
                        f"{formatar_tamanho(tamanho_real)}"
                    )


                    with open(
                        item["caminho"],
                        "rb"
                    ) as arquivo:

                        st.download_button(
                            label=(
                                f"⬇️ Baixar "
                                f"{item['nome']}"
                            ),

                            data=arquivo.read(),

                            file_name=item["nome"],

                            mime="application/zip",

                            use_container_width=True
                        )


                    if tamanho_real > LIMITE_ZIP:

                        st.warning(
                            f"⚠️ {item['nome']} ficou com "
                            f"{formatar_tamanho(tamanho_real)}, "
                            "acima de 10 MB. Isso pode acontecer "
                            "quando um único PDF de uma página já "
                            "é muito grande."
                        )


            mostrar_downloads(
                "📦 ZIPs com comprovantes",
                resultado[
                    "arquivos_comprovantes"
                ]
            )


            mostrar_downloads(
                "📦 ZIPs sem comprovantes",
                resultado[
                    "arquivos_sem_comprovantes"
                ]
            )


            # =================================================
            # DIAGNÓSTICO
            # =================================================

            if resultado["diagnostico"]:

                with st.expander(
                    "⚠️ Diagnóstico"
                ):

                    for mensagem in resultado[
                        "diagnostico"
                    ]:

                        st.write(
                            mensagem
                        )


            # =================================================
            # NENHUM COMPROVANTE
            # =================================================

            if resultado[
                "total_comprovantes"
            ] == 0:

                st.warning(
                    "Nenhum comprovante foi identificado. "
                    "Verifique se o PDF possui texto selecionável "
                    "ou se os termos usados no comprovante são "
                    "diferentes dos padrões configurados."
                )


        except Exception as erro:

            st.error(
                "❌ Ocorreu um erro durante o processamento."
            )

            st.exception(
                erro
            )


        finally:

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except Exception:

                pass
