// The small window on top: the agent's question and its answers (see attention.py).
const here = location.pathname.replace(/\/$/, "");
const state = document.getElementById("state");
async function answer(body) {
  state.textContent = "Przekazuję…";
  try {
    const reply = await fetch(here, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!reply.ok) throw new Error();
    state.textContent = "Przekazane. Ciąg dalszy w oknie NotarAI.";
    setTimeout(() => window.close(), 700);
  } catch { state.textContent = "To pytanie już nie czeka na odpowiedź. Zajrzyj do okna NotarAI."; }
}
(async () => {
  try {
    const reply = await fetch(here + "/dane");
    if (!reply.ok) throw new Error();
    const data = await reply.json();
    document.getElementById("text").textContent = data.text;
    const row = document.getElementById("answers");
    data.actions.forEach((action, index) => {
      const button = document.createElement("button");
      button.textContent = action;
      if (index === 0) button.className = "main";
      button.onclick = () => answer({ choice: index });
      row.append(button);
    });
    const later = document.createElement("button");
    later.textContent = "Później";
    later.onclick = () => window.close();
    row.append(later);
    if (data.free) {
      const own = document.getElementById("own");
      own.hidden = false;
      own.onsubmit = event => { event.preventDefault(); const words = document.getElementById("words").value.trim(); if (words) answer({ words }); };
    }
  } catch { document.getElementById("text").textContent = "To pytanie już nie czeka na odpowiedź."; }
})();
