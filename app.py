import streamlit as st
from pypdf import PdfReader, PdfWriter
import tempfile
from pathlib import Path
import shutil
import os
import re
import unicodedata
import gc


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Limite máximo desejado
LIMITE_FINAL_BYTES = 10_000_000

# Limite interno de segurança.
# Paramos em 9,5 MB para evitar que o arquivo final
# ultrapasse 10 MB por pequenas diferenças de gravação.
LIMITE_INTERNO_BYTES = 9_500_000

LIMITE_FINAL_MB = 10.00


# ============================================================
# CONFIGURAÇÃO DO STREAMLIT
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

    # --------------------------------------------------------
    # COMPROVANTE PIX
    # --------------------------------------------------------

    if "COMPROVANTE PIX" in texto:
        return "PIX"

    # --------------------------------------------------------
    # COMPROVANTE DE TRANSFERENCIA
    # --------------------------------------------------------

    if "COMPROVANTE DE TRANSFERENCIA" in texto:
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # COMPROVANTE DE TRANSACAO BANCARIA
    # --------------------------------------------------------

    if "COMPROVANTE DE TRANSACAO BANCARIA" in texto:
        return "TRANSACAO_BANCARIA"

    return None


# ============================================================
# IDENTIFICA ANEXO
# ============================================================

def identificar_anexo(texto):

    texto = normalizar_texto(texto)

    return bool(
        re.search(
            r"\bANEXO\b",
            texto
        )
    )


# ============================================================
# SALVA PDF EM ARQUIVO TEMPORÁRIO
# ============================================================

def salvar_writer(writer, caminho):

    with open(
        caminho,
        "wb"
    ) as arquivo:

        writer.write(
            arquivo
        )


# ============================================================
# GERA UM PDF TEMPORÁRIO COM AS PÁGINAS
# ============================================================

def gerar_pdf_temporario(
    reader,
    paginas,
    pasta_temp,
    nome_temp
):

    writer = PdfWriter()

    for numero_pagina in paginas:

        writer.add_page(
            reader.pages[numero_pagina]
        )

    caminho = (
        Path(pasta_temp)
        / nome_temp
    )

    salvar_writer(
        writer,
        caminho
    )

    tamanho = caminho.stat().st_size

    del writer

    gc.collect()

    return caminho, tamanho


# ============================================================
# COPIA UM PDF TEMPORÁRIO PARA O RESULTADO FINAL
# ============================================================

def salvar_grupo_final(
    reader,
    paginas,
    pasta_saida,
    prefixo,
    numero_arquivo
):

    nome = (
        f"{prefixo}_"
        f"{numero_arquivo:03d}.pdf"
    )

    caminho = (
        Path(pasta_saida)
        / nome
    )

    writer = PdfWriter()

    for numero_pagina in paginas:

        writer.add_page(
            reader.pages[numero_pagina]
        )

    salvar_writer(
        writer,
        caminho
    )

    tamanho = caminho.stat().st_size

    del writer

    gc.collect()

    return {
        "nome": nome,
        "caminho": str(caminho),
        "tamanho": tamanho,
        "acima_limite": tamanho > LIMITE_FINAL_BYTES
    }


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

    resultados = []

    if not paginas:
        return resultados

    total = len(paginas)

    paginas_atual = []

    numero_arquivo = 1

    for posicao, numero_pagina in enumerate(paginas):

        # ====================================================
        # PROGRESSO
        # ====================================================

        progresso = (
            inicio_progresso
            +
            (
                (posicao + 1)
                / total
            )
            *
            (
                fim_progresso
                - inicio_progresso
            )
        )

        progress_bar.progress(
            min(progresso, 1.0)
        )

        # ====================================================
        # SE NÃO EXISTE GRUPO ATUAL
        # ====================================================

        if not paginas_atual:

            paginas_atual = [
                numero_pagina
            ]

            # Testa a página sozinha
            caminho_teste, tamanho_teste = (
                gerar_pdf_temporario(
                    reader,
                    paginas_atual,
                    pasta_temp,
                    f"teste_{prefixo}.pdf"
                )
            )

            # ------------------------------------------------
            # Página sozinha já ultrapassa o limite
            # ------------------------------------------------

            if tamanho_teste > LIMITE_INTERNO_BYTES:

                resultado = salvar_grupo_final(
                    reader,
                    paginas_atual,
                    pasta_saida,
                    prefixo,
                    numero_arquivo
                )

                resultados.append(
                    resultado
                )

                numero_arquivo += 1

                paginas_atual = []

            # Remove teste
            try:
                caminho_teste.unlink()
            except Exception:
                pass

            del caminho_teste

            gc.collect()

            continue

        # ====================================================
        # TESTA ADICIONAR A PRÓXIMA PÁGINA
        # ====================================================

        paginas_teste = (
            paginas_atual
            +
            [numero_pagina]
        )

        caminho_teste, tamanho_teste = (
            gerar_pdf_temporario(
                reader,
                paginas_teste,
                pasta_temp,
                f"teste_{prefixo}.pdf"
            )
        )

        # ====================================================
        # AINDA CABE
        # ====================================================

        if tamanho_teste <= LIMITE_INTERNO_BYTES:

            paginas_atual.append(
                numero_pagina
            )

        # ====================================================
        # NÃO CABE
        # ====================================================

        else:

            # ------------------------------------------------
            # Salva grupo anterior
            # ------------------------------------------------

            resultado = salvar_grupo_final(
                reader,
                paginas_atual,
                pasta_saida,
                prefixo,
                numero_arquivo
            )

            resultados.append(
                resultado
            )

            numero_arquivo += 1

            # ------------------------------------------------
            # Começa novo grupo com a página atual
            # ------------------------------------------------

            paginas_atual = [
                numero_pagina
            ]

            # ------------------------------------------------
            # Verifica se a página individual também é grande
            # ------------------------------------------------

            caminho_pagina, tamanho_pagina = (
                gerar_pdf_temporario(
                    reader,
                    paginas_atual,
                    pasta_temp,
                    f"pagina_{prefixo}.pdf"
                )
            )

            if tamanho_pagina > LIMITE_INTERNO_BYTES:

                resultado = salvar_grupo_final(
                    reader,
                    paginas_atual,
                    pasta_saida,
                    prefixo,
                    numero_arquivo
                )

                resultado["acima_limite"] = True

                resultados.append(
                    resultado
                )

                numero_arquivo += 1

                paginas_atual = []

            try:
                caminho_pagina.unlink()
            except Exception:
                pass

            del caminho_pagina

        # ====================================================
        # REMOVE ARQUIVO DE TESTE
        # ====================================================

        try:
            caminho_teste.unlink()
        except Exception:
            pass

        del caminho_teste

        gc.collect()

    # ========================================================
    # SALVA ÚLTIMO GRUPO
    # ========================================================

    if paginas_atual:

        resultado = salvar_grupo_final(
            reader,
            paginas_atual,
            pasta_saida,
            prefixo,
            numero_arquivo
        )

        resultados.append(
            resultado
        )

    gc.collect()

    return resultados


# ============================================================
# FORMATA TAMANHO
# ============================================================

def formatar_tamanho(bytes_tamanho):

    return (
        f"{bytes_tamanho / 1_000_000:.2f} MB"
    )


# ============================================================
# PROCESSA O PDF
# ============================================================

def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar
):

    # ========================================================
    # CRIA PASTAS
    # ========================================================

    pasta_comprovantes = (
        Path(pasta_trabalho)
        / "COMPROVANTES"
    )

    pasta_sem_comprovantes = (
        Path(pasta_trabalho)
        / "SEM_COMPROVANTES"
    )

    pasta_temp = (
        Path(pasta_trabalho)
        / "TEMP"
    )

    pasta_comprovantes.mkdir(
        exist_ok=True
    )

    pasta_sem_comprovantes.mkdir(
        exist_ok=True
    )

    pasta_temp.mkdir(
        exist_ok=True
    )

    # ========================================================
    # ABRE PDF
    # ========================================================

    with open(
        caminho_pdf,
        "rb"
    ) as arquivo_pdf:

        reader = PdfReader(
            arquivo_pdf
        )

        total_paginas = len(
            reader.pages
        )

        paginas_comprovantes = []

        paginas_sem_comprovantes = []

        contadores = {
            "PIX": 0,
            "TRANSFERENCIA": 0,
            "TRANSACAO_BANCARIA": 0
        }

        encontrou_anexo = False

        # ====================================================
        # LEITURA DAS PÁGINAS
        # ====================================================

        for numero_pagina in range(
            total_paginas
        ):

            pagina = reader.pages[
                numero_pagina
            ]

            try:

                texto = (
                    pagina.extract_text()
                    or ""
                )

            except Exception:

                texto = ""

            # ------------------------------------------------
            # PROGRESSO DA LEITURA
            # ------------------------------------------------

            progresso = (
                (numero_pagina + 1)
                / total_paginas
            ) * 0.30

            progress_bar.progress(
                min(progresso, 0.30)
            )

            # ------------------------------------------------
            # PROCURA ANEXO
            # ------------------------------------------------

            if not encontrou_anexo:

                if identificar_anexo(
                    texto
                ):

                    encontrou_anexo = True

                # Não inclui a página do título ANEXO
                continue

            # ------------------------------------------------
            # IDENTIFICA COMPROVANTE
            # ------------------------------------------------

            tipo = identificar_comprovante(
                texto
            )

            if tipo:

                paginas_comprovantes.append(
                    numero_pagina
                )

                contadores[tipo] += 1

            else:

                paginas_sem_comprovantes.append(
                    numero_pagina
                )

        # ====================================================
        # AGRUPA COMPROVANTES
        # ====================================================

        arquivos_comprovantes = (
            agrupar_paginas(
                reader=reader,
                paginas=paginas_comprovantes,
                prefixo="COMPROVANTES",
                pasta_saida=pasta_comprovantes,
                pasta_temp=pasta_temp,
                progress_bar=progress_bar,
                inicio_progresso=0.30,
                fim_progresso=0.65
            )
        )

        # ====================================================
        # AGRUPA SEM COMPROVANTES
        # ====================================================

        arquivos_sem_comprovantes = (
            agrupar_paginas(
                reader=reader,
                paginas=paginas_sem_comprovantes,
                prefixo="SEM_COMPROVANTES",
                pasta_saida=pasta_sem_comprovantes,
                pasta_temp=pasta_temp,
                progress_bar=progress_bar,
                inicio_progresso=0.65,
                fim_progresso=1.0
            )
        )

    # ========================================================
    # LIMPA TEMPORÁRIOS
    # ========================================================

    try:
        shutil.rmtree(
            pasta_temp,
            ignore_errors=True
        )
    except Exception:
        pass

    gc.collect()

    progress_bar.progress(1.0)

    return (
        arquivos_comprovantes,
        arquivos_sem_comprovantes,
        contadores,
        encontrou_anexo
    )


# ============================================================
# LIMPA PROCESSAMENTO ANTERIOR
# ============================================================

def limpar_processamento_anterior():

    pasta_anterior = st.session_state.get(
        "pasta_trabalho"
    )

    if pasta_anterior:

        try:

            shutil.rmtree(
                pasta_anterior,
                ignore_errors=True
            )

        except Exception:
            pass

    st.session_state.pop(
        "pasta_trabalho",
        None
    )

    st.session_state.pop(
        "processado",
        None
    )


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "📄 Separador e Agrupador de Comprovantes"
)

st.write(
    "Processamento de PDFs mensais com agrupamento "
    "em arquivos de até 10 MB."
)


# ============================================================
# REGRAS
# ============================================================

with st.expander(
    "🔎 Regras do processamento"
):

    st.write(
        "O sistema procura o ANEXO e processa as páginas "
        "seguintes."
    )

    st.write(
        "São considerados comprovantes:"
    )

    st.write(
        "• COMPROVANTE PIX"
    )

    st.write(
        "• COMPROVANTE DE TRANSFERENCIA"
    )

    st.write(
        "• COMPROVANTE DE TRANSACAO BANCARIA"
    )

    st.write(
        "O sistema utiliza 9,5 MB como limite interno "
        "para garantir que o arquivo final fique abaixo "
        "de 10 MB."
    )


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "Selecione o PDF mensal",
    type=["pdf"]
)


# ============================================================
# INFORMA TAMANHO
# ============================================================

if arquivo is not None:

    tamanho_upload = (
        arquivo.size
    )

    st.info(
        f"📄 {arquivo.name} — "
        f"{formatar_tamanho(tamanho_upload)}"
    )


# ============================================================
# BOTÃO PROCESSAR
# ============================================================

if arquivo is not None:

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        # ----------------------------------------------------
        # LIMPA PROCESSAMENTO ANTERIOR
        # ----------------------------------------------------

        limpar_processamento_anterior()

        # ----------------------------------------------------
        # CRIA DIRETÓRIO DE TRABALHO
        # ----------------------------------------------------

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        pasta_trabalho_path = Path(
            pasta_trabalho
        )

        st.session_state[
            "pasta_trabalho"
        ] = pasta_trabalho

        # ----------------------------------------------------
        # SALVA UPLOAD NO DISCO
        # ----------------------------------------------------

        caminho_pdf = (
            pasta_trabalho_path
            / "arquivo_original.pdf"
        )

        with open(
            caminho_pdf,
            "wb"
        ) as arquivo_saida:

            arquivo_saida.write(
                arquivo.getbuffer()
            )

        # ----------------------------------------------------
        # BARRA DE PROGRESSO
        # ----------------------------------------------------

        progress_bar = st.progress(
            0
        )

        status = st.empty()

        status.info(
            "🔎 Iniciando processamento..."
        )

        try:

            # ================================================
            # PROCESSA
            # ================================================

            (
                arquivos_comprovantes,
                arquivos_sem_comprovantes,
                contadores,
                encontrou_anexo
            ) = processar_pdf(
                caminho_pdf=str(
                    caminho_pdf
                ),
                pasta_trabalho=pasta_trabalho,
                progress_bar=progress_bar
            )

            # ================================================
            # SALVA RESULTADOS NO SESSION STATE
            # ================================================

            st.session_state[
                "arquivos_comprovantes"
            ] = arquivos_comprovantes

            st.session_state[
                "arquivos_sem_comprovantes"
            ] = arquivos_sem_comprovantes

            st.session_state[
                "contadores"
            ] = contadores

            st.session_state[
                "encontrou_anexo"
            ] = encontrou_anexo

            st.session_state[
                "processado"
            ] = True

            status.success(
                "✅ Processamento concluído!"
            )

            gc.collect()

        except Exception as erro:

            status.error(
                "❌ O aplicativo encontrou um erro "
                "durante o processamento."
            )

            st.error(
                f"Detalhes: {erro}"
            )

            st.exception(
                erro
            )

            # Limpa em caso de erro
            try:

                shutil.rmtree(
                    pasta_trabalho,
                    ignore_errors=True
                )

            except Exception:
                pass


# ============================================================
# MOSTRA RESULTADOS
# ============================================================

if st.session_state.get(
    "processado",
    False
):

    arquivos_comprovantes = (
        st.session_state[
            "arquivos_comprovantes"
        ]
    )

    arquivos_sem_comprovantes = (
        st.session_state[
            "arquivos_sem_comprovantes"
        ]
    )

    contadores = (
        st.session_state[
            "contadores"
        ]
    )

    encontrou_anexo = (
        st.session_state[
            "encontrou_anexo"
        ]
    )

    # ========================================================
    # ANEXO
    # ========================================================

    if encontrou_anexo:

        st.success(
            "✅ ANEXO localizado."
        )

    else:

        st.warning(
            "⚠️ ANEXO não localizado."
        )

    # ========================================================
    # RESUMO
    # ========================================================

    total_comprovantes = sum(
        contadores.values()
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "PIX",
            contadores["PIX"]
        )

    with col2:

        st.metric(
            "Transferência",
            contadores["TRANSFERENCIA"]
        )

    with col3:

        st.metric(
            "Transação bancária",
            contadores[
                "TRANSACAO_BANCARIA"
            ]
        )

    with col4:

        st.metric(
            "Total",
            total_comprovantes
        )

    # ========================================================
    # COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📦 COMPROVANTES"
    )

    if arquivos_comprovantes:

        st.write(
            f"**{len(arquivos_comprovantes)}** "
            "arquivo(s) gerado(s)."
        )

        for item in arquivos_comprovantes:

            nome = item["nome"]

            caminho = item["caminho"]

            tamanho = item["tamanho"]

            tamanho_mb = (
                tamanho
                / 1_000_000
            )

            acima = item[
                "acima_limite"
            ]

            if acima:

                st.error(
                    f"⚠️ {nome} — "
                    f"{tamanho_mb:.2f} MB — "
                    f"ACIMA DE 10 MB"
                )

            else:

                st.success(
                    f"✅ {nome} — "
                    f"{tamanho_mb:.2f} MB / "
                    f"10,00 MB"
                )

            # ------------------------------------------------
            # DOWNLOAD
            # ------------------------------------------------

            if os.path.exists(
                caminho
            ):

                with open(
                    caminho,
                    "rb"
                ) as arquivo_download:

                    dados_download = (
                        arquivo_download.read()
                    )

                st.download_button(
                    label=(
                        f"⬇️ Baixar {nome}"
                    ),
                    data=dados_download,
                    file_name=nome,
                    mime="application/pdf",
                    key=f"comp_{nome}",
                    use_container_width=True
                )

                del dados_download

                gc.collect()

    else:

        st.info(
            "Nenhum comprovante foi encontrado."
        )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 SEM COMPROVANTES"
    )

    if arquivos_sem_comprovantes:

        st.write(
            f"**{len(arquivos_sem_comprovantes)}** "
            "arquivo(s) gerado(s)."
        )

        for item in arquivos_sem_comprovantes:

            nome = item["nome"]

            caminho = item["caminho"]

            tamanho = item["tamanho"]

            tamanho_mb = (
                tamanho
                / 1_000_000
            )

            acima = item[
                "acima_limite"
            ]

            if acima:

                st.error(
                    f"⚠️ {nome} — "
                    f"{tamanho_mb:.2f} MB — "
                    f"ACIMA DE 10 MB"
                )

            else:

                st.success(
                    f"✅ {nome} — "
                    f"{tamanho_mb:.2f} MB / "
                    f"10,00 MB"
                )

            # ------------------------------------------------
            # DOWNLOAD
            # ------------------------------------------------

            if os.path.exists(
                caminho
            ):

                with open(
                    caminho,
                    "rb"
                ) as arquivo_download:

                    dados_download = (
                        arquivo_download.read()
                    )

                st.download_button(
                    label=(
                        f"⬇️ Baixar {nome}"
                    ),
                    data=dados_download,
                    file_name=nome,
                    mime="application/pdf",
                    key=f"sem_{nome}",
                    use_container_width=True
                )

                del dados_download

                gc.collect()

    else:

        st.success(
            "Não existem páginas sem comprovantes."
        )
