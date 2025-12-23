---
trigger: manual
---

docs/architecture.md

Purpose: How the system is structured

Includes:
	•	High-level diagram (described in text)
	•	Backend vs frontend responsibilities
	•	WhatsApp send vs receive
	•	MCP + LLM flow
	•	Where business logic lives
	•	What must NEVER talk directly (e.g., WhatsApp → DB)

No code. No config.


<Module>
Whatsapp_receive
</Module>
This module is completely isolated from the entire application, so no dependencies outside the module.
<Working>
When webhook_verify is called, it should verify using the security functions already written. webhook_receive should push the data into the aws sqs using boto client and send back success response instantly. No processing of the request that is received.
</Working>