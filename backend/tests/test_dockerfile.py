from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def test_dockerfile_has_a_healthcheck_hitting_the_health_endpoint():
    # A host with no monitoring of its own (Render/Railway/a bare VPS) relies
    # on Docker's own HEALTHCHECK to know the container is actually serving
    # traffic, not just that the process didn't crash on boot.
    text = DOCKERFILE.read_text(encoding="utf-8")
    start = text.index("HEALTHCHECK")
    # A line-continued (`\`) instruction spans until the next blank line.
    end = text.index("\n\n", start)
    healthcheck_block = text[start:end]
    assert "--interval=30s" in healthcheck_block
    assert "/api/health" in healthcheck_block


def test_healthcheck_is_declared_before_the_final_cmd():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert text.index("HEALTHCHECK") < text.rindex("CMD")
