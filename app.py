import streamlit as st
import os
import re
import unicodedata
import tempfile
import shutil
import gc

from io import BytesIO
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Separador de Comprovantes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# FUNÇÕES
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

    # Junta quebras de linha e espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def identificar_comprovante(texto):
    """
    Identifica diversos tipos de comprovante.

    A regra principal é:
    qualquer página que contenha a palavra COMPROVANTE
    será considerada um comprovante.
    """

    texto = normalizar_texto(texto)

    if not texto:
        return None

    # --------------------------------------------------------
    # TIPOS ESPECÍFICOS
    # --------------------------------------------------------

    if re.search(r"\bCOMPROVANTE\s+PIX\b", texto):
        return "PIX"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TRANSFERENCIA\b",
        texto
    ):
        return "TRANSFERENCIA"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TRANSACAO\s+BANCARIA\b",
        texto
    ):
        return "TRANSACAO_BANCARIA"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?PAGAMENTO\b",
        texto
    ):
        return "PAGAMENTO"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?DEPOSITO\b",
        texto
    ):
        return "DEPOSITO"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TED\b",
        texto
    ):
        return "TED"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?DOC\b",
        texto
    ):
        return "DOC"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?BOLETO\b",
        texto
    ):
        return "BOLETO"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?AGENDAMENTO\b",
        texto
    ):
        return "AGENDAMENTO"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TRANSFERENCIA\s+ELETRONICA\b",
        texto
    ):
        return "TRANSFERENCIA_ELETRONICA"

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TRANSFERENCIA\s+BANCARIA\b",
        texto
    ):
        return "TRANSFERENCIA_BANCARIA"

    # --------------------------------------------------------
    # REGRA GERAL
    # --------------------------------------------------------
    # Se tiver COMPROVANTE na página, considera comprovante.
    #
    # Isso permite pegar tipos que não estão previstos acima.
    # --------------------------------------------------------

    if re.search(r"\bCOMPROVANTE\b", texto):
        return "OUTRO_COMPROVANTE"

    return None


def formatar_tamanho(tamanho):
    if tamanho < 1024:
        return f"{tamanho} B"

    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.2f} KB"

    return f"{tamanho / (1024 * 1024):.2f} MB"


def salvar_writer(writer, caminho):
    with open(caminho, "wb") as arquivo:
        writer.write(arquivo)


def gerar_pdf_temporario(
    reader,
    paginas,
    pasta_temp,
    nome_temp
):
    """
    Gera um PDF temporário para verificar o tamanho.
    """

    caminho = os.path.join(
        pasta_temp,
        nome_temp
    )

    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(reader.pages[pagina])

    salvar_writer(writer, caminho)

    tamanho = os.path.getsize(caminho)

    del writer
    gc.collect()

    return caminho, tamanho


def salvar_grupo_final(
    reader,
    paginas,
    pasta_saida,
    prefixo,
    numero
):
    """
    Salva o grupo definitivo.
    """

    nome = f"{prefixo}_{numero:03d}.pdf"

    caminho = os.path.join(
        pasta_saida,
        nome
    )

    writer = PdfWriter()

    for pagina in paginas:
        writer.add_page(reader.pages[pagina])

    salvar_writer(writer, caminho)

    tamanho = os.path.getsize(caminho)

    del writer
    gc.collect()

    return caminho, tamanho


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
    """
    Agrupa páginas em PDFs de aproximadamente até 9,5 MB.

    O limite interno é menor que 10 MB para deixar margem.
    """

    LIMITE_INTERNO_BYTES = 9_500_000

    arquivos = []

    grupo_atual = []
    numero_arquivo = 1

    total = len(paginas)

    for indice, pagina in enumerate(paginas):

        grupo_teste = grupo_atual + [pagina]

        caminho_teste, tamanho_teste = gerar_pdf_temporario(
            reader,
            grupo_teste,
            pasta_temp,
            f"teste_{prefixo}_{indice}.pdf"
        )

        # ----------------------------------------------------
        # SE PASSOU DO LIMITE
        # ----------------------------------------------------

        if (
            tamanho_teste > LIMITE_INTERNO_BYTES
            and grupo_atual
        ):

            # Salva o grupo anterior
            caminho_final, tamanho_final = salvar_grupo_final(
                reader,
                grupo_atual,
                pasta_saida,
                prefixo,
                numero_arquivo
            )

            arquivos.append({
                "nome": os.path.basename(caminho_final),
                "caminho": caminho_final,
                "tamanho": tamanho_final,
                "paginas": len(grupo_atual)
            })

            numero_arquivo += 1

            # Começa novo grupo
            grupo_atual = [pagina]

        else:
            grupo_atual = grupo_teste

        # Remove teste
        try:
            os.remove(caminho_teste)
        except:
            pass

        # Atualiza progresso
        if total > 0:
            progresso = inicio_progresso + (
                (indice + 1) / total
            ) * (fim_progresso - inicio_progresso)

            progress_bar.progress(
                min(int(progresso), 100)
            )

    # --------------------------------------------------------
    # SALVA ÚLTIMO GRUPO
    # --------------------------------------------------------

    if grupo_atual:

        caminho_final, tamanho_final = salvar_grupo_final(
            reader,
            grupo_atual,
            pasta_saida,
            prefixo,
            numero_arquivo
        )

        arquivos.append({
            "nome": os.path.basename(caminho_final),
            "caminho": caminho_final,
            "tamanho": tamanho_final,
            "paginas": len(grupo_atual)
        })

    return arquivos


def processar_pdf(
    caminho_pdf,
    pasta_trabalho,
    progress_bar
):

    reader = PdfReader(caminho_pdf)

    total_paginas = len(reader.pages)

    # ========================================================
    # LOCALIZA ANEXO
    # ========================================================

    pagina_anexo = None

    for i, pagina in enumerate(reader.pages):

        try:
            texto = pagina.extract_text() or ""
        except:
            texto = ""

        texto_normalizado = normalizar_texto(texto)

        if re.search(r"\bANEXO\b", texto_normalizado):

            pagina_anexo = i
            break

        progresso = int(
            ((i + 1) / total_paginas) * 20
        )

        progress_bar.progress(
            min(progresso, 20)
        )

    # Se encontrou ANEXO, começa depois dele.
    # Caso contrário, começa na primeira página.
    if pagina_anexo is not None:
        pagina_inicio = pagina_anexo + 1
    else:
        pagina_inicio = 0

    paginas_comprovantes = []
    paginas_sem_comprovantes = []

    contadores = {}

    # ========================================================
    # ANALISA PÁGINAS
    # ========================================================

    paginas_processar = list(
        range(
            pagina_inicio,
            total_paginas
        )
    )

    total_processar = len(paginas_processar)

    for indice, numero_pagina in enumerate(
        paginas_processar
    ):

        pagina = reader.pages[numero_pagina]

        try:
            texto = pagina.extract_text() or ""
        except:
            texto = ""

        tipo = identificar_comprovante(texto)

        if tipo:

            paginas_comprovantes.append(
                numero_pagina
            )

            contadores[tipo] = (
                contadores.get(tipo, 0) + 1
            )

        else:

            paginas_sem_comprovantes.append(
                numero_pagina
            )

        # Progresso entre 20 e 60
        if total_processar > 0:

            progresso = 20 + int(
                ((indice + 1) / total_processar) * 40
            )

            progress_bar.progress(
                min(progresso, 60)
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

    arquivos_comprovantes = agrupar_paginas(
        reader=reader,
        paginas=paginas_comprovantes,
        prefixo="COMPROVANTES",
        pasta_saida=pasta_saida,
        pasta_temp=pasta_temp,
        progress_bar=progress_bar,
        inicio_progresso=60,
        fim_progresso=80
    )

    # ========================================================
    # AGRUPA NÃO COMPROVANTES
    # ========================================================

    arquivos_sem_comprovantes = agrupar_paginas(
        reader=reader,
        paginas=paginas_sem_comprovantes,
        prefixo="SEM_COMPROVANTES",
        pasta_saida=pasta_saida,
        pasta_temp=pasta_temp,
        progress_bar=progress_bar,
        inicio_progresso=80,
        fim_progresso=100
    )

    progress_bar.progress(100)

    return {
        "arquivos_comprovantes": arquivos_comprovantes,
        "arquivos_sem_comprovantes": arquivos_sem_comprovantes,
        "contadores": contadores,
        "total_paginas": total_paginas,
        "pagina_anexo": pagina_anexo,
        "total_comprovantes": len(paginas_comprovantes),
        "total_sem_comprovantes": len(paginas_sem_comprovantes)
    }


# ============================================================
# INTERFACE
# ============================================================

st.title("📄 Separador de Comprovantes")

st.write(
    "Envie o PDF mensal para separar automaticamente "
    "os comprovantes das demais páginas."
)

st.info(
    "O sistema identifica PIX, transferência, pagamento, "
    "TED, DOC, depósito, boleto e também outros documentos "
    "que contenham a palavra COMPROVANTE."
)

# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📎 Selecione o arquivo PDF",
    type=["pdf"],
    help="Escolha o PDF que deseja processar."
)

# ============================================================
# QUANDO ARQUIVO FOR ENVIADO
# ============================================================

if arquivo is not None:

    st.success(
        f"Arquivo carregado: **{arquivo.name}**"
    )

    tamanho_upload = len(
        arquivo.getbuffer()
    )

    st.write(
        f"Tamanho do arquivo: "
        f"**{formatar_tamanho(tamanho_upload)}**"
    )

    if st.button(
        "🚀 Processar PDF",
        type="primary",
        use_container_width=True
    ):

        progress_bar = st.progress(0)

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        caminho_pdf = os.path.join(
            pasta_trabalho,
            arquivo.name
        )

        try:

            # Salva o upload no disco
            with open(
                caminho_pdf,
                "wb"
            ) as f:

                f.write(
                    arquivo.getbuffer()
                )

            # Processa
            resultado = processar_pdf(
                caminho_pdf,
                pasta_trabalho,
                progress_bar
            )

            # Guarda o resultado na sessão
            st.session_state["resultado"] = resultado
            st.session_state["pasta_trabalho"] = (
                pasta_trabalho
            )

            st.success(
                "✅ Processamento concluído!"
            )

        except Exception as e:

            st.error(
                "❌ Ocorreu um erro durante o processamento."
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

    resultado = st.session_state["resultado"]

    st.divider()

    st.subheader("📊 Resultado")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Páginas do PDF",
            resultado["total_paginas"]
        )

    with col2:
        st.metric(
            "Comprovantes",
            resultado["total_comprovantes"]
        )

    with col3:
        st.metric(
            "Sem comprovantes",
            resultado["total_sem_comprovantes"]
        )

    # ========================================================
    # TIPOS ENCONTRADOS
    # ========================================================

    contadores = resultado["contadores"]

    if contadores:

        st.subheader(
            "🔎 Comprovantes encontrados"
        )

        tipos_ordenados = sorted(
            contadores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        colunas = st.columns(
            min(4, len(tipos_ordenados))
        )

        for i, (tipo, quantidade) in enumerate(
            tipos_ordenados
        ):

            with colunas[
                i % len(colunas)
            ]:

                st.metric(
                    tipo.replace("_", " "),
                    quantidade
                )

    # ========================================================
    # COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 PDFs de comprovantes"
    )

    arquivos_comprovantes = (
        resultado["arquivos_comprovantes"]
    )

    if arquivos_comprovantes:

        for arquivo_saida in arquivos_comprovantes:

            caminho = arquivo_saida["caminho"]

            st.write(
                f"📄 **{arquivo_saida['nome']}**  \n"
                f"Páginas: {arquivo_saida['paginas']}  \n"
                f"Tamanho: {formatar_tamanho(arquivo_saida['tamanho'])}"
            )

            try:

                with open(
                    caminho,
                    "rb"
                ) as f:

                    st.download_button(
                        label=f"⬇️ Baixar {arquivo_saida['nome']}",
                        data=f.read(),
                        file_name=arquivo_saida["nome"],
                        mime="application/pdf",
                        key=f"download_comp_{arquivo_saida['nome']}",
                        use_container_width=True
                    )

            except Exception as e:

                st.error(
                    f"Erro ao disponibilizar "
                    f"{arquivo_saida['nome']}: {e}"
                )

    else:

        st.warning(
            "Nenhum comprovante foi encontrado."
        )

    # ========================================================
    # SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 PDFs sem comprovantes"
    )

    arquivos_sem_comprovantes = (
        resultado["arquivos_sem_comprovantes"]
    )

    if arquivos_sem_comprovantes:

        for arquivo_saida in arquivos_sem_comprovantes:

            caminho = arquivo_saida["caminho"]

            st.write(
                f"📄 **{arquivo_saida['nome']}**  \n"
                f"Páginas: {arquivo_saida['paginas']}  \n"
                f"Tamanho: {formatar_tamanho(arquivo_saida['tamanho'])}"
            )

            try:

                with open(
                    caminho,
                    "rb"
                ) as f:

                    st.download_button(
                        label=f"⬇️ Baixar {arquivo_saida['nome']}",
                        data=f.read(),
                        file_name=arquivo_saida["nome"],
                        mime="application/pdf",
                        key=f"download_sem_{arquivo_saida['nome']}",
                        use_container_width=True
                    )

            except Exception as e:

                st.error(
                    f"Erro ao disponibilizar "
                    f"{arquivo_saida['nome']}: {e}"
                )

    else:

        st.info(
            "Não existem páginas sem comprovantes."
        )
