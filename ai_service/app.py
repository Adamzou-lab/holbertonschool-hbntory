"""Service IA — MOCK temporaire.

Ce fichier n'implémente PAS de vrai agent IA. Il expose juste le contrat
REST que le Client Web va consommer (POST /api/query), avec des réponses
à base de mots-clés, pour pouvoir développer et tester le Client Web sans
attendre que le serveur MCP et l'agent (Erwan, Task 4-5) soient prêts.

Quand le vrai agent existera, seule la fonction answer_question() doit
changer (appeler l'agent au lieu de faire du matching de mots-clés) — le
contrat HTTP (POST /api/query -> {"answer": "..."}) ne bouge pas, donc le
Client Web n'aura rien à modifier.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
# CORS activé : en dev, le Client Web (ex: port 8000) et ce service
# (port 5002) tournent sur des origines différentes. Sans ça, le
# navigateur bloque les requêtes fetch() du Client Web par la politique
# same-origin. Pas nécessaire si les deux finissent derrière le même
# reverse proxy en prod, mais indispensable pour le dev local séparé.
CORS(app)


def answer_question(question):
    """Mock : réponses à base de mots-clés. À remplacer par l'appel à
    l'agent IA connecté au serveur MCP (cf. docs/decisions.md, Task 5)."""
    lower = question.lower()

    if not question.strip():
        return "Pose-moi une question sur un produit ou une branche."

    if "bonjour" in lower or "salut" in lower:
        return (
            "Bonjour ! Demande-moi la disponibilité d'un produit "
            "ou son détail."
        )

    if "hb-lap-1001" in lower or "laptop" in lower:
        return (
            "[MOCK] Le produit HB-LAP-1001 (Holberton Student Laptop 14) "
            "est disponible à la Branche Lyon (12 unités)."
        )

    if "branche" in lower and ("produit" in lower or "stock" in lower):
        return (
            "[MOCK] La Branche Lyon a 3 produits en stock : HB-LAP-1001, "
            "HB-KBD-4101, HB-MSE-4201."
        )

    return (
        "[MOCK] Je ne peux pas encore répondre précisément — l'agent IA "
        "réel (connecté au serveur MCP) n'est pas encore branché ici."
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
