import streamlit as st
import os
import re
import unicodedata
import tempfile
import shutil
import gc

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
# NORMALIZA TEXTO
# ============================================================

def normalizar_texto(texto):
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper()

    # Junta quebras de linha, tabs e espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


# ============================================================
# IDENTIFICA COMPROVANTE
# ============================================================

def identificar_comprovante(texto):

    texto = normalizar_texto(texto)

    if not texto:
        return None

    # ========================================================
    # PIX
    # ========================================================

    # COMPROVANTE PIX
    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?PIX\b",
        texto
    ):
        return "PIX"

    # COMPROVANTE DE PAGAMENTO PIX
    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bPAGAMENTO\b", texto)
        and re.search(r"\bPIX\b", texto)
    ):
        return "PIX"

    # PIX + COMPROVANTE
    if (
        re.search(r"\bPIX\b", texto)
        and re.search(r"\bCOMPROVANTE\b", texto)
    ):
        return "PIX"

    # PAGAMENTO PIX
    if re.search(
        r"\bPAGAMENTO\b.*\bPIX\b",
        texto
    ):
        return "PIX"

    # ========================================================
    # TRANSFERÊNCIA
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bTRANSFERENCIA\b", texto)
    ):
        return "TRANSFERENCIA"

    if (
        re.search(r"\bTRANSFERENCIA\b", texto)
        and re.search(r"\bCOMPROVANTE\b", texto)
    ):
        return "TRANSFERENCIA"

    # ========================================================
    # TRANSAÇÃO BANCÁRIA
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bTRANSACAO\b", texto)
        and re.search(r"\bBANCARIA\b", texto)
    ):
        return "TRANSACAO_BANCARIA"

    # ========================================================
    # PAGAMENTO
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bPAGAMENTO\b", texto)
    ):
        return "PAGAMENTO"

    # ========================================================
    # DEPÓSITO
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bDEPOSITO\b", texto)
    ):
        return "DEPOSITO"

    # ========================================================
    # TED
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bTED\b", texto)
    ):
        return "TED"

    # ========================================================
    # DOC
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bDOC\b", texto)
    ):
        return "DOC"

    # ========================================================
    # BOLETO
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bBOLETO\b", texto)
    ):
        return "BOLETO"

    # ========================================================
    # AGENDAMENTO
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bAGENDAMENTO\b", texto)
    ):
        return "AGENDAMENTO"

    # ========================================================
    # TRANSFERÊNCIA ELETRÔNICA
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bTRANSFERENCIA\b", texto)
        and re.search(r"\bELETRONICA\b", texto)
    ):
        return "TRANSFERENCIA_ELETRONICA"

    # ========================================================
    # TRANSFERÊNCIA BANCÁRIA
    # ========================================================

    if (
        re.search(r"\bCOMPROVANTE\b", texto)
        and re.search(r"\bTRANSFERENCIA\b", texto)
        and re.search(r"\bBANCARIA\b", texto)
    ):
        return "TRANSFERENCIA_BANCARIA"

    # ========================================================
    # OUTRO COMPROVANTE
    # ========================================================

    # Regra geral:
    # qualquer página que tenha COMPROVANTE
    # será considerada comprovante.
    if re.search(
        r"\bCOMPROVANTE\b",
        texto
    ):
        return "OUTRO_COMPROVANTE"

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
# SALVA PDF
# ============================================================

def salvar_writer(writer, caminho):

    with open(
        caminho,
        "wb"
    ) as arquivo:

        writer.write(arquivo)


# ============================================================
# GERA PDF TEMPORÁRIO
# ============================================================

def gerar_pdf_temporario(
    reader,
    paginas,
    pasta_temp,
    nome_temp
):

    caminho = os.path.join(
        pasta_temp,
        nome_temp
    )

    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(
            reader.pages[pagina]
        )

    salvar_writer(
        writer,
        caminho
    )

    tamanho = os.path.getsize(
        caminho
    )

    del writer

    gc.collect()

    return caminho, tamanho


# ============================================================
# SALVA GRUPO FINAL
# ============================================================

def salvar_grupo_final(
    reader,
    paginas,
    pasta_saida,
    prefixo,
    numero
):

    nome = (
        f"{prefixo}_{numero:03d}.pdf"
    )

    caminho = os.path.join(
        pasta_saida,
        nome
    )

    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(
            reader.pages[pagina]
        )

    salvar_writer(
        writer,
        caminho
    )

    tamanho = os.path.getsize(
        caminho
    )

    del writer

    gc.collect()

    return caminho, tamanho


# ============================================================
# AGRUPA PÁGINAS
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    prefixo,
    pasta_saida,
    pasta_temp,
    progress_bar,
    inicio_progresso,
    fim_progresso
):

    # Mantemos margem abaixo de 10 MB
    LIMITE_INTERNO_BYTES = 9_500_000

    arquivos = []

    grupo_atual = []

    numero_arquivo = 1

    total = len(paginas)

    for indice, pagina in enumerate(paginas):

        grupo_teste = (
            grupo_atual + [pagina]
        )

        caminho_teste, tamanho_teste = (
            gerar_pdf_temporario(
                reader,
                grupo_teste,
                pasta_temp,
                f"teste_{prefixo}_{indice}.pdf"
            )
        )

        # ----------------------------------------------------
        # ULTRAPASSOU O LIMITE
        # ----------------------------------------------------

        if (
            tamanho_teste > LIMITE_INTERNO_BYTES
            and grupo_atual
        ):

            caminho_final, tamanho_final = (
                salvar_grupo_final(
                    reader,
                    grupo_atual,
                    pasta_saida,
                    prefixo,
                    numero_arquivo
                )
            )

            arquivos.append({
                "nome": os.path.basename(
                    caminho_final
                ),
                "caminho": caminho_final,
                "tamanho": tamanho_final,
                "paginas": len(
                    grupo_atual
                )
            })

            numero_arquivo += 1

            # Começa novo grupo
            grupo_atual = [
                pagina
            ]

        else:

            grupo_atual = grupo_teste

        # Remove arquivo de teste
        try:

            os.remove(
                caminho_teste
            )

        except:

            pass

        # ----------------------------------------------------
        # PROGRESSO
        # ----------------------------------------------------

        if total > 0:

            progresso = (
                inicio_progresso
                +
                (
                    (indice + 1) / total
                )
                *
                (
                    fim_progresso
                    -
                    inicio_progresso
                )
            )

            progress_bar.progress(
                min(
                    int(progresso),
                    100
                )
            )

    # --------------------------------------------------------
    # ÚLTIMO GRUPO
    # --------------------------------------------------------

    if grupo_atual:

        caminho_final, tamanho_final = (
            salvar_grupo_final(
                reader,
                grupo_atual,
                pasta_saida,
                prefixo,
                numero_arquivo
            )
        )

        arquivos.append({
            "nome": os.path.basename(
                caminho_final
            ),
            "caminho": caminho_final,
            "tamanho": tamanho_final,
            "paginas": len(
                grupo_atual
            )
        })

    return arquivos


# ============================================================
# PROCESSA PDF
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar
):

    reader = PdfReader(
        caminho_pdf
    )

    total_paginas = len(
        reader.pages
    )

    # ========================================================
    # PROCURA ANEXO
    # ========================================================

    pagina_anexo = None

    for i, pagina in enumerate(
        reader.pages
    ):

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except:

            texto = ""

        texto_normalizado = (
            normalizar_texto(
                texto
            )
        )

        if re.search(
            r"\bANEXO\b",
            texto_normalizado
        ):

            pagina_anexo = i

            break

        progresso = int(
            (
                (i + 1)
                /
                max(total_paginas, 1)
            )
            * 20
        )

        progress_bar.progress(
            min(
                progresso,
                20
            )
        )

    # ========================================================
    # COMEÇA DEPOIS DO ANEXO
    # ========================================================

    if pagina_anexo is not None:

        pagina_inicio = (
            pagina_anexo + 1
        )

    else:

        pagina_inicio = 0

    # ========================================================
    # LISTAS
    # ========================================================

    paginas_comprovantes = []

    paginas_sem_comprovantes = []

    contadores = {}

    diagnostico = []

    paginas_processar = list(
        range(
            pagina_inicio,
            total_paginas
        )
    )

    total_processar = len(
        paginas_processar
    )

    # ========================================================
    # ANALISA CADA PÁGINA
    # ========================================================

    for indice, numero_pagina in enumerate(
        paginas_processar
    ):

        pagina = reader.pages[
            numero_pagina
        ]

        try:

            texto = (
                pagina.extract_text()
                or ""
            )

        except:

            texto = ""

        tipo = identificar_comprovante(
            texto
        )

        # ----------------------------------------------------
        # COMPROVANTE
        # ----------------------------------------------------

        if tipo:

            paginas_comprovantes.append(
                numero_pagina
            )

            contadores[tipo] = (
                contadores.get(
                    tipo,
                    0
                )
                +
                1
            )

        # ----------------------------------------------------
        # NÃO COMPROVANTE
        # ----------------------------------------------------

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

        # ----------------------------------------------------
        # DIAGNÓSTICO
        # ----------------------------------------------------

        diagnostico.append({
            "pagina": numero_pagina + 1,
            "tipo": (
                tipo
                if tipo
                else "NAO_COMPROVANTE"
            ),
            "texto": (
                normalizar_texto(
                    texto
                )[:500]
            )
        })

        # ----------------------------------------------------
        # PROGRESSO
        # ----------------------------------------------------

        if total_processar > 0:

            progresso = (
                20
                +
                int(
                    (
                        (indice + 1)
                        /
                        total_processar
                    )
                    * 40
                )
            )

            progress_bar.progress(
                min(
                    progresso,
                    60
                )
            )

    # ========================================================
    # CRIA PASTAS
    # ========================================================

    pasta_saida = os.path.join(
        pasta_trabalho,
        "resultado"
    )

    pasta_temp = os.path.join(
        pasta_trabalho,
        "temporarios"
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
    # AGRUPA COMPROVANTES
    # ========================================================

    arquivos_comprovantes = (
        agrupar_paginas(
            reader=reader,
            paginas=paginas_comprovantes,
            prefixo="COMPROVANTES",
            pasta_saida=pasta_saida,
            pasta_temp=pasta_temp,
            progress_bar=progress_bar,
            inicio_progresso=60,
            fim_progresso=80
        )
    )

    # ========================================================
    # AGRUPA NÃO COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = (
        agrupar_paginas(
            reader=reader,
            paginas=paginas_sem_comprovantes,
            prefixo="SEM_COMPROVANTES",
            pasta_saida=pasta_saida,
            pasta_temp=pasta_temp,
            progress_bar=progress_bar,
            inicio_progresso=80,
            fim_progresso=100
        )
    )

    progress_bar.progress(
        100
    )

    return {
        "arquivos_comprovantes":
            arquivos_comprovantes,

        "arquivos_sem_comprovantes":
            arquivos_sem_comprovantes,

        "contadores":
            contadores,

        "diagnostico":
            diagnostico,

        "total_paginas":
            total_paginas,

        "pagina_anexo":
            pagina_anexo,

        "total_comprovantes":
            len(
                paginas_comprovantes
            ),

        "total_sem_comprovantes":
            len(
                paginas_sem_comprovantes
            )
    }


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador de Comprovantes"
)

st.write(
    "Envie o PDF mensal para separar "
    "automaticamente os comprovantes "
    "das demais páginas."
)

st.info(
    "O sistema identifica PIX, transferência, "
    "pagamento, TED, DOC, depósito, boleto "
    "e outros documentos que contenham "
    "a palavra COMPROVANTE."
)


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📎 Selecione o arquivo PDF",
    type=["pdf"],
    help="Selecione o PDF que deseja processar."
)


# ============================================================
# ARQUIVO CARREGADO
# ============================================================

if arquivo is not None:

    tamanho_upload = len(
        arquivo.getbuffer()
    )

    st.success(
        f"Arquivo carregado: **{arquivo.name}**"
    )

    st.write(
        "Tamanho do arquivo: "
        f"**{formatar_tamanho(tamanho_upload)}**"
    )

    # ========================================================
    # BOTÃO PROCESSAR
    # ========================================================

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        progress_bar = st.progress(
            0
        )

        status = st.empty()

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        caminho_pdf = os.path.join(
            pasta_trabalho,
            arquivo.name
        )

        try:

            status.info(
                "Salvando arquivo..."
            )

            with open(
                caminho_pdf,
                "wb"
            ) as f:

                f.write(
                    arquivo.getbuffer()
                )

            status.info(
                "Analisando páginas..."
            )

            resultado = processar_pdf(
                caminho_pdf,
                pasta_trabalho,
                progress_bar
            )

            st.session_state[
                "resultado"
            ] = resultado

            st.session_state[
                "pasta_trabalho"
            ] = pasta_trabalho

            status.success(
                "✅ Processamento concluído!"
            )

            st.balloons()

        except Exception as e:

            status.error(
                "❌ Erro durante o processamento."
            )

            st.exception(e)

            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except:

                pass


# ============================================================
# RESULTADOS
# ============================================================

if "resultado" in st.session_state:

    resultado = (
        st.session_state[
            "resultado"
        ]
    )

    st.divider()

    st.subheader(
        "📊 Resultado"
    )

    # ========================================================
    # INDICADORES
    # ========================================================

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Páginas do PDF",
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

    # ========================================================
    # TIPOS ENCONTRADOS
    # ========================================================

    contadores = (
        resultado[
            "contadores"
        ]
    )

    if contadores:

        st.subheader(
            "🔎 Tipos de comprovantes encontrados"
        )

        tipos_ordenados = sorted(
            contadores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        numero_colunas = min(
            4,
            len(tipos_ordenados)
        )

        colunas = st.columns(
            numero_colunas
        )

        for i, (
            tipo,
            quantidade
        ) in enumerate(
            tipos_ordenados
        ):

            with colunas[
                i % numero_colunas
            ]:

                st.metric(
                    tipo.replace(
                        "_",
                        " "
                    ),
                    quantidade
                )

    # ========================================================
    # ALERTA PIX
    # ========================================================

    quantidade_pix = (
        contadores.get(
            "PIX",
            0
        )
    )

    if quantidade_pix > 0:

        st.success(
            f"💚 Foram encontrados "
            f"**{quantidade_pix} comprovante(s) PIX**."
        )

    else:

        st.warning(
            "⚠️ Nenhum comprovante PIX "
            "foi identificado pelo texto "
            "extraído do PDF."
        )

    # ========================================================
    # DOWNLOAD DOS COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 PDFs de comprovantes"
    )

    arquivos_comprovantes = (
        resultado[
            "arquivos_comprovantes"
        ]
    )

    if arquivos_comprovantes:

        for arquivo_saida in (
            arquivos_comprovantes
        ):

            caminho = (
                arquivo_saida[
                    "caminho"
                ]
            )

            st.write(
                f"📄 **{arquivo_saida['nome']}**"
            )

            st.caption(
                f"Páginas: "
                f"{arquivo_saida['paginas']} | "
                f"Tamanho: "
                f"{formatar_tamanho(arquivo_saida['tamanho'])}"
            )

            try:

                with open(
                    caminho,
                    "rb"
                ) as f:

                    st.download_button(
                        label=(
                            f"⬇️ Baixar "
                            f"{arquivo_saida['nome']}"
                        ),
                        data=f.read(),
                        file_name=(
                            arquivo_saida[
                                "nome"
                            ]
                        ),
                        mime="application/pdf",
                        key=(
                            "download_comp_"
                            +
                            arquivo_saida[
                                "nome"
                            ]
                        ),
                        use_container_width=True
                    )

            except Exception as e:

                st.error(
                    f"Erro ao disponibilizar "
                    f"{arquivo_saida['nome']}: "
                    f"{e}"
                )

    else:

        st.warning(
            "Nenhum PDF de comprovante foi gerado."
        )

    # ========================================================
    # DOWNLOAD DOS SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 PDFs sem comprovantes"
    )

    arquivos_sem_comprovantes = (
        resultado[
            "arquivos_sem_comprovantes"
        ]
    )

    if arquivos_sem_comprovantes:

        for arquivo_saida in (
            arquivos_sem_comprovantes
        ):

            caminho = (
                arquivo_saida[
                    "caminho"
                ]
            )

            st.write(
                f"📄 **{arquivo_saida['nome']}**"
            )

            st.caption(
                f"Páginas: "
                f"{arquivo_saida['paginas']} | "
                f"Tamanho: "
                f"{formatar_tamanho(arquivo_saida['tamanho'])}"
            )

            try:

                with open(
                    caminho,
                    "rb"
                ) as f:

                    st.download_button(
                        label=(
                            f"⬇️ Baixar "
                            f"{arquivo_saida['nome']}"
                        ),
                        data=f.read(),
                        file_name=(
                            arquivo_saida[
                                "nome"
                            ]
                        ),
                        mime="application/pdf",
                        key=(
                            "download_sem_"
                            +
                            arquivo_saida[
                                "nome"
                            ]
                        ),
                        use_container_width=True
                    )

            except Exception as e:

                st.error(
                    f"Erro ao disponibilizar "
                    f"{arquivo_saida['nome']}: "
                    f"{e}"
                )

    else:

        st.info(
            "Não existem páginas sem comprovantes."
        )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    st.divider()

    with st.expander(
        "🔍 Diagnóstico das páginas"
    ):

        st.write(
            "Aqui você consegue verificar "
            "o que o sistema encontrou em cada página."
        )

        for item in resultado[
            "diagnostico"
        ]:

            tipo = item[
                "tipo"
            ]

            if tipo == "PIX":

                st.success(
                    f"Página {item['pagina']} → "
                    f"PIX"
                )

            elif tipo != "NAO_COMPROVANTE":

                st.info(
                    f"Página {item['pagina']} → "
                    f"{tipo}"
                )

            else:

                st.write(
                    f"Página {item['pagina']} → "
                    f"Não identificado"
                )

            if item["texto"]:

                st.caption(
                    item["texto"]
                )

            else:

                st.caption(
                    "⚠️ Nenhum texto foi extraído "
                    "desta página."
                )
