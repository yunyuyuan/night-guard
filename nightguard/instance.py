from __future__ import annotations

import hashlib
from pathlib import Path
import time
from PySide6.QtCore import QObject, QLockFile, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class Instance(QObject):
    command = Signal(str)

    def __init__(self, root: Path):
        super().__init__()
        digest = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:24]
        self.name = f"nightguard-{digest}"
        self.lock = QLockFile(str(root / "agent.lock"))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.receive)
        self.sockets = set()
        self.primary = False

    def acquire(self) -> bool:
        self.primary = self.lock.tryLock(0)
        if not self.primary:
            return False
        QLocalServer.removeServer(self.name)  # We hold the process lock.
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError("Could not start local command server")
        return True

    def send(self, command: str) -> bool:
        for _ in range(3):
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(500):
                socket.write((command + "\n").encode("ascii"))
                socket.waitForBytesWritten(500)
                socket.disconnectFromServer()
                return True
            time.sleep(0.1)
        return False

    def receive(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.sockets.add(socket)
            socket.setReadBufferSize(512)
            socket._buffer = b""
            socket.readyRead.connect(lambda s=socket: self.consume(s))
            socket.disconnected.connect(lambda s=socket: self.cleanup(s))
            self.consume(socket)

    def consume(self, socket):
        socket._buffer += bytes(socket.readAll())
        if len(socket._buffer) > 256:
            socket.abort()
            return
        if b"\n" not in socket._buffer:
            return
        command = socket._buffer.split(b"\n", 1)[0].decode("ascii", errors="ignore")
        socket.disconnectFromServer()
        if command in ("settings", "stop", "preview"):
            self.command.emit(command)

    def cleanup(self, socket):
        self.sockets.discard(socket)
        socket.deleteLater()

    def close(self):
        for socket in list(self.sockets):
            socket.abort()
        self.server.close()
        if self.primary:
            self.lock.unlock()
