# Kotak Neo Broker Specific Findings & Technical Quirks

## Overview
This document records technical behaviors, limitations, token lifespans, rate limits, and quirks discovered when integrating Kotak Neo API (`kotakneoapi` / `neo-api-client`).

## Phase 1 Placeholders
- **Authentication Lifecycle**: Kotak Neo uses multi-factor authentication (Access Token, Session Token, OTP/MPIN). Session tokens expire intraday and require proactive refresh cycles before market open (09:15 IST).
- **Rate Limits**: Kotak Neo enforces per-second rate limits on order placement and quotes. Order engine must enforce client-side token bucket throttling.
- **WebSocket Protocol**: Kotak Neo SFeed utilizes binary packet structures for high-speed streaming. Decoupled ingest pipelines will be required in Phase 3.
- **Order Tagging**: Kotak Neo allows client order tags (`tag` / `order_id`). Used for correlating locally generated orders with broker execution callbacks.

