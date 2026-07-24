# Security and Audit Controls

## Upload Validation

Image uploads are read in 1 MB chunks and rejected as soon as the configured byte limit is
exceeded. ThreatLens then checks the PNG, JPEG, or WebP file signature before invoking Pillow,
verifies that the complete image decodes, and enforces a maximum pixel count.

This prevents a declared `Content-Type` from being treated as proof, avoids buffering an
unbounded request, and limits decompression-style resource exhaustion. Defaults are configurable
through `MAX_IMAGE_SIZE_MB` and `MAX_IMAGE_PIXELS`.

## Browser and API Boundaries

- CORS defaults to the two local development origins instead of `*`.
- Allowed methods are limited to `GET`, `POST`, and `OPTIONS`.
- Allowed request headers are limited to content type and request ID.
- Static and proxied responses include CSP, `nosniff`, no-referrer, and frame-denial headers.

Additional origins can be explicitly configured through `CORS_ALLOWED_ORIGINS`.

## Audit Trail

Every request receives a sanitized `X-Request-ID`. The backend writes one structured audit log
line containing request ID, method, path, status, and duration, without logging uploaded image
bytes or architecture JSON.

Every completed analysis also returns:

- `analysisId`.
- `requestId`.
- UTC generation time.
- Pipeline version.
- Human-review state.
- Qualified detector model reference.

These fields remain in JSON exports and allow a demonstrated report to be tied back to its
pipeline execution.

## Verification

Automated tests cover valid image decoding, invalid content rejection, and early stream-size
rejection. The complete suite contains 49 passing tests after these controls.
