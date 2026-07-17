"""Shared Docker lifecycle for isolated provider contract tests.

The fixtures deliberately use container-to-container DNS names.  This keeps
the tests independent of host port allocation and makes the same test code
work on Docker Desktop and Linux CI runners.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pytest
import docker
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

ROOT = Path(__file__).parents[2]
SUT_IMAGE = os.getenv("CONTRACT_SUT_IMAGE", "arazzo-contract-sut:local")
SPECMATIC_IMAGE = os.getenv("SPECMATIC_ENTERPRISE_IMAGE", "specmatic/enterprise:1.20.1")


@dataclass
class ProviderEnvironment:
    name: str
    sut_service: str
    sut_port: int
    needs_kafka: bool = False
    dependency_mock: str | None = None
    network: Network | None = None
    containers: list[DockerContainer] = field(default_factory=list)

    def start(self) -> "ProviderEnvironment":
        self._start_network()
        self._start_postgres()
        if self.needs_kafka:
            self._start_kafka()

        self._run_database_command("database-init", "python scripts/db_init.py")
        if self.sut_service in {"order", "warehouse"}:
            self._run_database_command(
                "order-contract-seed",
                "python /usr/src/app/tests/contracts/order/seed.py",
                mount_source=True,
            )
        self._start_sut(self.sut_service, self.sut_port)
        if self.needs_kafka:
            time.sleep(2)
        return self

    def run_contract(self) -> None:
        self._run_specmatic("run-suite")

    def _run_specmatic(self, command: str) -> None:
        specmatic = (
            DockerContainer(SPECMATIC_IMAGE)
            .with_network(self.network)
            .with_volume_mapping(str(ROOT), "/usr/src/app", mode="rw")
            .with_kwargs(working_dir=f"/usr/src/app/tests/contracts/{self.name}")
            .with_command(command)
        )

        if self.dependency_mock:
            specmatic.with_network_aliases(self.dependency_mock)
        if self.needs_kafka:
            specmatic.with_env("KAFKA_BROKER", "kafka:9092")

        specmatic.start()
        self.containers.append(specmatic)
        result = specmatic.get_wrapped_container().wait()
        logs = self._logs(specmatic)
        self._copy_reports()
        if result.get("StatusCode", 1) != 0:
            raise AssertionError(f"{self.name} Specmatic run failed:\n{logs}")

    def close(self) -> None:
        for container in reversed(self.containers):
            try:
                container.stop()
            except Exception:
                pass
        if self.network and self.network._network is not None:
            self.network.remove()

    def _start_network(self) -> None:
        self.network = Network()
        self.network.create()

    def _start_postgres(self) -> None:
        postgres = (
            PostgresContainer("postgres:15-alpine", username="user", password="password", dbname="shared_db")
            .with_network(self.network)
            .with_network_aliases("postgres")
        )
        postgres.start()
        self.containers.append(postgres)

    def _start_kafka(self) -> None:
        kafka = (
            KafkaContainer("confluentinc/cp-kafka:7.6.0")
            .with_network(self.network)
            .with_network_aliases("kafka")
        )
        kafka.start()
        self.containers.append(kafka)
        for topic in ("new-orders", "wip-orders", "accepted-orders", "out-for-delivery-orders"):
            result = kafka.exec(
                [
                    "kafka-topics",
                    "--create",
                    "--if-not-exists",
                    "--topic",
                    topic,
                    "--bootstrap-server",
                    "localhost:9092",
                ]
            )
            if result.exit_code != 0:
                raise RuntimeError(f"Failed to create Kafka topic {topic}: {result.output.decode(errors='replace')}")

    def _start_sut(self, service: str, port: int) -> None:
        sut_env = {"PORT": str(port)}
        if service == "warehouse":
            sut_env["ORDER_SERVICE_PORT"] = "3002"
        if service == "order":
            sut_env["KAFKA_BOOTSTRAP_SERVERS"] = "kafka:9092"

        sut = self._sut(service, service, sut_env).with_exposed_ports(port)
        sut.start()
        self.containers.append(sut)
        self._wait_for_http(sut, port)
        if service == "order":
            self._wait_for_order_consumers(sut)

    def _run_database_command(self, name: str, command: str, *, mount_source: bool = False) -> None:
        database_command = self._sut(name, "database", {}, command=command)
        if mount_source:
            database_command.with_volume_mapping(str(ROOT), "/usr/src/app", mode="ro")
            database_command.with_env("PYTHONPATH", "/app:/usr/src/app")
        database_command.start()
        result = database_command.get_wrapped_container().wait()
        logs = self._logs(database_command)
        database_command.stop()
        if result.get("StatusCode", 1) != 0:
            raise RuntimeError(f"Database command failed ({command}):\n{logs}")

    @staticmethod
    def _logs(container: DockerContainer) -> str:
        stdout, stderr = container.get_logs()
        return (stdout + stderr).decode(errors="replace")

    def _sut(
        self,
        name: str,
        service: str,
        extra_env: dict[str, str],
        *,
        command: str | None = None,
    ) -> DockerContainer:
        env = {
            "DATABASE_URL": "postgresql://user:password@postgres:5432/shared_db",
            **extra_env,
        }
        return (
            DockerContainer(SUT_IMAGE)
            .with_name(f"contract-{self.name}-{name}")
            .with_network(self.network)
            .with_network_aliases(service)
            .with_envs(**env)
            .with_command(command or "sh -c 'fastapi run --host 0.0.0.0 --port ${PORT:-3000} services/$SERVICE_NAME'")
            .with_env("SERVICE_NAME", service)
        )

    def _wait_for_http(self, container: DockerContainer, port: int, *, path: str = "/docs") -> None:
        host = container.get_container_host_ip()
        published = container.get_exposed_port(port)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"http://{host}:{published}{path}", timeout=1)
                return
            except urllib.error.HTTPError:
                return
            except (OSError, urllib.error.URLError):
                time.sleep(0.5)
        raise TimeoutError(f"{self.name} SUT did not become ready:\n{self._logs(container)}")

    def _wait_for_order_consumers(self, container: DockerContainer) -> None:
        expected = ("Started consuming from new-orders", "Started consuming from out-for-delivery-orders")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            logs = self._logs(container)
            if all(marker in logs for marker in expected):
                return
            time.sleep(0.5)
        raise TimeoutError(f"{self.name} Order consumers did not become ready:\n{self._logs(container)}")

    def _copy_reports(self) -> None:
        output = ROOT / "build" / "reports" / "specmatic" / self.name
        source = ROOT / "tests" / "contracts" / self.name / "build" / "reports" / "specmatic"
        if not source.exists():
            return
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(source, output)


@pytest.fixture
def provider_environment(request: pytest.FixtureRequest) -> Iterator[ProviderEnvironment]:
    environment = request.param
    try:
        environment.start()
        yield environment
    finally:
        environment.close()


@pytest.fixture(scope="session", autouse=True)
def contract_sut_image() -> Iterator[None]:
    """Build the application image once; each provider still gets fresh containers."""
    client = docker.from_env()
    if os.getenv("CONTRACT_SUT_IMAGE"):
        try:
            client.images.get(SUT_IMAGE)
        except docker.errors.ImageNotFound as error:
            raise pytest.UsageError(f"CONTRACT_SUT_IMAGE={SUT_IMAGE!r} was not found; build it before running contract tests") from error
        yield
        return
    try:
        build = subprocess.run(
            ["docker", "buildx", "build", "--load", "--tag", SUT_IMAGE, str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise pytest.UsageError("Docker CLI with buildx is required to build the contract-test SUT image") from error
    if build.returncode != 0:
        output = (build.stdout + build.stderr).strip()
        raise RuntimeError(f"Failed to build {SUT_IMAGE!r} with Docker Buildx:\n{output}")
    yield
