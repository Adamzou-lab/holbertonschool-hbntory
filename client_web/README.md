# Client Web - Zaiko

Page publique, anonyme, sans authentification. HTML/CSS/JS pur (pas de framework), REST vers le
Service IA - cf. [docs/decisions.md](../docs/decisions.md) (Décision 2).

## Lancer en local

Nécessite que le [Service IA](../ai_service/README.md) tourne sur `http://127.0.0.1:5002`
(voir son README pour le lancer).

```bash
cd client_web
python3 -m http.server 8000
# puis ouvrir http://127.0.0.1:8000/index.html dans un navigateur
```

## Questions d'exemple à tester

- « Où trouver le produit HB-LAP-1001 ? »
- « Quels produits sont disponibles à la Branche Lyon ? »
- « Donne-moi les détails du produit HB-MON-2101. »
- « Si je veux 3 HB-LAP-1001, 2 HB-MON-2101 et 4 HB-KBD-4101, quelle(s) branche(s) visiter ? »

Ces exemples viennent du sujet (Task 6). Tant que `ai_service/` est en mode mock (cf. son
README), les réponses sont approximatives - elles seront correctes une fois l'agent réel
d'Erwan branché dessus.

## Ce qui est géré

- Zone de saisie + bouton, style chat (bulles utilisateur/assistant).
- Indicateur "L'assistant réfléchit…" pendant l'attente de la réponse.
- Message d'erreur explicite si le Service IA ne répond pas (service éteint, timeout réseau...).
