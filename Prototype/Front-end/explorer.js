const BACKEND_BASE = "http://127.0.0.1:5001"; // backend node port

async function loadBlocks() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/chain`);
    const chain = await res.json();

    const tbody = document.querySelector("#blockTable tbody");
    tbody.innerHTML = "";

    chain.forEach(block => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${block.index}</td>
        <td>${block.hash.substring(0, 15)}...</td>
        <td>${block.prev_hash.substring(0, 15)}...</td>
        <td>${block.txs.length}</td>
        <td>${new Date(block.timestamp * 1000).toLocaleTimeString()}</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    console.error("Error loading blockchain:", err);
  }
}

async function loadMempool() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/mempool`);
    const mempool = await res.json();

    const tbody = document.querySelector("#mempoolTable tbody");
    tbody.innerHTML = "";

    if (mempool.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="4">No pending transactions</td>`;
      tbody.appendChild(row);
      return;
    }

    mempool.forEach(tx => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${tx.txid.substring(0, 10)}...</td>
        <td>${tx.sender}</td>
        <td>${tx.receiver}</td>
        <td>${tx.amount}</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    console.error("Error loading mempool:", err);
  }
}

// ✅ Auto refresh every 5 seconds
document.addEventListener("DOMContentLoaded", () => {
  loadBlocks();
  loadMempool();
  setInterval(() => {
    loadBlocks();
    loadMempool();
  }, 5000); // refreshes automatically every 5 seconds
});
