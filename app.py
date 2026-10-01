def separar_comprovantes(
    leitor,
    progresso,
    status
):
    comprovantes = []

    paginas_brancas = 0
    paginas_sem_comprovante = []

    total_paginas = len(leitor.pages)

    for indice, pagina in enumerate(leitor.pages):

        numero_pagina = indice + 1

        progresso.progress(
            numero_pagina / total_paginas
        )

        status.text(
            f"🔍 Analisando página "
            f"{numero_pagina} de {total_paginas}..."
        )

        texto = pagina.extract_text() or ""

        tipo = identificar_tipo_comprovante(texto)

        # ====================================================
        # ENCONTROU UM COMPROVANTE
        # ====================================================

        if tipo is not None:

            comprovantes.append(
                {
                    "tipo": tipo,
                    "paginas": [pagina],
                    "pagina_inicio": numero_pagina,
                    "pagina_fim": numero_pagina
                }
            )

            continue

        # ====================================================
        # PÁGINA EM BRANCO
        # ====================================================

        if is_pagina_em_branco(pagina):

            paginas_brancas += 1

            continue

        # ====================================================
        # PÁGINA QUE NÃO É COMPROVANTE
        # ====================================================

        paginas_sem_comprovante.append(
            numero_pagina
        )

    return (
        comprovantes,
        paginas_brancas,
        paginas_sem_comprovante
    )
