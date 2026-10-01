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

# Limite máximo desejado
LIMITE_BYTES = 10_000_000

# Limite interno para deixar margem de segurança
# 9,5 MB = 9.500.000 bytes
LIMITE_INTERNO = 9_500_000


# ============================================================
# NORMALIZAÇÃO DO TEXTO
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

    # Mantém somente letras e números
    texto = re.sub(r"[^A-Z0-9]", " ", texto)

    # Remove espaços duplicados
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


# ============================================================
# IDENTIFICAÇÃO DO TIPO DE COMPROVANTE
# ============================================================

def identificar_comprovante(texto):
    texto_norm = normalizar_texto(texto)

    if not texto_norm:
        return None

    possui_comprovante = "COMPROVANTE" in texto_norm
    possui_pix = "PIX" in texto_norm

    # --------------------------------------------------------
    # PIX
    # --------------------------------------------------------

    if possui_comprovante and possui_pix:
        return "PIX"

    if "PAGAMENTO PIX" in texto_norm:
        return "PIX"

    if "PIX PAGAMENTO" in texto_norm:
        return "PIX"

    # --------------------------------------------------------
    # TRANSFERÊNCIA
    # --------------------------------------------------------

    if possui_comprovante and "TRANSFERENCIA" in texto_norm:
        return "TRANSFERENCIA"

    # --------------------------------------------------------
    # TRANSAÇÃO BANCÁRIA
    # --------------------------------------------------------

    if (
        possui_comprovante
        and "TRANSACAO" in texto_norm
        and "BANCARIA" in texto_norm
    ):
        return "TRANSACAO_BANCARIA"

    # --------------------------------------------------------
    # PAGAMENTO
    # --------------------------------------------------------

    if possui_comprovante and "PAGAMENTO" in texto_norm:
        return "PAGAMENTO"

    # --------------------------------------------------------
    # DEPÓSITO
    # --------------------------------------------------------

    if possui_comprovante and "DEPOSITO" in texto_norm:
        return "DEPOSITO"

    # --------------------------------------------------------
    # TED
    # --------------------------------------------------------

    if possui_comprovante and re.search(r"\bTED\b", texto_norm):
        return "TED"

    # --------------------------------------------------------
    # DOC
    # --------------------------------------------------------

    if possui_comprovante and re.search(r"\bDOC\b", texto_norm):
        return "DOC"

    # --------------------------------------------------------
    # BOLETO
    # --------------------------------------------------------

    if possui_comprovante and "BOLETO" in texto_norm:
        return "BOLETO"

    # --------------------------------------------------------
    # AGENDAMENTO
    # --------------------------------------------------------

    if possui_comprovante and "AGENDAMENTO" in texto_norm:
        return "AGENDAMENTO"

    # --------------------------------------------------------
    # QUALQUER OUTRO COMPROVANTE
    # --------------------------------------------------------

    if possui_comprovante:
        return "OUTRO_COMPROVANTE"

    return None


# ============================================================
# FORMATAÇÃO DE TAMANHO
# ============================================================

def formatar_tamanho(bytes_size):

    if bytes_size < 1024:
        return f"{bytes_size} bytes"

    if bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.2f} KB"

    return f"{bytes_size / (1024 * 1024):.2f} MB"


# ============================================================
# CRIA PDF A PARTIR DE PÁGINAS
# ============================================================

def criar_pdf(reader, paginas, caminho):

    writer = PdfWriter()

    for numero_pagina in paginas:
        writer.add_page(reader.pages[numero_pagina])

    with open(caminho, "wb") as arquivo:
        writer.write(arquivo)

    writer.close()

    tamanho = os.path.getsize(caminho)

    return tamanho


# ============================================================
# TESTA TAMANHO DE UM GRUPO
# ============================================================

def testar_grupo(
    reader,
    paginas,
    pasta_temp,
    contador
):

    caminho_teste = os.path.join(
        pasta_temp,
        f"teste_{contador}.pdf"
    )

    writer = PdfWriter()

    for numero_pagina in paginas:
        writer.add_page(reader.pages[numero_pagina])

    with open(caminho_teste, "wb") as arquivo:
        writer.write(arquivo)

    writer.close()

    tamanho = os.path.getsize(caminho_teste)

    try:
        os.remove(caminho_teste)
    except:
        pass

    return tamanho


# ============================================================
# AGRUPAMENTO DOS PDFs
# ============================================================

def agrupar_paginas(
    reader,
    paginas,
    pasta_saida,
    prefixo
):

    arquivos_gerados = []

    if not paginas:
        return arquivos_gerados

    # --------------------------------------------------------
    # IMPORTANTE:
    #
    # Aqui NÃO criamos um PDF por página.
    #
    # Vamos acumulando várias páginas no mesmo grupo.
    # Só criamos um novo arquivo quando o próximo grupo
    # ultrapassaria o limite.
    # --------------------------------------------------------

    grupo_atual = []

    numero_arquivo = 1
    contador_teste = 1

    for pagina in paginas:

        # ----------------------------------------------------
        # Primeiro elemento do grupo
        # ----------------------------------------------------

        if not grupo_atual:

            grupo_atual = [pagina]

            continue

        # ----------------------------------------------------
        # Testa se podemos colocar a nova página
        # no grupo atual
        # ----------------------------------------------------

        grupo_teste = grupo_atual + [pagina]

        tamanho_teste = testar_grupo(
            reader,
            grupo_teste,
            pasta_saida,
            contador_teste
        )

        contador_teste += 1

        # ----------------------------------------------------
        # Cabe no mesmo PDF
        # ----------------------------------------------------

        if tamanho_teste <= LIMITE_INTERNO:

            grupo_atual.append(pagina)

        # ----------------------------------------------------
        # Não cabe:
        #
        # grava o grupo atual
        # e começa outro grupo.
        # ----------------------------------------------------

        else:

            nome_arquivo = (
                f"{prefixo}_{numero_arquivo:03d}.pdf"
            )

            caminho_final = os.path.join(
                pasta_saida,
                nome_arquivo
            )

            tamanho_final = criar_pdf(
                reader,
                grupo_atual,
                caminho_final
            )

            arquivos_gerados.append({
                "nome": nome_arquivo,
                "caminho": caminho_final,
                "tamanho": tamanho_final,
                "paginas": len(grupo_atual)
            })

            numero_arquivo += 1

            # A página que não coube começa o próximo grupo
            grupo_atual = [pagina]

            gc.collect()

    # --------------------------------------------------------
    # GRAVA O ÚLTIMO GRUPO
    # --------------------------------------------------------

    if grupo_atual:

        nome_arquivo = (
            f"{prefixo}_{numero_arquivo:03d}.pdf"
        )

        caminho_final = os.path.join(
            pasta_saida,
            nome_arquivo
        )

        tamanho_final = criar_pdf(
            reader,
            grupo_atual,
            caminho_final
        )

        arquivos_gerados.append({
            "nome": nome_arquivo,
            "caminho": caminho_final,
            "tamanho": tamanho_final,
            "paginas": len(grupo_atual)
        })

    return arquivos_gerados


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar_pdf(caminho_pdf, pasta_trabalho):

    reader = PdfReader(caminho_pdf)

    total_paginas = len(reader.pages)

    paginas_comprovantes = []
    paginas_sem_comprovantes = []

    diagnostico = []

    contadores = {
        "PIX": 0,
        "TRANSFERENCIA": 0,
        "TRANSACAO_BANCARIA": 0,
        "PAGAMENTO": 0,
        "DEPOSITO": 0,
        "TED": 0,
        "DOC": 0,
        "BOLETO": 0,
        "AGENDAMENTO": 0,
        "OUTRO_COMPROVANTE": 0
    }

    # ========================================================
    # LEITURA E IDENTIFICAÇÃO DAS PÁGINAS
    # ========================================================

    progresso = st.progress(0)

    for i, pagina in enumerate(reader.pages):

        try:
            texto = pagina.extract_text() or ""
        except Exception:
            texto = ""

        tipo = identificar_comprovante(texto)

        if tipo:

            paginas_comprovantes.append(i)

            if tipo in contadores:
                contadores[tipo] += 1

            # Guarda diagnóstico principalmente para PIX
            if (
                tipo == "PIX"
                or "COMPROVANTE" in normalizar_texto(texto)
            ):
                diagnostico.append({
                    "pagina": i + 1,
                    "tipo": tipo,
                    "texto": texto[:3000]
                })

        else:

            paginas_sem_comprovantes.append(i)

        progresso.progress(
            min((i + 1) / total_paginas, 1.0)
        )

    progresso.empty()

    # ========================================================
    # PASTAS
    # ========================================================

    pasta_resultado = os.path.join(
        pasta_trabalho,
        "resultado"
    )

    pasta_temporarios = os.path.join(
        pasta_trabalho,
        "temporarios"
    )

    os.makedirs(
        pasta_resultado,
        exist_ok=True
    )

    os.makedirs(
        pasta_temporarios,
        exist_ok=True
    )

    # ========================================================
    # AGRUPAR COMPROVANTES
    # ========================================================

    st.info(
        f"📄 Agrupando {len(paginas_comprovantes)} "
        f"páginas de comprovantes em arquivos de até "
        f"{LIMITE_INTERNO / (1024 * 1024):.1f} MB..."
    )

    arquivos_comprovantes = agrupar_paginas(
        reader=reader,
        paginas=paginas_comprovantes,
        pasta_saida=pasta_resultado,
        prefixo="COMPROVANTES"
    )

    # ========================================================
    # AGRUPAR SEM COMPROVANTES
    # ========================================================

    st.info(
        f"📄 Agrupando {len(paginas_sem_comprovantes)} "
        f"páginas sem comprovantes em arquivos de até "
        f"{LIMITE_INTERNO / (1024 * 1024):.1f} MB..."
    )

    arquivos_sem_comprovantes = agrupar_paginas(
        reader=reader,
        paginas=paginas_sem_comprovantes,
        pasta_saida=pasta_resultado,
        prefixo="SEM_COMPROVANTES"
    )

    # ========================================================
    # LIMPEZA
    # ========================================================

    gc.collect()

    return {
        "total_paginas": total_paginas,
        "paginas_comprovantes": len(paginas_comprovantes),
        "paginas_sem_comprovantes": len(paginas_sem_comprovantes),
        "arquivos_comprovantes": arquivos_comprovantes,
        "arquivos_sem_comprovantes": arquivos_sem_comprovantes,
        "contadores": contadores,
        "diagnostico": diagnostico
    }


# ============================================================
# INTERFACE
# ============================================================

st.title("📄 Separador e Agrupador de Comprovantes")

st.write(
    "O sistema identifica os comprovantes e agrupa as páginas "
    "em arquivos PDF de até aproximadamente 10 MB."
)

st.caption(
    "Limite interno utilizado: 9,5 MB por arquivo, "
    "para manter margem de segurança."
)


# ============================================================
# UPLOAD
# ============================================================

arquivo = st.file_uploader(
    "📎 Selecione o arquivo PDF",
    type=["pdf"]
)


if arquivo:

    tamanho_upload = len(arquivo.getvalue())

    st.info(
        f"Arquivo recebido: **{arquivo.name}** — "
        f"{formatar_tamanho(tamanho_upload)}"
    )

    if st.button(
        "🚀 Processar PDF",
        type="primary"
    ):

        # ====================================================
        # CRIA PASTA TEMPORÁRIA
        # ====================================================

        pasta_trabalho = tempfile.mkdtemp(
            prefix="separador_comprovantes_"
        )

        caminho_pdf = os.path.join(
            pasta_trabalho,
            "arquivo_original.pdf"
        )

        # Salva o arquivo enviado
        with open(caminho_pdf, "wb") as f:
            f.write(arquivo.getvalue())

        # Libera referência
        gc.collect()

        # ====================================================
        # PROCESSAMENTO
        # ====================================================

        try:

            resultado = processar_pdf(
                caminho_pdf,
                pasta_trabalho
            )

            # Guarda para os downloads
            st.session_state["resultado"] = resultado
            st.session_state["pasta_trabalho"] = pasta_trabalho

            st.success(
                "✅ Processamento concluído!"
            )

        except Exception as e:

            st.error(
                f"❌ Erro durante o processamento: {e}"
            )

            shutil.rmtree(
                pasta_trabalho,
                ignore_errors=True
            )


# ============================================================
# EXIBIÇÃO DO RESULTADO
# ============================================================

if "resultado" in st.session_state:

    resultado = st.session_state["resultado"]

    st.divider()

    st.subheader("📊 Resultado")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total de páginas",
            resultado["total_paginas"]
        )

    with col2:
        st.metric(
            "Páginas com comprovantes",
            resultado["paginas_comprovantes"]
        )

    with col3:
        st.metric(
            "Páginas sem comprovantes",
            resultado["paginas_sem_comprovantes"]
        )

    # ========================================================
    # TIPOS ENCONTRADOS
    # ========================================================

    st.subheader("🔎 Comprovantes identificados")

    contadores = resultado["contadores"]

    dados_tipos = []

    for tipo, quantidade in contadores.items():

        if quantidade > 0:

            dados_tipos.append({
                "Tipo": tipo,
                "Quantidade": quantidade
            })

    if dados_tipos:

        st.dataframe(
            dados_tipos,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "Nenhum tipo de comprovante foi identificado."
        )

    # ========================================================
    # ARQUIVOS DE COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 Arquivos agrupados — COMPROVANTES"
    )

    arquivos_comprovantes = resultado[
        "arquivos_comprovantes"
    ]

    if arquivos_comprovantes:

        st.success(
            f"{len(arquivos_comprovantes)} "
            f"arquivo(s) de comprovantes gerado(s)."
        )

        for arquivo_info in arquivos_comprovantes:

            nome = arquivo_info["nome"]
            caminho = arquivo_info["caminho"]
            tamanho = arquivo_info["tamanho"]
            paginas = arquivo_info["paginas"]

            tamanho_mb = tamanho / (
                1024 * 1024
            )

            col1, col2, col3 = st.columns(
                [3, 1, 2]
            )

            with col1:

                st.write(
                    f"📄 **{nome}**"
                )

            with col2:

                st.write(
                    f"{paginas} páginas"
                )

            with col3:

                st.write(
                    f"{tamanho_mb:.2f} MB"
                )

            with open(
                caminho,
                "rb"
            ) as f:

                dados = f.read()

            st.download_button(
                label=f"⬇️ Baixar {nome}",
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"download_{nome}"
            )

    else:

        st.warning(
            "Nenhum arquivo de comprovantes foi gerado."
        )

    # ========================================================
    # ARQUIVOS SEM COMPROVANTES
    # ========================================================

    st.divider()

    st.subheader(
        "📁 Arquivos agrupados — SEM COMPROVANTES"
    )

    arquivos_sem = resultado[
        "arquivos_sem_comprovantes"
    ]

    if arquivos_sem:

        st.success(
            f"{len(arquivos_sem)} "
            f"arquivo(s) sem comprovantes gerado(s)."
        )

        for arquivo_info in arquivos_sem:

            nome = arquivo_info["nome"]
            caminho = arquivo_info["caminho"]
            tamanho = arquivo_info["tamanho"]
            paginas = arquivo_info["paginas"]

            tamanho_mb = tamanho / (
                1024 * 1024
            )

            col1, col2, col3 = st.columns(
                [3, 1, 2]
            )

            with col1:

                st.write(
                    f"📄 **{nome}**"
                )

            with col2:

                st.write(
                    f"{paginas} páginas"
                )

            with col3:

                st.write(
                    f"{tamanho_mb:.2f} MB"
                )

            with open(
                caminho,
                "rb"
            ) as f:

                dados = f.read()

            st.download_button(
                label=f"⬇️ Baixar {nome}",
                data=dados,
                file_name=nome,
                mime="application/pdf",
                key=f"download_{nome}"
            )

    else:

        st.warning(
            "Nenhum arquivo sem comprovantes foi gerado."
        )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    st.divider()

    with st.expander(
        "🔍 Diagnóstico das páginas identificadas"
    ):

        diagnostico = resultado["diagnostico"]

        if diagnostico:

            for item in diagnostico:

                st.markdown(
                    f"### Página {item['pagina']} — "
                    f"{item['tipo']}"
                )

                st.text(
                    item["texto"]
                )

        else:

            st.write(
                "Nenhuma página foi registrada no diagnóstico."
            )
