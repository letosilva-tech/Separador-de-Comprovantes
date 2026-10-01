def separar_comprovantes(
    leitor,
    progresso,
    status
):

    comprovantes = []

    comprovante_atual = []

    tipo_atual = None

    pagina_inicio = None

    paginas_sem_comprovante = []

    total_paginas = len(leitor.pages)

    # ========================================================
    # ANALISA CADA PÁGINA
    # ========================================================

    for indice, pagina in enumerate(leitor.pages):

        numero_pagina = indice + 1

        progresso.progress(
            numero_pagina / total_paginas
        )

        status.text(
            f"🔍 Analisando página "
            f"{numero_pagina} de "
            f"{total_paginas}..."
        )

        # ----------------------------------------------------
        # EXTRAI TEXTO
        # ----------------------------------------------------

        texto = pagina.extract_text() or ""

        # ----------------------------------------------------
        # IDENTIFICA TIPO
        # ----------------------------------------------------

        tipo = identificar_tipo_comprovante(
            texto
        )

        # ====================================================
        # NOVO COMPROVANTE
        # ====================================================

        if tipo is not None:

            # ------------------------------------------------
            # Salva comprovante anterior
            # ------------------------------------------------

            if comprovante_atual:

                comprovantes.append({
                    "tipo": tipo_atual,
                    "paginas": comprovante_atual,
                    "pagina_inicio": pagina_inicio,
                    "pagina_fim": numero_pagina - 1
                })

            # ------------------------------------------------
            # Inicia novo comprovante
            # ------------------------------------------------

            comprovante_atual = [
                pagina
            ]

            tipo_atual = tipo

            pagina_inicio = numero_pagina

            continue

        # ====================================================
        # PÁGINA QUE NÃO É COMPROVANTE
        # ====================================================

        if not comprovante_atual:

            paginas_sem_comprovante.append({
                "pagina": numero_pagina,
                "objeto": pagina
            })

        else:

            # ------------------------------------------------
            # Página pertence ao comprovante atual
            # ------------------------------------------------

            # Se quiser que páginas em branco entre páginas
            # de um comprovante também sejam mantidas,
            # elas continuarão aqui.
            comprovante_atual.append(
                pagina
            )

    # ========================================================
    # SALVA O ÚLTIMO COMPROVANTE
    # ========================================================

    if comprovante_atual:

        comprovantes.append({
            "tipo": tipo_atual,
            "paginas": comprovante_atual,
            "pagina_inicio": pagina_inicio,
            "pagina_fim": total_paginas
        })

    return (
        comprovantes,
        paginas_sem_comprovante
    )
