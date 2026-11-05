// Kotak Neo Personal Trading Terminal - Phase 1 Foundation
document.addEventListener("DOMContentLoaded", () => {
    const wsStatus = document.getElementById("ws-status");
    const statusLabel = document.getElementById("status-label");

    // Establish WebSocket connection via Socket.IO
    if (typeof io !== "undefined") {
        const socket = io();

        socket.on("connect", () => {
            if (wsStatus) wsStatus.className = "status-indicator online";
            if (statusLabel) statusLabel.textContent = "WS Connected";
        });

        socket.on("disconnect", () => {
            if (wsStatus) wsStatus.className = "status-indicator";
            if (statusLabel) statusLabel.textContent = "WS Disconnected";
        });
    }

    // Health check ping
    fetch("/api/system/health")
        .then(res => res.json())
        .then(data => {
            console.log("System Health:", data);
        })
        .catch(err => {
            console.warn("Health check error:", err);
        });
});

