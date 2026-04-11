# WebSocket Events Reference

This document outlines the WebSocket events emitted by the SEVA AI Socket.io backend to connected clients. Frontends should listen for these channels to update state synchronously without polling.

## `new_report`
**Fires when:** A new FieldReport is created from any source (voice, paper, whatsapp, manual intervention).
**Direction**: Server -> Client
**Payload:**
```json
{
  "id": "c1f7b0a8-1234-4567-89ab-cdef01234567",
  "zone_id": "d2f7b0a8-1234-4567-89ab-cdef01234111",
  "extracted_need": "Stagnant drainage causing issues.",
  "source_type": "voice",
  "urgency_level": "medium",
  "bio_markers_detected": ["stagnant_water"],
  "reported_at": "2026-04-05T18:14:53+05:30"
}
```

## `zone_update`
**Fires when:** A zone's biological risk index is mutated successfully and committed.
**Direction**: Server -> Client
**Payload:**
```json
{
   "zone_id": "d2f7b0a8-1234-4567-89ab-cdef01234111",
   "new_bio_risk_index": 3.4,
   "new_risk_level": "amber"
}
```

## `new_alert`
**Fires when:** A zone's biological risk crosses defined thresholds (e.g., > 2.0 or > 5.0), automatically spawning a BioAlert system record.
**Direction**: Server -> Client
**Payload:**
```json
{
   "alert_id": "a3f7b0a8-1234-4567-89ab-cdef01234222",
   "zone_id": "d2f7b0a8-1234-4567-89ab-cdef01234111",
   "alert_type": "Threshold Crossed",
   "severity": "warning",
   "recommended_skills": ["medical", "sanitation"]
}
```

## `volunteer_assigned`
**Fires when:** An assignment connects an active volunteer to a zone or a specific report.
**Direction**: Server -> Client
**Payload:**
```json
{
   "assignment_id": "b4f7b0a8-1234-4567-89ab-cdef01234333",
   "volunteer_id": "v5f7b0a8-1234-4567-89ab-cdef01234555",
   "zone_id": "d2f7b0a8-1234-4567-89ab-cdef01234111",
   "status": "dispatched"
}
```
