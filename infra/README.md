# Infrastructure boundary

Phase 1 runs locally. No cloud project, credential, bucket or deployed service is provisioned. Future deployment must route the Flutter app and `/api/v1` behind the same HTTPS origin and run API/database with restricted runtime credentials.
