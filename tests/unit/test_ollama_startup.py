from unittest.mock import Mock, patch

import pytest
import requests

from cdm.config import OllamaConfig
from cdm.deployment.ollama import OllamaStartup


def test_running_server_is_reused_and_configured_model_checked() -> None:
    session = Mock(spec=requests.Session)
    session.post.return_value.status_code = 200
    with patch("cdm.deployment.ollama.subprocess.run") as run:
        OllamaStartup(
            OllamaConfig(ollama_model="custom:tag"), session
        ).ensure()
    run.assert_not_called()
    assert session.post.call_args.kwargs["json"] == {"model": "custom:tag"}


def test_stopped_native_service_is_started_and_waited_for() -> None:
    session = Mock(spec=requests.Session)
    session.get.side_effect = [
        requests.ConnectionError(), requests.ConnectionError(), Mock(),
    ]
    session.post.return_value.status_code = 200
    with (
        patch("cdm.deployment.ollama.platform.system", return_value="Darwin"),
        patch("cdm.deployment.ollama.shutil.which", return_value="/opt/homebrew/bin/brew"),
        patch("cdm.deployment.ollama.subprocess.run") as run,
        patch("cdm.deployment.ollama.time.sleep") as sleep,
    ):
        run.return_value.returncode = 0
        OllamaStartup(OllamaConfig(), session).ensure()
    assert run.call_args.args[0] == ["brew", "services", "start", "ollama"]
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("check_only", [True, False])
def test_unreachable_remote_never_starts_local_server(check_only: bool) -> None:
    session = Mock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError()
    with (
        patch("cdm.deployment.ollama.subprocess.run") as run,
        pytest.raises(RuntimeError, match="unreachable"),
    ):
        OllamaStartup(
            OllamaConfig(ollama_url="http://remote.example:11434"), session
        ).ensure(check_only=check_only)
    run.assert_not_called()


def test_missing_model_fails_without_implicit_download() -> None:
    session = Mock(spec=requests.Session)
    session.post.return_value.status_code = 404
    with pytest.raises(RuntimeError, match="ollama pull"):
        OllamaStartup(OllamaConfig(), session).ensure()
    assert session.post.call_count == 1


def test_service_start_failure_is_not_hidden() -> None:
    session = Mock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError()
    with (
        patch("cdm.deployment.ollama.platform.system", return_value="Linux"),
        patch("cdm.deployment.ollama.subprocess.run", side_effect=OSError("no service")),
        pytest.raises(OSError, match="no service"),
    ):
        OllamaStartup(OllamaConfig(), session).ensure()


def test_service_readiness_timeout_fails() -> None:
    session = Mock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError()
    with (
        patch.object(OllamaStartup, "_start"),
        patch("cdm.deployment.ollama.time.monotonic", side_effect=[0, 61]),
        pytest.raises(RuntimeError, match="Timed out"),
    ):
        OllamaStartup(OllamaConfig(), session).ensure()
