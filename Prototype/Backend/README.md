# DoubleForge prototype - quick start

# 1) Install dependencies
pip install flask flask-cors requests matplotlib

# 2) Files
# Place app.py, node_launcher.py, experiment_runner.py, experiment_runner_sweep.py in same folder
# Ensure your Front-End folder (dashboard/log.html etc.) sits next to app.py

# 3) Launch a single node manually (for testing)
python app.py --port 5001
# open http://127.0.0.1:5001 in browser (serves log.html if Front-End/log.html exists)
# Use dashboard to arm/run attack, etc.

# 4) Launch multiple nodes (example: 2 nodes) via node_launcher
python node_launcher.py --nodes 2 --base-port 5001

# 5) Run a single experiment:
python experiment_runner.py

# 6) Run a sweep (automated experiments):
python experiment_runner_sweep.py

# Output:
# - experiment_results.csv is appended with each run result
# - sweep_results.csv contains parameter sweep records

# Notes:
# - SimBlock integration: SimBlock must POST well-formed JSON objects to /simblock_ingest on a running node:
#   - For transactions: {"kind":"add-tx","content":{"tx-id":"...", "sender":"X","receiver":"Y","amount":10}}
#   - For blocks: {"kind":"add-block","content":{...}}
# - You can also use the dashboard Run Attack button to arm the attack on the node
