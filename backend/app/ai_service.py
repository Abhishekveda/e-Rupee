"""
ai_service.py
-------------
This module has been superseded by the custom e₹ AI Agent
introduced in v2.0 of the bridge.

The agent lives in: backend/app/agent/

Sub-agents:
  fema_agent.py     - TF-IDF classification over 13 FEMA purpose codes
  risk_agent.py     - Rule-based transaction risk scoring (0-100)
  qa_agent.py       - RAG over RBI regulatory knowledge base
  orchestrator.py   - Routes requests to the right sub-agent
  knowledge_base.py - FEMA codes + RBI circulars (source-cited)

This file is kept for reference only and is no longer imported.
See /v1/agent/* endpoints in main.py for the live agent API.
"""
