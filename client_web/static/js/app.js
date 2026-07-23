// URL du Service IA. En dev, il tourne sur le port 5002 (cf. ai_service/app.py).
// 127.0.0.1 plutôt que "localhost" : Flask n'écoute qu'en IPv4 par défaut,
// alors que "localhost" peut se résoudre en IPv6 (::1) selon l'OS/le
// navigateur, ce qui casse la connexion. À adapter si le service est
// déployé ailleurs (docker-compose, prod...).
const AI_SERVICE_URL = "http://127.0.0.1:5002/api/query";

const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const input = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");

function appendMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
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
    throw new Error(body.error || `Erreur serveur (${response.status}).`);
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

  const pending = appendMessage("pending", "L'assistant réfléchit…");

  try {
    const answer = await askQuestion(question);
    pending.remove();
    appendMessage("bot", answer);
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
