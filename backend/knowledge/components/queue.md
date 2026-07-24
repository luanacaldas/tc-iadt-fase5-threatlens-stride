# Message Queue — Threats and Security Controls

## Component Overview

Message queues (SQS, RabbitMQ, Kafka, Azure Service Bus) decouple producers from consumers in asynchronous architectures. They can carry sensitive payloads and, if compromised, enable message injection, replay, or data exfiltration.

## STRIDE Threat Analysis

### Tampering — Message Injection and Replay

**Risk:** Medium | **CWE-345, CWE-294**

Attack patterns:

- Unauthorized producer injecting forged messages into the queue
- Message replay attacks reprocessing the same event multiple times
- Message body manipulation if the queue lacks payload integrity validation

Controls:

- Authenticate all producers with IAM roles, API keys, or client certificates
- Sign message bodies with HMAC or digital signature; verify signature at consumer
- Implement idempotency keys to detect and discard duplicate message processing
- Use sequence numbers or timestamps to detect out-of-order or replayed messages

### Denial of Service — Queue Flooding

**Risk:** Medium | **CWE-400**

Attack patterns:

- Malicious producer flooding the queue with oversized or excessive messages
- Consumer processing failure causing unbounded queue backlog
- Dead-letter queue filling and masking underlying processing errors

Controls:

- Set per-producer message rate limits and maximum message size limits
- Configure dead-letter queues with alerting on any messages entering DLQ
- Implement backpressure mechanisms to signal producers to slow down
- Monitor queue depth, oldest message age, and consumer lag

## Security References

- OWASP Microservices Security Cheat Sheet
- CWE-345: Insufficient Verification of Data Authenticity
