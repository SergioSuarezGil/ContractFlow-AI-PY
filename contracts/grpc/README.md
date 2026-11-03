# gRPC

Messages in `contractflow.v1`:

| Service | RPC | Server | Client |
| --- | --- | --- | --- |
| `WorkerHealth` | `Check` | ai-worker `:50052` | contracts-api |
| `ComparisonLookup` | `GetByJobId` | ai-worker `:50052` | `GET /api/v1/jobs/{id}/worker-comparison` |

Python stubs live in `packages/grpc_contractflow` (generated; do not edit `*_pb2.py` by hand).

Enable the server with `AI_WORKER_GRPC_ENABLED=true`. Point the API at it with `AI_WORKER_GRPC_TARGET` (Compose uses `ai-worker:50052`).
