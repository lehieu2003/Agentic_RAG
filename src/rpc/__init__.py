"""gRPC RPC service module for decoupled retrieval service."""

import sys
from pathlib import Path

# Ensure generated protobuf stubs can import each other
_rpc_dir = str(Path(__file__).parent.resolve())
if _rpc_dir not in sys.path:
    sys.path.insert(0, _rpc_dir)

from src.rpc import retrieval_pb2, retrieval_pb2_grpc

__all__ = ["retrieval_pb2", "retrieval_pb2_grpc"]

