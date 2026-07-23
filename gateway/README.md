# HOTIRJAM Gateway

Transport skeleton between venue host and HOTIRJAM AI.

**Hard rules:** no AI imports, no NinjaTrader libraries, no broker APIs, no trading logic, no orders.

Sprint 1 delivers connection lifecycle, envelopes (Identity v2 shape), health, heartbeat/connection manager skeletons, and structured logging.

Sprint 2.1 delivers the transport foundation: TCP server, one active session, NDJSON UTF-8 receive path, and a validation-layer hook (no Tick/DOM/AI parsing).
