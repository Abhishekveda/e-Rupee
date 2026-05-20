"""
ai_compliance.py
----------------
Superseded by the custom e₹ AI Agent in v2.0.

The compliance logic is now split across:
  agent/fema_agent.py  - FEMA purpose code classification
  agent/risk_agent.py  - Pre-transfer compliance and risk scoring

No external API keys are required. The agent runs entirely on
Python standard library with TF-IDF similarity matching.
"""
