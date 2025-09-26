async function fetchLogs() {
  const res = await fetch("http://127.0.0.1:5001/logs");
  const logs = await res.json();

  const logContainer = document.getElementById("logContainer");
  const attackContainer = document.querySelector(".box"); // Recent Attacks area

  if (logContainer) logContainer.innerHTML = "";
  if (attackContainer) attackContainer.innerHTML = "";

  logs.forEach(line => {
    const div = document.createElement("div");

    if (line.includes("[ATTACK]")) {
      div.className = "attack-success";
      div.innerText = line;
      if (attackContainer) attackContainer.appendChild(div.cloneNode(true));
    } else if (line.includes("[ATTACK-ARMED]")) {
      div.className = "attack-armed";
    } else if (line.includes("rejected")) {
      div.className = "rejected";
    } else {
      div.className = "normal";
    }

    if (logContainer) logContainer.appendChild(div);
  });
}
