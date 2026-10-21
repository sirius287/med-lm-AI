import importlib.util
from pathlib import Path


def scanner():
    source = Path(__file__).resolve().parents[3] / "scripts/check_repository.py"
    spec = importlib.util.spec_from_file_location("release_scanner", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scanner_does_not_exempt_credentials_just_because_they_are_in_tests():
    subject = scanner()
    # Constructed synthetic literals, not credentials for a running account.
    value = b"postgresql+psycopg://runtime:" + b"not-a-real-password" + b"@127.0.0.1/db"
    result = subject.inspect("services/api/tests/example.py", value)
    assert result == [("services/api/tests/example.py", "credential_url")]
    assert value.decode() not in repr(result)


def test_scanner_keeps_only_explicit_noncredential_examples_exempt():
    subject = scanner()
    assert (
        subject.inspect("SETUP_WINDOWS.md", b"postgresql://owner:URL_ENCODED_PASSWORD@localhost/db")
        == []
    )
    assert (
        subject.inspect(
            "services/api/tests/example.py", b"postgresql://runtime:synthetic@db.invalid/db"
        )
        == []
    )
    assert subject.inspect("README.md", b"postgresql://runtime:synthetic@db.invalid/db")


def test_scanner_returns_rule_and_path_never_the_matched_secret():
    subject = scanner()
    value = b"sk-proj-" + b"A" * 40
    assert subject.inspect("example.py", value) == [("example.py", "provider_secret")]
    assert value.decode() not in repr(subject.inspect("example.py", value))
