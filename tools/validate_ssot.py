#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SSOT_PATH = ROOT / "docs" / "service-endpoints-ssot.md"
COMPOSE_PATH = ROOT / "docker-compose.yml"
K8S_SERVICES_PATH = ROOT / "k8s" / "services.yaml"


SERVICE_NAME_MAP = {
    "Vision": {"compose": "vision-svc", "k8s": "vision-service"},
    "Weaver": {"compose": "weaver-svc", "k8s": "weaver-service"},
    "Canvas": {"compose": "canvas-ui", "k8s": "canvas-service"},
    "Redis Bus": {"compose": "redis-bus", "k8s": "redis-bus-service"},
}


def parse_ssot_runtime_active_table(text: str) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    in_runtime_active = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## 1. 현재 배포 프로파일"):
            in_runtime_active = True
            continue
        if in_runtime_active and line.startswith("## "):
            break
        if not in_runtime_active:
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cols = [x.strip() for x in line.strip("|").split("|")]
        if len(cols) < 4 or cols[0] == "서비스":
            continue
        service = cols[0]
        try:
            container_port = int(cols[1])
            host_port = int(cols[2])
        except ValueError:
            continue
        rows[service] = {"container_port": container_port, "host_port": host_port}
    return rows


def parse_compose_ports(text: str) -> dict[str, dict[str, int]]:
    services: dict[str, dict[str, int]] = {}
    lines = text.splitlines()
    in_services = False
    current_service: str | None = None
    in_ports = False
    service_indent = 0
    ports_indent = 0

    for raw in lines:
        if not in_services and raw.strip() == "services:":
            in_services = True
            continue
        if not in_services:
            continue
        if raw.strip() == "":
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        service_match = re.match(r"^([A-Za-z0-9_-]+):\s*$", line)
        if service_match and indent <= 2:
            current_service = service_match.group(1)
            service_indent = indent
            in_ports = False
            continue

        if current_service is None:
            continue
        if indent <= service_indent and line.endswith(":"):
            current_service = None
            in_ports = False
            continue
        if line == "ports:":
            in_ports = True
            ports_indent = indent
            continue
        if in_ports:
            if indent <= ports_indent:
                in_ports = False
                continue
            port_match = re.search(r'"?(\d+):(\d+)"?', line)
            if port_match:
                services[current_service] = {
                    "host_port": int(port_match.group(1)),
                    "container_port": int(port_match.group(2)),
                }
    return services


def parse_k8s_service_ports(text: str) -> dict[str, int]:
    services: dict[str, int] = {}
    blocks = [b.strip() for b in text.split("---") if b.strip()]
    for block in blocks:
        name_match = re.search(r"metadata:\s*\n\s*name:\s*([A-Za-z0-9_-]+)", block)
        port_match = re.search(r"\n\s*port:\s*(\d+)", block)
        if name_match and port_match:
            services[name_match.group(1)] = int(port_match.group(1))
    return services


def main() -> int:
    ssot = parse_ssot_runtime_active_table(SSOT_PATH.read_text(encoding="utf-8"))
    compose = parse_compose_ports(COMPOSE_PATH.read_text(encoding="utf-8"))
    k8s = parse_k8s_service_ports(K8S_SERVICES_PATH.read_text(encoding="utf-8"))

    failures: list[str] = []
    for service_name, ports in ssot.items():
        mapping = SERVICE_NAME_MAP.get(service_name)
        if not mapping:
            failures.append(f"[SSOT] unknown service mapping: {service_name}")
            continue
        compose_name = mapping["compose"]
        k8s_name = mapping["k8s"]

        compose_ports = compose.get(compose_name)
        if not compose_ports:
            failures.append(f"[compose] missing service: {compose_name} (for {service_name})")
        else:
            if compose_ports["host_port"] != ports["host_port"]:
                failures.append(
                    f"[compose] host port mismatch for {service_name}: ssot={ports['host_port']} compose={compose_ports['host_port']}"
                )
            if compose_ports["container_port"] != ports["container_port"]:
                failures.append(
                    f"[compose] container port mismatch for {service_name}: ssot={ports['container_port']} compose={compose_ports['container_port']}"
                )

        k8s_port = k8s.get(k8s_name)
        if k8s_port is None:
            failures.append(f"[k8s] missing service: {k8s_name} (for {service_name})")
        elif k8s_port != ports["container_port"]:
            failures.append(
                f"[k8s] service port mismatch for {service_name}: ssot_container={ports['container_port']} k8s={k8s_port}"
            )

    if failures:
        print("SSOT validation failed:")
        for f in failures:
            print(f"- {f}")
        return 1

    print("SSOT validation passed for Runtime-Active profile.")
    for service_name, ports in ssot.items():
        print(f"- {service_name}: host={ports['host_port']} container={ports['container_port']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
