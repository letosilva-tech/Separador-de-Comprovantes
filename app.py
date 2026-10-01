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
    layout="wide"
)


# ============================================================
# CONSTANTES
# ============================================================

# Limite real desejado:
LIMITE_ZIP = 10 * 1024 * 1024

# Margem de segurança para cabeçalho/estrutura do ZIP.
# O resultado ficará normalmente abaixo de 10 MB.
LIMITE_SEGURANCA = 9_500_000


# ============================================================
# INTERFACE
# ============================================================

st.title("📄 Separador de Comprovantes")

st.write(
    """
    O sistema analisa o PDF página por página e identifica somente
    páginas que contenham os seguintes comprovantes:

    🔵 **COMPROVANTE PIX**

    🟢 **COMPROVANTE DE TRANSFERENCIA**

    🟣 **COMPROVANTE DE TRANSACAO BANCARIA**

    Cada comprovante identificado é extraído como uma página
    independente.

    Depois os PDFs são agrupados em arquivos ZIP de até aproximadamente
    **10 MB**.
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
    # NÃO É UM DOS COMPROVANTES SOLICITADOS
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
# CRIA PDF DE UMA ÚNICA PÁGINA
# ============================================================

def criar_pdf_pagina(
    reader,
    numero_pagina,
    caminho_saida
):

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

                self.arquivos.append({

                    "nome":
                        os.path.basename(
                            self.caminho_zip
                        ),

                    "caminho":
                        self.caminho_zip,

                    "tamanho":
                        tamanho,

                    "quantidade":
                        self.quantidade_arquivos
                })

            else:

                try:

                    os.remove(
                        self.caminho_zip
                    )

                except Exception:

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

        # ----------------------------------------------------
        # Tamanho atual do ZIP no disco
        # ----------------------------------------------------

        if os.path.exists(
            self.caminho_zip
        ):

            tamanho_atual_disco = os.path.getsize(
                self.caminho_zip
            )

        else:

            tamanho_atual_disco = 0

        # ----------------------------------------------------
        # Verifica se cabe
        # ----------------------------------------------------

        precisa_novo_zip = (

            self.quantidade_arquivos > 0
            and
            (
                tamanho_atual_disco
                +
                tamanho_pdf
                +
                4096
            )
            >
            LIMITE_SEGURANCA
        )

        # ----------------------------------------------------
        # Se não couber, fecha e abre outro
        # ----------------------------------------------------

        if precisa_novo_zip:

            self._fechar_zip()

            self.numero += 1

            self._abrir_novo_zip()

        # ----------------------------------------------------
        # Adiciona arquivo
        # ----------------------------------------------------

        self.zip_file.write(
            caminho_pdf,
            arcname=nome_pdf
        )

        self.quantidade_arquivos += 1

        # ----------------------------------------------------
        # Atualiza tamanho
        # ----------------------------------------------------

        self.zip_file.fp.flush()

        self.tamanho_atual = os.path.getsize(
            self.caminho_zip
        )

        # ----------------------------------------------------
        # Caso um único PDF seja maior que o limite
        # ----------------------------------------------------

        if (
            self.tamanho_atual
            >
            LIMITE_ZIP
        ):

            # Não é possível dividir um único PDF
            # de uma página sem alterar seu conteúdo.
            pass


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

    paginas_pix = []

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

        pagina = reader.pages[
            indice
        ]

        # ----------------------------------------------------
        # EXTRAÇÃO DO TEXTO
        # ----------------------------------------------------

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except Exception:

            texto = ""

        texto_normalizado = normalizar_texto(
            texto
        )

        # ----------------------------------------------------
        # IDENTIFICA
        # ----------------------------------------------------

        tipo = identificar_comprovante(
            texto
        )

        # ====================================================
        # COMPROVANTE
        # ====================================================

        if tipo:

            total_comprovantes += 1

            # ------------------------------------------------
            # CONTADORES
            # ------------------------------------------------

            if tipo == "PIX":

                quantidade_pix += 1

                paginas_pix.append(
                    numero_pagina
                )

                prefixo = "PIX"

            elif tipo == "TRANSFERENCIA":

                quantidade_transferencia += 1

                prefixo = "TRANSFERENCIA"

            elif tipo == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1

                prefixo = "TRANSACAO_BANCARIA"

            else:

                prefixo = tipo

            # ------------------------------------------------
            # CRIA PDF TEMPORÁRIO
            # ------------------------------------------------

            nome_temp = (
                f"comp_{numero_pagina:06d}.pdf"
            )

            caminho_temp = os.path.join(
                pasta_temp,
                nome_temp
            )

            criar_pdf_pagina(
                reader,
                indice,
                caminho_temp
            )

            tamanho_pdf = os.path.getsize(
                caminho_temp
            )

            # ------------------------------------------------
            # NOME DENTRO DO ZIP
            # ------------------------------------------------

            nome_pdf = (
                f"comprovante_"
                f"{prefixo}_"
                f"{total_comprovantes:06d}.pdf"
            )

            # ------------------------------------------------
            # ADICIONA AO ZIP
            # ------------------------------------------------

            zip_comprovantes.adicionar(
                caminho_temp,
                nome_pdf,
                tamanho_pdf
            )

            # ------------------------------------------------
            # REMOVE TEMPORÁRIO
            # ------------------------------------------------

            try:

                os.remove(
                    caminho_temp
                )

            except Exception:

                pass

        # ====================================================
        # SEM COMPROVANTE
        # ====================================================

        else:

            total_sem_comprovantes += 1

            nome_temp = (
                f"sem_{numero_pagina:06d}.pdf"
            )

            caminho_temp = os.path.join(
                pasta_temp,
                nome_temp
            )

            criar_pdf_pagina(
                reader,
                indice,
                caminho_temp
            )

            tamanho_pdf = os.path.getsize(
                caminho_temp
            )

            nome_pdf = (
                f"pagina_"
                f"{numero_pagina:06d}.pdf"
            )

            zip_sem_comprovantes.adicionar(
                caminho_temp,
                nome_pdf,
                tamanho_pdf
            )

            try:

                os.remove(
                    caminho_temp
                )

            except Exception:

                pass

        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        diagnostico.append({

            "Página":
                numero_pagina,

            "Tipo":
                tipo
                if tipo
                else "SEM COMPROVANTE",

            "PIX":
                "SIM"
                if "PIX" in texto_normalizado
                else "NÃO"
        })

        # ====================================================
        # PROGRESSO
        # ====================================================

        progresso = int(
            (
                numero_pagina
                /
                max(
                    total_paginas,
                    1
                )
            )
            *
            100
        )

        progress_bar.progress(
            progresso
        )

        # ====================================================
        # LIMPEZA DE MEMÓRIA
        # ====================================================

        if numero_pagina % 20 == 0:

            gc.collect()

    # ========================================================
    # FINALIZA ZIPS
    # ========================================================

    status.info(
        "📦 Finalizando arquivos ZIP..."
    )

    arquivos_comprovantes = (
        zip_comprovantes.finalizar()
    )

    arquivos_sem_comprovantes = (
        zip_sem_comprovantes.finalizar()
    )

    # ========================================================
    # LIMPA TEMP
    # ========================================================

    try:

        for arquivo_temp in os.listdir(
            pasta_temp
        ):

            caminho = os.path.join(
                pasta_temp,
                arquivo_temp
            )

            try:

                os.remove(
                    caminho
                )

            except Exception:

                pass

    except Exception:

        pass

    # ========================================================
    # LIBERA READER
    # ========================================================

    del reader

    gc.collect()

    tempo = (
        time.time()
        -
        inicio
    )

    return {

        "total_paginas":
            total_paginas,

        "total_comprovantes":
            total_comprovantes,

        "total_sem_comprovantes":
            total_sem_comprovantes,

        "pix":
            quantidade_pix,

        "transferencias":
            quantidade_transferencia,

        "transacoes":
            quantidade_transacao,

        "arquivos_comprovantes":
            arquivos_comprovantes,

        "arquivos_sem_comprovantes":
            arquivos_sem_comprovantes,

        "diagnostico":
            diagnostico,

        "tempo":
            tempo
    }


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📎 Selecione o arquivo PDF",
    type=["pdf"]
)


# ============================================================
# PROCESSAMENTO
# ============================================================

if arquivo is not None:

    tamanho_upload = len(
        arquivo.getbuffer()
    )

    st.success(
        f"✅ Arquivo selecionado: "
        f"**{arquivo.name}**"
    )

    st.write(
        f"📦 Tamanho do arquivo: "
        f"**{formatar_tamanho(tamanho_upload)}**"
    )

    if st.button(
        "🚀 PROCESSAR PDF",
        type="primary",
        use_container_width=True
    ):

        progress_bar = st.progress(
            0
        )

        status = st.empty()

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_"
        )

        caminho_pdf = os.path.join(
            pasta_trabalho,
            "arquivo_original.pdf"
        )

        try:

            # =================================================
            # SALVA ORIGINAL
            # =================================================

            status.info(
                "💾 Salvando arquivo..."
            )

            with open(
                caminho_pdf,
                "wb"
            ) as arquivo_saida:

                arquivo.seek(0)

                shutil.copyfileobj(
                    arquivo,
                    arquivo_saida,
                    length=1024 * 1024
                )

            # =================================================
            # PROCESSA
            # =================================================

            resultado = processar_pdf(
                caminho_pdf,
                pasta_trabalho,
                progress_bar,
                status
            )

            # =================================================
            # GUARDA RESULTADO
            # =================================================

            st.session_state[
                "resultado"
            ] = resultado

            st.session_state[
                "pasta_trabalho"
            ] = pasta_trabalho

            status.success(
                "✅ Processamento concluído!"
            )

        except Exception as erro:

            status.error(
                "❌ Ocorreu um erro durante o processamento."
            )

            st.exception(
                erro
            )

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except Exception:

                pass


# ============================================================
# RESULTADO
# ============================================================

if "resultado" in st.session_state:

    resultado = st.session_state[
        "resultado"
    ]

    st.divider()

    st.header(
        "📊 Resultado"
    )

    # ========================================================
    # INDICADORES
    # ========================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Páginas",
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
            "Sem comprovante",
            resultado[
                "total_sem_comprovantes"
            ]
        )

    with col4:

        st.metric(
            "Tempo",
            f"{resultado['tempo']:.1f}s"
        )

    # ========================================================
    # TIPOS
    # ========================================================

    st.subheader(
        "🔎 Comprovantes encontrados"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "🔵 PIX",
            resultado[
                "pix"
            ]
        )

    with c2:

        st.metric(
            "🟢 Transferências",
            resultado[
                "transferencias"
            ]
        )

    with c3:

        st.metric(
            "🟣 Transações bancárias",
            resultado[
                "transacoes"
            ]
        )

    # ========================================================
    # MENSAGEM
    # ========================================================

    if resultado[
        "total_comprovantes"
    ] > 0:

        st.success(
            f"✅ Foram encontrados "
            f"**{resultado['total_comprovantes']} "
            f"comprovante(s)**."
        )

    else:

        st.warning(
            "⚠️ Nenhum comprovante foi encontrado."
        )

    # ========================================================
    # DOWNLOAD COMPROVANTES
    # ========================================================

    st.divider()

    st.header(
        "📦 ZIPs dos comprovantes"
    )

    arquivos = resultado[
        "arquivos_comprovantes"
    ]

    if arquivos:

        for item in arquivos:

            tamanho = item[
                "tamanho"
            ]

            st.write(
                f"📦 **{item['nome']}**"
            )

            st.caption(
                f"{formatar_tamanho(tamanho)} "
                f"• "
                f"{item['quantidade']} comprovante(s)"
            )

            with open(
                item["caminho"],
                "rb"
            ) as arquivo_zip:

                dados = arquivo_zip.read()

            st.download_button(
                label=(
                    f"⬇️ Baixar "
                    f"{item['nome']} "
                    f"({formatar_tamanho(tamanho)})"
                ),

                data=dados,

                file_name=item[
                    "nome"
                ],

                mime="application/zip",

                key=(
                    "download_comp_"
                    +
                    item["nome"]
                ),

                use_container_width=True
            )

            # Verificação visual
            if tamanho <= LIMITE_ZIP:

                st.success(
                    f"✅ Dentro do limite de 10 MB "
                    f"({formatar_tamanho(tamanho)})"
                )

            else:

                st.warning(
                    f"⚠️ Este ZIP ultrapassou 10 MB: "
                    f"{formatar_tamanho(tamanho)}"
                )

    else:

        st.warning(
            "Nenhum ZIP de comprovantes foi gerado."
        )

    # ========================================================
    # DOWNLOAD SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.header(
        "📁 ZIPs sem comprovantes"
    )

    arquivos = resultado[
        "arquivos_sem_comprovantes"
    ]

    if arquivos:

        for item in arquivos:

            tamanho = item[
                "tamanho"
            ]

            st.write(
                f"📦 **{item['nome']}**"
            )

            st.caption(
                f"{formatar_tamanho(tamanho)} "
                f"• "
                f"{item['quantidade']} página(s)"
            )

            with open(
                item["caminho"],
                "rb"
            ) as arquivo_zip:

                dados = arquivo_zip.read()

            st.download_button(
                label=(
                    f"⬇️ Baixar "
                    f"{item['nome']} "
                    f"({formatar_tamanho(tamanho)})"
                ),

                data=dados,

                file_name=item[
                    "nome"
                ],

                mime="application/zip",

                key=(
                    "download_sem_"
                    +
                    item["nome"]
                ),

                use_container_width=True
            )

            if tamanho <= LIMITE_ZIP:

                st.success(
                    f"✅ Dentro do limite de 10 MB "
                    f"({formatar_tamanho(tamanho)})"
                )

            else:

                st.warning(
                    f"⚠️ Este ZIP ultrapassou 10 MB: "
                    f"{formatar_tamanho(tamanho)}"
                )

    else:

        st.success(
            "✅ Não existem páginas sem comprovantes."
        )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    st.divider()

    with st.expander(
        "🔍 Diagnóstico das páginas"
    ):

        st.dataframe(
            resultado[
                "diagnostico"
            ],
            use_container_width=True,
            hide_index=True
        )
```
