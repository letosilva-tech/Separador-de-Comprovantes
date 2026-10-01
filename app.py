def identificar_comprovante(texto):

    if not texto:
        return None

    texto_original = texto

    # Normalização
    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper()

    # Remove caracteres estranhos,
    # mas preserva letras e números
    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    ).strip()

    # ========================================================
    # PIX - REGRA MUITO ABRANGENTE
    # ========================================================

    possui_pix = bool(
        re.search(
            r"\bPIX\b",
            texto
        )
    )

    possui_comprovante = bool(
        re.search(
            r"\bCOMPROVANTE\b",
            texto
        )
    )

    if possui_pix and possui_comprovante:
        return "PIX"

    # Mesmo que venha "PAGAMENTO PIX"
    if re.search(
        r"\bPAGAMENTO\s+PIX\b",
        texto
    ):
        return "PIX"

    if re.search(
        r"\bPIX\s+PAGAMENTO\b",
        texto
    ):
        return "PIX"

    # ========================================================
    # TRANSFERÊNCIA
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSFERENCIA\b",
            texto
        )
    ):
        return "TRANSFERENCIA"

    # ========================================================
    # TRANSAÇÃO BANCÁRIA
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTRANSACAO\b",
            texto
        )
        and re.search(
            r"\bBANCARIA\b",
            texto
        )
    ):
        return "TRANSACAO_BANCARIA"

    # ========================================================
    # PAGAMENTO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bPAGAMENTO\b",
            texto
        )
    ):
        return "PAGAMENTO"

    # ========================================================
    # DEPÓSITO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bDEPOSITO\b",
            texto
        )
    ):
        return "DEPOSITO"

    # ========================================================
    # TED
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bTED\b",
            texto
        )
    ):
        return "TED"

    # ========================================================
    # DOC
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bDOC\b",
            texto
        )
    ):
        return "DOC"

    # ========================================================
    # BOLETO
    # ========================================================

    if (
        possui_comprovante
        and re.search(
            r"\bBOLETO\b",
            texto
        )
    ):
        return "BOLETO"

    # ========================================================
    # QUALQUER COMPROVANTE
    # ========================================================

    if possui_comprovante:
        return "OUTRO_COMPROVANTE"

    return None
