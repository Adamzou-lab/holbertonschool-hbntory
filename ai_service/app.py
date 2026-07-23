"""Service IA — MOCK temporaire.

Ce fichier n'implémente PAS de vrai agent IA. Il expose le contrat REST
que le Client Web consomme (POST /api/query), avec des réponses classées
par type de question (cf. Task 5.1 / ai_service/README.md), pour pouvoir
développer et tester le Client Web sans attendre que le serveur MCP et
l'agent (Erwan, Task 4-5) soient prêts.

Les 4 catégories ci-dessous correspondent exactement aux 4 tools stock du
serveur MCP d'Erwan (product_mcp_server/src/tools/stock_tools.py) : quand
le vrai agent remplacera ce mock, chaque catégorie appellera le tool du
même nom au lieu de renvoyer une réponse figée. Le contrat HTTP ne bouge
pas, donc le Client Web n'aura rien à modifier.
"""

import re

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
# CORS activé : en dev, le Client Web (ex: port 8000) et ce service
# (port 5002) tournent sur des origines différentes. Sans ça, le
# navigateur bloque les requêtes fetch() du Client Web par la politique
# same-origin. Pas nécessaire si les deux finissent derrière le même
# reverse proxy en prod, mais indispensable pour le dev local séparé.
CORS(app)

SKU_PATTERN = re.compile(r"\bHB-[A-Z]{3}-\d{4}\b", re.IGNORECASE)


def classify(question):
    """Range la question dans une des 4 catégories supportées, ou None si
    elle sort du périmètre qu'on a défini (Task 5.1)."""
    lower = question.lower()

    if re.search(r"combien|si je veux|j'ai besoin de \d", lower) and (
        len(re.findall(r"\d+\s", lower)) >= 2 or " et " in lower
    ):
        return "shopping_list"

    # "quels produits"/"stock de la branche" est un signal plus précis que
    # "disponible" (qui apparaît aussi dans les questions de disponibilité
    # produit) : on le teste en premier pour éviter le faux-positif.
    inventory_words = ("quels produits", "stock de la branche", "en stock à")
    if any(w in lower for w in inventory_words):
        return "branch_inventory"

    availability_words = ("où", "ou trouver", "disponible", "quelle branche")
    if any(w in lower for w in availability_words):
        return "product_availability"

    detail_words = ("détail", "detail", "description", "qu'est-ce")
    if any(w in lower for w in detail_words):
        return "product_details"

    # Fallback : un sku seul, sans mot-clé -> on suppose une demande de détail.
    if SKU_PATTERN.search(question):
        return "product_details"

    return None


def answer_question(question):
    if not question.strip():
        return "Pose-moi une question sur un produit ou une branche."

    if any(w in question.lower() for w in ("bonjour", "salut")):
        return (
            "Bonjour ! Demande-moi la disponibilité d'un produit, le "
            "contenu d'une branche, ou une liste de courses."
        )

    category = classify(question)

    if category == "product_details":
        return (
            "[MOCK] HB-LAP-1001 — Holberton Student Laptop 14. Catégorie "
            "Laptops. (Nom/description réels viendront de l'API Produit "
            "via le serveur MCP.)"
        )

    if category == "product_availability":
        return (
            "[MOCK] HB-LAP-1001 est disponible à la Branche Lyon "
            "(12 unités)."
        )

    if category == "branch_inventory":
        return (
            "[MOCK] La Branche Lyon a 3 produits en stock : HB-LAP-1001, "
            "HB-KBD-4101, HB-MSE-4201."
        )

    if category == "shopping_list":
        return (
            "[MOCK] Pour cette liste, la Branche Lyon peut tout fournir "
            "en une seule visite."
        )

    return (
        "Je ne peux répondre qu'aux questions sur le détail d'un produit, "
        "sa disponibilité par branche, le contenu d'une branche, ou une "
        "liste de courses multi-produits. Ta question sort de ce "
        "périmètre pour l'instant."
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "mode": "mock"})


@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Le champ 'question' est requis."}), 400

    answer = answer_question(question)
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True, port=5002)
