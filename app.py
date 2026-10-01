def identificar_comprovante(texto):

    texto_original = texto or ""

    texto = normalizar_texto(
        texto_original
    )

    # ========================================================
    # COMPROVANTE PIX
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+PIX\b",
        texto
    ):
        return "PIX"

    # ========================================================
    # COMPROVANTE DE TRANSFERÊNCIA
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TRANSFERENCIA\b",
        texto
    ):
        return "TRANSFERENCIA"

    # ========================================================
    # COMPROVANTE DE TRANSAÇÃO BANCÁRIA
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\s+(DE\s+)?TRANSACAO\s+BANCARIA\b",
        texto
    ):
        return "TRANSACAO_BANCARIA"

    # ========================================================
    # OUTROS TIPOS DE COMPROVANTE
    # ========================================================

    outros_comprovantes = [
        (
            r"\bCOMPROVANTE\s+(DE\s+)?PAGAMENTO\b",
            "PAGAMENTO"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?DEPOSITO\b",
            "DEPOSITO"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?TED\b",
            "TED"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?DOC\b",
            "DOC"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?BOLETO\b",
            "BOLETO"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?AGENDAMENTO\b",
            "AGENDAMENTO"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?TRANSFERENCIA\s+ELETRONICA\b",
            "TRANSFERENCIA_ELETRONICA"
        ),
        (
            r"\bCOMPROVANTE\s+(DE\s+)?TRANSFERENCIA\s+BANCARIA\b",
            "TRANSFERENCIA_BANCARIA"
        ),
    ]

    for padrao, tipo in outros_comprovantes:

        if re.search(
            padrao,
            texto
        ):
            return tipo

    # ========================================================
    # REGRA GERAL
    #
    # Se existir a palavra COMPROVANTE no texto da página,
    # considera a página como comprovante mesmo que seja um
    # modelo diferente dos tipos acima.
    # ========================================================

    if re.search(
        r"\bCOMPROVANTE\b",
        texto
    ):
        return "OUTRO_COMPROVANTE"

    return None
