import os
import yaml
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

@pytest.fixture(scope="module")
def compose_data():
    compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")
    assert os.path.exists(compose_path), "docker-compose.yml must exist at root"
    with open(compose_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data is not None, "docker-compose.yml must not be empty"
    return data


class TestDockerComposeConfig:
    """Validates the root docker-compose.yml configuration."""

    def test_required_services_present(self, compose_data):
        services = compose_data.get("services", {})
        required = {"postgres", "redis", "backend-main", "ml-service", "genai-service"}
        assert required.issubset(services.keys()), f"Missing services in compose: {required - services.keys()}"

    def test_port_mappings_correct(self, compose_data):
        services = compose_data.get("services", {})
        expected_ports = {
            "postgres": "5432:5432",
            "redis": "6379:6379",
            "backend-main": "8000:8000",
            "ml-service": "8001:8001",
            "genai-service": "8002:8002"
        }
        for svc_name, port_mapping in expected_ports.items():
            ports = services[svc_name].get("ports", [])
            assert port_mapping in ports, f"Service {svc_name} missing port {port_mapping}"

    def test_healthchecks_configured(self, compose_data):
        services = compose_data.get("services", {})
        assert "healthcheck" in services["postgres"], "Postgres must have a healthcheck"
        assert "healthcheck" in services["redis"], "Redis must have a healthcheck"

    def test_backend_depends_on_healthy_dbs(self, compose_data):
        services = compose_data.get("services", {})
        depends_on = services["backend-main"].get("depends_on", {})
        assert "postgres" in depends_on, "Backend must depend on postgres"
        assert "redis" in depends_on, "Backend must depend on redis"
        assert depends_on["postgres"]["condition"] == "service_healthy"
        assert depends_on["redis"]["condition"] == "service_healthy"

    def test_shared_network_and_volumes(self, compose_data):
        networks = compose_data.get("networks", {})
        assert "academiq-network" in networks

        volumes = compose_data.get("volumes", {})
        assert "postgres_data" in volumes
        assert "redis_data" in volumes


class TestDockerfilesIntegrity:
    """Validates Dockerfile presence, base images, exposed ports, and healthchecks."""

    @pytest.mark.parametrize("service_name,expected_port", [
        ("backend-main", 8000),
        ("ml-service", 8001),
        ("genai-service", 8002),
    ])
    def test_dockerfile_structure(self, service_name, expected_port):
        df_path = os.path.join(ROOT_DIR, service_name, "Dockerfile")
        assert os.path.exists(df_path), f"Dockerfile missing for {service_name}"
        with open(df_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "FROM python:3.11-slim" in content, f"{service_name} must use python:3.11-slim"
        assert f"EXPOSE {expected_port}" in content, f"{service_name} must expose port {expected_port}"
        assert "HEALTHCHECK" in content, f"{service_name} must include a HEALTHCHECK directive"

    def test_ml_service_includes_opencv_system_libs(self):
        ml_df_path = os.path.join(ROOT_DIR, "ml-service", "Dockerfile")
        with open(ml_df_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "libgl1" in content, "ML service Dockerfile must install libgl1 for OpenCV"
        assert "libglib2.0-0" in content, "ML service Dockerfile must install libglib2.0-0 for OpenCV"
