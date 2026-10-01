```python
import streamlit as st
import pandas as pd
import re
import io
import zipfile

from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Renomeador de PDFs",
    page_icon="📄",
    layout="wide"
)

# Limite máximo de cada PDF gerado
LIMITE_MB = 10
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


# ============================================================
# FUNÇÕES
# ============================================================

def normalizar_valor(valor):
    """
    Converte qualquer valor para uma representação numérica simples.

    Exemplos:

    72699       -> 72699
    72699.0     -> 72699
    "72699"     -> 72699
    " 72699 "   -> 72699
    "OP 72699"  -> 72699
    """

    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    # Remove .0 do final
    texto = re.sub(r"\.0+$", "", texto)

    # Mantém somente números
    numeros = re.sub(r"\D", "", texto)

    return numeros


def extrair_op_do_nome(nome_arquivo):
    """
    Pega a primeira sequência de números do nome do PDF.

    Exemplo:

    72699-instituto-qualisa-de-gestao-ltda.pdf

    retorna:

    72699
    """

    nome_sem_extensao = nome_arquivo.rsplit(".", 1)[0]

    encontrado = re.match(
        r"^\s*(\d+)",
        nome_sem_extensao
    )

    if encontrado:
        return encontrado.group(1)

    return ""


def extrair_op_do_texto(texto):
    """
    Procura uma Ordem de Pagamento dentro do texto da página.

    Aceita exemplos como:

    OP 72699
    OP: 72699
    OP - 72699
    O.P. 72699
    Ordem de Pagamento: 72699
    Ordem de Pagamento 72699
    """

    if not texto:
        return ""

    # Junta quebras de linha e espaços
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    padroes = [

        # Ordem de Pagamento: 72699
        r"ordem\s+de\s+pagamento\s*[:\-]?\s*(\d+)",

        # OP: 72699
        r"\bOP\s*[:\-]?\s*(\d+)",

        # O.P.: 72699
        r"\bO\.?\s*P\.?\s*[:\-]?\s*(\d+)",
    ]

    for padrao in padroes:

        encontrado = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE
        )

        if encontrado:

            return normalizar_valor(
                encontrado.group(1)
            )

    return ""


def criar_nome_arquivo(item, nome_original):
    """
    Cria o novo nome do PDF.
    """

    item = str(item).strip()

    # Remove .0
    item = re.sub(
        r"\.0+$",
        "",
        item
    )

    return f"Item {item} - {nome_original}"


def tamanho_mb(conteudo):
    """
    Retorna o tamanho do conteúdo em MB.
    """

    return len(conteudo) / (
        1024 * 1024
    )


def gerar_pdf_paginas(reader, paginas):
    """
    Cria um novo PDF contendo somente as páginas informadas.

    paginas:
        lista com os índices das páginas.
    """

    writer = PdfWriter()

    for indice in paginas:

        writer.add_page(
            reader.pages[indice]
        )

    buffer = io.BytesIO()

    writer.write(buffer)

    return buffer.getvalue()


def dividir_por_tamanho(
    reader,
    paginas,
    limite_bytes=LIMITE_BYTES
):
    """
    Divide um conjunto de páginas em blocos de até 10 MB.

    Importante:
    A divisão por tamanho só acontece quando o documento
    individual ultrapassa o limite.

    O sistema tenta colocar o maior número possível
    de páginas em cada parte.
    """

    blocos = []

    bloco_atual = []

    for pagina in paginas:

        teste = bloco_atual + [
            pagina
        ]

        conteudo_teste = gerar_pdf_paginas(
            reader,
            teste
        )

        tamanho_teste = len(
            conteudo_teste
        )

        # Ainda cabe no limite
        if tamanho_teste <= limite_bytes:

            bloco_atual.append(
                pagina
            )

        else:

            # Salva o bloco anterior
            if bloco_atual:

                conteudo_bloco = (
                    gerar_pdf_paginas(
                        reader,
                        bloco_atual
                    )
                )

                blocos.append(
                    (
                        bloco_atual.copy(),
                        conteudo_bloco
                    )
                )

                bloco_atual = [
                    pagina
                ]

            else:

                # Uma única página já ultrapassa 10 MB
                conteudo_pagina = (
                    gerar_pdf_paginas(
                        reader,
                        [pagina]
                    )
                )

                blocos.append(
                    (
                        [pagina],
                        conteudo_pagina
                    )
                )

                bloco_atual = []

    # Último bloco
```
