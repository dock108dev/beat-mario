"""Keep shipped project text and ordinary inference on the supported provider."""
import ast
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_application_shares_one_provider_across_game_conversations(tmp_path, monkeypatch):
    from smb3_agent import ai_provider, lab_ui

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAME_COMPANION_USER_DATA", str(tmp_path / "profile"))
    provider = ai_provider.UnavailableProvider("Offline ownership check")
    calls = []

    def factory():
        calls.append(provider)
        return provider

    monkeypatch.setattr(ai_provider, "create_provider", factory)
    server = lab_ui._new_lab_ui_server("127.0.0.1", 0)
    try:
        assert calls == [provider]
        assert server.ai_provider is provider
        assert server.minecraft_chat.provider is provider
        assert server.conversation_service.ai.provider is provider
        assert server.stardew_conversation_service.ai.provider is provider
    finally:
        server.minecraft_chat.close()
        server.conversation_service.close()
        server.stardew_conversation_service.close()
        provider.close()
        server.server_close()


def test_standalone_minecraft_uses_shared_factory_unless_injected(tmp_path, monkeypatch):
    from smb3_agent import ai_provider, minecraft_chat

    provider = ai_provider.UnavailableProvider("Offline ownership check")
    calls = []

    def factory():
        calls.append(provider)
        return provider

    monkeypatch.setattr(minecraft_chat, "create_provider", factory)
    ordinary = minecraft_chat.MinecraftChat(tmp_path / "ordinary")
    injected = minecraft_chat.MinecraftChat(tmp_path / "injected", provider=provider)
    try:
        assert calls == [provider]
        assert ordinary.provider is injected.provider is provider
    finally:
        ordinary.close()
        injected.close()


def retired_reference(name, data):
    # Assemble retired names so the guard itself remains branding-neutral.
    retired = ("co" + "dex", "chat" + "gpt")
    if any(word in name.lower() for word in retired):
        return True
    if b"\0" in data:
        return False
    text = data.decode("utf-8", errors="replace").lower()
    return any(word in text for word in retired)


def test_reference_guard_checks_binary_names_and_mixed_case_text():
    assert retired_reference("Co" + "dex.png", b"\0image")
    assert retired_reference("guide.md", b"CHAT" + b"GPT")
    assert not retired_reference("game.png", b"\0image")
    assert not retired_reference("guide.md", b"Game Companion")


def test_transport_constructor_is_owned_by_provider_factory():
    callers = set()
    for path in (ROOT / "src/smb3_agent").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == "LocalHTTPProvider" for alias in node.names
            ):
                callers.add(path.name)
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", None))
                if name == "LocalHTTPProvider":
                    callers.add(path.name)
    assert callers == {"ai_provider.py"}


def test_project_files_do_not_reference_retired_ai_products():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    matches = []
    for name in result.stdout.decode().split("\0"):
        if not name:
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        if retired_reference(name, path.read_bytes()):
            matches.append(name)
    assert not matches, f"Retired provider references in project files: {matches}"


def test_explicit_falsey_provider_is_not_replaced(tmp_path, monkeypatch):
    from smb3_agent import ai_provider, minecraft_chat

    class FalseyProvider(ai_provider.UnavailableProvider):
        def __bool__(self):
            return False

    provider = FalseyProvider("Explicitly unavailable")

    def unexpected_factory():
        raise AssertionError("An explicit provider must not trigger selection")

    monkeypatch.setattr(minecraft_chat, "create_provider", unexpected_factory)
    service = minecraft_chat.MinecraftChat(tmp_path, provider=provider)
    try:
        assert service.provider is provider
    finally:
        service.close()
