#!/bin/bash

ORIGEM="/var/spool/cups"
DESTINO="/home/suporte/impressora/arquivo"

# Cria a pasta de destino caso não exista
mkdir -p "$DESTINO"

# Processa todos os arquivos d*
for arquivo in "$ORIGEM"/d*; do

    # Ignora caso não exista nenhum arquivo
    [ -f "$arquivo" ] || continue

    nome=$(basename "$arquivo")
    destino_pdf="$DESTINO/$nome.pdf"
    destino_original="$DESTINO/$nome"

    # Não processa novamente arquivos já copiados
    if [ -f "$destino_pdf" ] || [ -f "$destino_original" ]; then
        continue
    fi

    tipo=$(file -b "$arquivo")

    if echo "$tipo" | grep -qi "PDF"; then
        cp "$arquivo" "$destino_pdf"
        echo "[OK] PDF copiado: $nome.pdf"

    elif echo "$tipo" | grep -qi "gzip"; then

        # Descompacta para um arquivo temporário
        tmp=$(mktemp)

        if gzip -dc "$arquivo" > "$tmp" 2>/dev/null; then

            # Confirma que o conteúdo descompactado é realmente um PDF
            if file "$tmp" | grep -qi "PDF"; then
                mv "$tmp" "$destino_pdf"
                echo "[OK] GZIP convertido para PDF: $nome.pdf"
            else
                mv "$tmp" "$destino_original"
                echo "[AVISO] GZIP continha outro formato: $nome"
            fi

        else
            echo "[ERRO] Não foi possível descompactar $nome"
            rm -f "$tmp"
        fi

    else
        cp "$arquivo" "$destino_original"
        echo "[INFO] Arquivo copiado sem alteração: $nome ($tipo)"
    fi

done

echo "========================================="
echo "Processamento concluído."