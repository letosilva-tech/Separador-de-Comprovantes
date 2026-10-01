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


st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide",
)



LIMITE_ZIP = 10 * 1024 * 1024


LIMITE_SEGURANCA = 9_500_000



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



def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    if not texto:
        return None


    if re.search(
        r"\bCOMPROVANTE\s+(?:DE\s+)?PIX\b",
        texto
    ):
        return "PIX"


    if re.search(
        r"\bCOMPROVANTE\s+(?:DE\s+)?TRANSFERENCIA\b",
        texto
    ):
        return "TRANSFERENCIA"



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


def salvar_writer(writer, caminho):

    with open(
        caminho,
        "wb"
    ) as arquivo:

        writer.write(
            arquivo
        )


def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar,
    status
):

    inicio = time.time()

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


    if total_paginas == 0:

        raise ValueError(
            "O PDF não possui páginas."
        )


    pasta_saida = os.path.join(
        pasta_trabalho,
        "saida"
    )

    os.makedirs(
        pasta_saida,
        exist_ok=True
    )


    writer_comprovantes = PdfWriter()

    writer_sem_comprovantes = PdfWriter()


    total_comprovantes = 0

    total_sem_comprovantes = 0

    quantidade_pix = 0

    quantidade_transferencia = 0

    quantidade_transacao = 0

    diagnostico = []


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


        if tipo:

            writer_comprovantes.add_page(
                pagina
            )

            total_comprovantes += 1


            if tipo == "PIX":

                quantidade_pix += 1


            elif tipo == "TRANSFERENCIA":

                quantidade_transferencia += 1


            elif tipo == "TRANSACAO_BANCARIA":

                quantidade_transacao += 1




        else:

            writer_sem_comprovantes.add_page(
                pagina
            )

            total_sem_comprovantes += 1


        # Libera memória
        gc.collect()



    caminho_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.pdf"
    )

    caminho_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.pdf"
    )


    if total_comprovantes > 0:

        status.info(
            "💾 Salvando PDF dos comprovantes..."
        )

        salvar_writer(
            writer_comprovantes,
            caminho_comprovantes
        )



    if total_sem_comprovantes > 0:

        status.info(
            "💾 Salvando PDF das páginas sem comprovantes..."
        )

        salvar_writer(
            writer_sem_comprovantes,
            caminho_sem_comprovantes
        )


    # Libera os writers

    del writer_comprovantes

    del writer_sem_comprovantes

    gc.collect()


    tamanho_comprovantes = 0

    tamanho_sem_comprovantes = 0


    if os.path.exists(
        caminho_comprovantes
    ):

        tamanho_comprovantes = os.path.getsize(
            caminho_comprovantes
        )


    if os.path.exists(
        caminho_sem_comprovantes
    ):

        tamanho_sem_comprovantes = os.path.getsize(
            caminho_sem_comprovantes
        )



    caminho_zip_comprovantes = os.path.join(
        pasta_saida,
        "COMPROVANTES.zip"
    )

    caminho_zip_sem_comprovantes = os.path.join(
        pasta_saida,
        "SEM_COMPROVANTES.zip"
    )


    if os.path.exists(
        caminho_comprovantes
    ):

        with zipfile.ZipFile(
            caminho_zip_comprovantes,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        ) as zip_file:

            zip_file.write(
                caminho_comprovantes,
                arcname="COMPROVANTES.pdf"
            )


    if os.path.exists(
        caminho_sem_comprovantes
    ):

        with zipfile.ZipFile(
            caminho_zip_sem_comprovantes,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1
        ) as zip_file:

            zip_file.write(
                caminho_sem_comprovantes,
                arcname="SEM_COMPROVANTES.pdf"
            )

    tamanho_zip_comprovantes = 0

    tamanho_zip_sem_comprovantes = 0


    if os.path.exists(
        caminho_zip_comprovantes
    ):

        tamanho_zip_comprovantes = os.path.getsize(
            caminho_zip_comprovantes
        )


    if os.path.exists(
        caminho_zip_sem_comprovantes
    ):

        tamanho_zip_sem_comprovantes = os.path.getsize(
            caminho_zip_sem_comprovantes
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

        "caminho_comprovantes":
            caminho_comprovantes,

        "caminho_sem_comprovantes":
            caminho_sem_comprovantes,

        "caminho_zip_comprovantes":
            caminho_zip_comprovantes,

        "caminho_zip_sem_comprovantes":
            caminho_zip_sem_comprovantes,

        "tamanho_comprovantes":
            tamanho_comprovantes,

        "tamanho_sem_comprovantes":
            tamanho_sem_comprovantes,

        "tamanho_zip_comprovantes":
            tamanho_zip_comprovantes,

        "tamanho_zip_sem_comprovantes":
            tamanho_zip_sem_comprovantes,

        "diagnostico":
            diagnostico,

        "tempo_total":
            tempo_total,
    }



st.title(
    "📄 Separador de Comprovantes"
)


st.write(
    """
    O sistema analisa o PDF página por página e separa:

    🔵 **COMPROVANTES**

    🟢 **PÁGINAS SEM COMPROVANTES**

    Todas as páginas de cada grupo são reunidas em **um único PDF**.

    Depois são disponibilizados também os arquivos ZIP.
    """
)


st.info(
    """
    💡 O PDF original não é alterado.
    As páginas são apenas classificadas e copiadas para
    dois novos arquivos PDF.
    """
)



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



            st.divider()

            st.subheader(
                "📊 Resultado"
            )


            col1, col2, col3, col4 = st.columns(
                4
            )


            col1.metric(
                "Total de páginas",
                resultado[
                    "total_paginas"
                ]
            )


            col2.metric(
                "Comprovantes",
                resultado[
                    "total_comprovantes"
                ]
            )


            col3.metric(
                "Sem comprovante",
                resultado[
                    "total_sem_comprovantes"
                ]
            )


            col4.metric(
                "Tempo",
                f"{resultado['tempo_total']:.1f}s"
            )



            st.subheader(
                "🔎 Tipos identificados"
            )


            c1, c2, c3 = st.columns(
                3
            )


            c1.metric(
                "🔵 PIX",
                resultado[
                    "quantidade_pix"
                ]
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



            if os.path.exists(
                resultado[
                    "caminho_comprovantes"
                ]
            ):

                st.subheader(
                    "📄 PDF — Comprovantes"
                )


                st.write(
                    f"**{resultado['total_comprovantes']} "
                    f"página(s)** — "
                    f"{formatar_tamanho(
                        resultado['tamanho_comprovantes']
                    )}"
                )


                with open(
                    resultado[
                        "caminho_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    st.download_button(
                        label="⬇️ Baixar COMPROVANTES.pdf",

                        data=arquivo.read(),

                        file_name="COMPROVANTES.pdf",

                        mime="application/pdf",

                        use_container_width=True,

                        key="download_comprovantes_pdf"
                    )


            if os.path.exists(
                resultado[
                    "caminho_sem_comprovantes"
                ]
            ):

                st.subheader(
                    "📄 PDF — Sem comprovantes"
                )


                st.write(
                    f"**{resultado['total_sem_comprovantes']} "
                    f"página(s)** — "
                    f"{formatar_tamanho(
                        resultado['tamanho_sem_comprovantes']
                    )}"
                )


                with open(
                    resultado[
                        "caminho_sem_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    st.download_button(
                        label="⬇️ Baixar SEM_COMPROVANTES.pdf",

                        data=arquivo.read(),

                        file_name="SEM_COMPROVANTES.pdf",

                        mime="application/pdf",

                        use_container_width=True,

                        key="download_sem_comprovantes_pdf"
                    )


            if os.path.exists(
                resultado[
                    "caminho_zip_comprovantes"
                ]
            ):

                st.subheader(
                    "📦 ZIP — Comprovantes"
                )


                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_zip_comprovantes"
                        ]
                    )
                )


                with open(
                    resultado[
                        "caminho_zip_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    st.download_button(
                        label="⬇️ Baixar COMPROVANTES.zip",

                        data=arquivo.read(),

                        file_name="COMPROVANTES.zip",

                        mime="application/zip",

                        use_container_width=True,

                        key="download_comprovantes_zip"
                    )



            if os.path.exists(
                resultado[
                    "caminho_zip_sem_comprovantes"
                ]
            ):

                st.subheader(
                    "📦 ZIP — Sem comprovantes"
                )


                st.write(
                    formatar_tamanho(
                        resultado[
                            "tamanho_zip_sem_comprovantes"
                        ]
                    )
                )


                with open(
                    resultado[
                        "caminho_zip_sem_comprovantes"
                    ],
                    "rb"
                ) as arquivo:

                    st.download_button(
                        label="⬇️ Baixar SEM_COMPROVANTES.zip",

                        data=arquivo.read(),

                        file_name="SEM_COMPROVANTES.zip",

                        mime="application/zip",

                        use_container_width=True,

                        key="download_sem_comprovantes_zip"
                    )



            if resultado[
                "diagnostico"
            ]:

                with st.expander(
                    "⚠️ Diagnóstico"
                ):

                    for mensagem in resultado[
                        "diagnostico"
                    ]:

                        st.write(
                            mensagem
                        )



            if resultado[
                "total_comprovantes"
            ] == 0:

                st.warning(
                    "Nenhum comprovante foi identificado. "
                    "Verifique se o PDF possui texto selecionável "
                    "ou se os termos utilizados nos comprovantes "
                    "são diferentes dos padrões configurados."
                )



            if resultado[
                "total_sem_comprovantes"
            ] == 0:

                st.info(
                    "Todas as páginas do PDF foram identificadas "
                    "como comprovantes."
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
