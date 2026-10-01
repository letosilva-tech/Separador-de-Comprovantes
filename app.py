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

# Limite máximo REAL do ZIP
LIMITE_ZIP = 10 * 1024 * 1024


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

    Cada página é transformada em um PDF independente.

    Depois os PDFs são agrupados em arquivos ZIP de até **10 MB**.
    """
)

st.info(
    """
    💡 O sistema trabalha com arquivos temporários no disco para
    reduzir o consumo de memória.
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
        return f"{tamanho / 1024:.2f} KB"

    return f"{tamanho / (1024 * 1024):.2f} MB"


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

        self.caminho_zip = None

        self.arquivos = []

        self.quantidade_arquivos = 0

        self.nomes_arquivos = []

        self._abrir_novo_zip()


    # ========================================================
    # NOME DO ZIP
    # ========================================================

    def _gerar_nome_zip(self):

        return (
            f"{self.prefixo}_"
            f"{self.numero:03d}.zip"
        )


    # ========================================================
    # ABRE NOVO ZIP
    # ========================================================

    def _abrir_novo_zip(self):

        nome = self._gerar_nome_zip()

        self.caminho_zip = os.path.join(
            self.pasta_saida,
            nome
        )

        # Cria ZIP vazio.
        # O arquivo só será considerado no resultado
        # quando possuir pelo menos um PDF.

        with zipfile.ZipFile(
            self.caminho_zip,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        ):
            pass

        self.quantidade_arquivos = 0

        self.nomes_arquivos = []


    # ========================================================
    # FECHA/REGISTRA ZIP
    # ========================================================

    def _registrar_zip_atual(self):

        if not self.caminho_zip:
            return

        if not os.path.exists(
            self.caminho_zip
        ):
            return

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
                        self.quantidade_arquivos
                }
            )

        else:

            try:
                os.remove(
                    self.caminho_zip
                )
            except Exception:
                pass


    # ========================================================
    # CRIA ZIP CANDIDATO
    #
    # Essa é a parte importante.
    #
    # Em vez de tentar adivinhar o tamanho comprimido,
    # criamos um ZIP temporário com os arquivos que já
    # existem + o novo arquivo.
    #
    # Assim sabemos o tamanho REAL que o ZIP terá.
    # ========================================================

    def _criar_zip_candidato(
        self,
        caminho_pdf,
        nome_pdf
    ):

        caminho_candidato = os.path.join(
            self.pasta_saida,
            (
                f".candidato_"
                f"{self.prefixo}_"
                f"{self.numero:03d}_"
                f"{int(time.time() * 1000000)}.zip"
            )
        )

        try:

            with zipfile.ZipFile(
                caminho_candidato,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=1
            ) as zip_candidato:

                # ------------------------------------------------
                # Copia os arquivos que já estão no ZIP atual
                # ------------------------------------------------

                if (
                    self.quantidade_arquivos > 0
                    and
                    os.path.exists(
                        self.caminho_zip
                    )
                ):

                    with zipfile.ZipFile(
                        self.caminho_zip,
                        mode="r"
                    ) as zip_atual:

                        for nome in zip_atual.namelist():

                            dados = zip_atual.read(
                                nome
                            )

                            zip_candidato.writestr(
                                nome,
                                dados
                            )


                # ------------------------------------------------
                # Adiciona o novo PDF
                # ------------------------------------------------

                zip_candidato.write(
                    caminho_pdf,
                    arcname=nome_pdf
                )


            return caminho_candidato

        except Exception:

            if os.path.exists(
                caminho_candidato
            ):

                try:
                    os.remove(
                        caminho_candidato
                    )
                except Exception:
                    pass

            raise


    # ========================================================
    # ADICIONA PDF
    # ========================================================

    def adicionar(
        self,
        caminho_pdf,
        nome_pdf,
        tamanho_pdf
    ):

        # --------------------------------------------------------
        # Caso o PDF sozinho já seja maior que 10 MB
        # --------------------------------------------------------

        if (
            self.quantidade_arquivos == 0
            and
            tamanho_pdf > LIMITE_ZIP
        ):

            with zipfile.ZipFile(
                self.caminho_zip,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=1
            ) as zip_atual:

                zip_atual.write(
                    caminho_pdf,
                    arcname=nome_pdf
                )

            self.quantidade_arquivos = 1

            self.nomes_arquivos = [
                nome_pdf
            ]

            return


        # --------------------------------------------------------
        # Se já existem arquivos no ZIP:
        #
        # cria um ZIP candidato com:
        #
        # arquivos atuais + novo arquivo
        #
        # e mede o tamanho REAL.
        # --------------------------------------------------------

        if self.quantidade_arquivos > 0:

            caminho_candidato = (
                self._criar_zip_candidato(
                    caminho_pdf,
                    nome_pdf
                )
            )

            tamanho_candidato = (
                os.path.getsize(
                    caminho_candidato
                )
            )

            # ----------------------------------------------------
            # Cabe no ZIP atual
            # ----------------------------------------------------

            if tamanho_candidato <= LIMITE_ZIP:

                os.replace(
                    caminho_candidato,
                    self.caminho_zip
                )

                self.quantidade_arquivos += 1

                self.nomes_arquivos.append(
                    nome_pdf
                )

                return


            # ----------------------------------------------------
            # NÃO cabe.
            #
            # Remove o candidato e abre outro ZIP.
            # ----------------------------------------------------

            try:
                os.remove(
                    caminho_candidato
                )
            except Exception:
                pass

            self._registrar_zip_atual()

            self.numero += 1

            self._abrir_novo_zip()


        # --------------------------------------------------------
        # Novo ZIP.
        #
        # Aqui o PDF é colocado diretamente.
        # --------------------------------------------------------

        with zipfile.ZipFile(
            self.caminho_zip,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        ) as zip_novo:

            zip_novo.write(
                caminho_pdf,
                arcname=nome_pdf
            )


        self.quantidade_arquivos = 1

        self.nomes_arquivos = [
            nome_pdf
        ]


    # ========================================================
    # FINALIZA
    # ========================================================

    def finalizar(self):

        self._registrar_zip_atual()

        return self.arquivos


# ============================================================
# PROCESSAMENTO DO PDF
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

        pagina = reader.pages[
            indice
        ]


        # ====================================================
        # EXTRAÇÃO DO TEXTO
        # ====================================================

        try:

            texto = pagina.extract_text()

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
        # IDENTIFICA COMPROVANTE
        # ====================================================

        tipo_comprovante = (
            identificar_comprovante(
                texto
            )
        )


        # ====================================================
        # NOME DO PDF
        # ====================================================

        if tipo_comprovante:

            total_comprovantes += 1

            if tipo_comprovante == "PIX":

                quantidade_pix += 1

            elif tipo_comprovante == "TRANSFERENCIA":

                quantidade_transferencia += 1

            elif tipo_comprovante == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1


            nome_pdf = (
                f"COMPROVANTE_"
                f"{total_comprovantes:06d}_"
                f"{tipo_comprovante}_"
                f"PAGINA_{numero_pagina:06d}.pdf"
            )

            pasta_tipo = os.path.join(
                pasta_temp,
                "comprovantes"
            )

        else:

            total_sem_comprovantes += 1

            nome_pdf = (
                f"SEM_COMPROVANTE_"
                f"{total_sem_comprovantes:06d}_"
                f"PAGINA_{numero_pagina:06d}.pdf"
            )

            pasta_tipo = os.path.join(
                pasta_temp,
                "sem_comprovantes"
            )


        os.makedirs(
            pasta_tipo,
            exist_ok=True
        )


        caminho_pdf = os.path.join(
            pasta_tipo,
            nome_pdf
        )


        # ====================================================
        # CRIA PDF DA PÁGINA
        # ====================================================

        criar_pdf_pagina(
            reader,
            indice,
            caminho_pdf
        )


        # ====================================================
        # TAMANHO REAL DO PDF
        # ====================================================

        tamanho_pdf = os.path.getsize(
            caminho_pdf
        )


        # ====================================================
        # ADICIONA AO ZIP CORRETO
        # ====================================================

        if tipo_comprovante:

            zip_comprovantes.adicionar(
                caminho_pdf,
                nome_pdf,
                tamanho_pdf
            )

        else:

            zip_sem_comprovantes.adicionar(
                caminho_pdf,
                nome_pdf,
                tamanho_pdf
            )


        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        diagnostico.append(
            {
                "pagina":
                    numero_pagina,

                "tipo":
                    tipo_comprovante
                    if tipo_comprovante
                    else "SEM_COMPROVANTE",

                "tamanho_pdf":
                    tamanho_pdf,

                "tamanho_formatado":
                    formatar_tamanho(
                        tamanho_pdf
                    )
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


        # ====================================================
        # LIBERA MEMÓRIA
        # ====================================================

        del pagina

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


    # ========================================================
    # LIMPA REFERÊNCIAS
    # ========================================================

    del reader

    gc.collect()


    # ========================================================
    # RESULTADO
    # ========================================================

    tempo_total = (
        time.time()
        -
        inicio
    )


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
# FUNÇÃO PARA CRIAR ZIP FINAL COM TODOS OS ZIPs
# ============================================================

def criar_zip_final(
    arquivos,
    caminho_saida
):

    with zipfile.ZipFile(
        caminho_saida,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1
    ) as zip_final:

        for arquivo in arquivos:

            if os.path.exists(
                arquivo["caminho"]
            ):

                zip_final.write(
                    arquivo["caminho"],
                    arcname=arquivo["nome"]
                )


# ============================================================
# INTERFACE DE UPLOAD
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
        # ÁREA TEMPORÁRIA
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
            # SALVA PDF ORIGINAL
            # ==================================================

            with open(
                caminho_pdf_original,
                "wb"
            ) as arquivo:

                arquivo.write(
                    arquivo_upload.getbuffer()
                )


            # ==================================================
            # COMPONENTES DE PROGRESSO
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
            # TIPOS DE COMPROVANTE
            # ==================================================

            st.subheader(
                "📄 Tipos identificados"
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
            # ZIPs DE COMPROVANTES
            # ==================================================

            st.subheader(
                "📦 ZIPs de comprovantes"
            )


            arquivos_comprovantes = (
                resultado[
                    "arquivos_comprovantes"
                ]
            )


            if arquivos_comprovantes:

                for arquivo in arquivos_comprovantes:

                    tamanho = (
                        arquivo["tamanho"]
                    )

                    st.write(
                        f"**{arquivo['nome']}**  \n"
                        f"📄 {arquivo['quantidade']} arquivos  \n"
                        f"💾 {formatar_tamanho(tamanho)}"
                    )


                    with open(
                        arquivo["caminho"],
                        "rb"
                    ) as arquivo_zip:

                        st.download_button(
                            label=(
                                f"⬇️ Baixar "
                                f"{arquivo['nome']}"
                            ),

                            data=arquivo_zip.read(),

                            file_name=arquivo[
                                "nome"
                            ],

                            mime="application/zip",

                            key=(
                                "download_comprovantes_"
                                + arquivo["nome"]
                            ),

                            use_container_width=True
                        )

            else:

                st.warning(
                    "Nenhum comprovante foi identificado."
                )


            # ==================================================
            # ZIPs SEM COMPROVANTES
            # ==================================================

            st.subheader(
                "📦 ZIPs sem comprovantes"
            )


            arquivos_sem_comprovantes = (
                resultado[
                    "arquivos_sem_comprovantes"
                ]
            )


            if arquivos_sem_comprovantes:

                for arquivo in arquivos_sem_comprovantes:

                    tamanho = (
                        arquivo["tamanho"]
                    )

                    st.write(
                        f"**{arquivo['nome']}**  \n"
                        f"📄 {arquivo['quantidade']} arquivos  \n"
                        f"💾 {formatar_tamanho(tamanho)}"
                    )


                    with open(
                        arquivo["caminho"],
                        "rb"
                    ) as arquivo_zip:

                        st.download_button(
                            label=(
                                f"⬇️ Baixar "
                                f"{arquivo['nome']}"
                            ),

                            data=arquivo_zip.read(),

                            file_name=arquivo[
                                "nome"
                            ],

                            mime="application/zip",

                            key=(
                                "download_sem_"
                                + arquivo["nome"]
                            ),

                            use_container_width=True
                        )

            else:

                st.info(
                    "Todas as páginas foram identificadas "
                    "como comprovantes."
                )


            # ==================================================
            # DOWNLOAD DE TODOS OS ZIPs
            # ==================================================

            todos_os_arquivos = (
                arquivos_comprovantes
                +
                arquivos_sem_comprovantes
            )


            if todos_os_arquivos:

                st.subheader(
                    "📥 Baixar todos os ZIPs"
                )


                caminho_zip_final = os.path.join(
                    resultado["pasta_saida"],
                    "TODOS_OS_ZIPS.zip"
                )


                criar_zip_final(
                    todos_os_arquivos,
                    caminho_zip_final
                )


                with open(
                    caminho_zip_final,
                    "rb"
                ) as arquivo_final:

                    st.download_button(
                        label=(
                            "⬇️ BAIXAR TODOS OS ZIPs"
                        ),

                        data=arquivo_final.read(),

                        file_name=(
                            "TODOS_OS_ZIPS.zip"
                        ),

                        mime="application/zip",

                        key="download_todos",

                        use_container_width=True
                    )


            # ==================================================
            # DIAGNÓSTICO
            # ==================================================

            with st.expander(
                "🔎 Ver diagnóstico das páginas"
            ):

                for item in resultado[
                    "diagnostico"
                ]:

                    pagina = item[
                        "pagina"
                    ]

                    tipo = item[
                        "tipo"
                    ]

                    tamanho = item.get(
                        "tamanho_formatado",
                        ""
                    )

                    st.write(
                        f"Página **{pagina}** → "
                        f"{tipo}"
                        +
                        (
                            f" → {tamanho}"
                            if tamanho
                            else ""
                        )
                    )


        except Exception as erro:

            st.error(
                "❌ Ocorreu um erro durante o processamento."
            )

            st.exception(
                erro
            )


        finally:

            # ==================================================
            # LIMPEZA
            # ==================================================

            # Não apagamos a pasta aqui porque os arquivos
            # ainda podem ser necessários pelos botões
            # de download do Streamlit durante a execução.
            #
            # O sistema operacional poderá limpar os
            # temporários posteriormente.


            gc.collect()
