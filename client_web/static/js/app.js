// Appel same-origin : nginx (cf. client_web/nginx.conf) relaie /query vers le
// Service IA via le réseau interne de Compose (ai_service:8080, endpoint
// POST /query — pas /api/query).
//
// Volontairement une URL relative, pas http://127.0.0.1:8080 : coder l'hôte en
// dur expose à ce qu'un port-forward de l'IDE tenant déjà 127.0.0.1:8080
// intercepte la requête et réponde depuis un autre Service IA (données
// périmées, sans aucune erreur visible). Relative = toujours le service qui a
// servi la page.
const AI_SERVICE_URL = "/query";

const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const input = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");

const REDUCED_MOTION = window.matchMedia(
  "(prefers-reduced-motion: reduce)"
).matches;

function appendMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

function appendPendingMessage() {
  const el = document.createElement("div");
  el.className = "msg pending";
  el.innerHTML =
    '<span class="typing-dots"><span></span><span></span><span></span></span>';
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

function appendBotMessage(text) {
  const el = document.createElement("div");
  el.className = "msg bot";
  chat.appendChild(el);

  if (REDUCED_MOTION || text.length === 0) {
    el.textContent = text;
    return el;
  }

  // Pas de vrai streaming depuis le Service IA (la réponse arrive d'un
  // coup) : on simule l'écriture progressive côté client. Vitesse
  // adaptative pour qu'une réponse longue ne prenne jamais plus de ~1.5s
  // à s'afficher — sinon l'effet devient gênant plutôt qu'agréable.
  el.classList.add("typing");
  const totalDurationMs = Math.min(1500, Math.max(300, text.length * 12));
  const stepMs = Math.max(8, totalDurationMs / text.length);
  let i = 0;
  const timer = setInterval(() => {
    i += 1;
    el.textContent = text.slice(0, i);
    chat.scrollTop = chat.scrollHeight;
    if (i >= text.length) {
      clearInterval(timer);
      el.classList.remove("typing");
    }
  }, stepMs);
  return el;
}

async function askQuestion(question) {
  const response = await fetch(AI_SERVICE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    // Le Service IA (FastAPI) renvoie les erreurs sous {"detail": ...} —
    // une chaîne pour une HTTPException, une liste d'objets pour une
    // erreur de validation Pydantic (422). "error" gardé en repli pour
    // rester compatible avec un éventuel autre backend.
    let message = body.error || `Erreur serveur (${response.status}).`;
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      message = body.detail[0].msg;
    }
    throw new Error(message);
  }

  const data = await response.json();
  return data.answer;
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  appendMessage("user", question);
  input.value = "";
  sendBtn.disabled = true;

  const pending = appendPendingMessage();

  try {
    const answer = await askQuestion(question);
    pending.remove();
    appendBotMessage(answer);
  } catch (err) {
    pending.remove();
    appendMessage(
      "error",
      "Impossible de contacter le service IA. Vérifie qu'il tourne bien " +
        `(${AI_SERVICE_URL}). Détail : ${err.message}`
    );
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});
