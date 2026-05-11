#!/bin/bash
set -e

MSG="${1:-actualización $(date '+%d/%m/%Y %H:%M')}"

git add dashboard.py analizador.py requirements.txt .gitignore \
        .github/workflows/email_diario.yml \
        olea_neutral_historico.csv 2>/dev/null || true

git diff --cached --quiet && echo "Sin cambios que subir." && exit 0

git commit -m "$MSG"
git push origin main

echo ""
echo "✔ Subido correctamente a GitHub."
