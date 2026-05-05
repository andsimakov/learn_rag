import numpy as np
import pytest

from app.core.embedder import warm_up


def _mock_embedder(mocker, dim: int):
    mock_model = mocker.MagicMock()
    mock_model.encode.return_value = np.zeros(dim)
    mocker.patch("app.core.embedder._load_model", return_value=mock_model)

    mock_settings = mocker.MagicMock()
    mock_settings.embedding_dim = 384
    mock_settings.embedding_model = "all-MiniLM-L6-v2"
    mocker.patch("app.core.embedder.get_settings", return_value=mock_settings)


def test_warm_up_passes_with_correct_dim(mocker):
    _mock_embedder(mocker, dim=384)
    warm_up()  # should not raise


def test_warm_up_raises_on_wrong_dim(mocker):
    _mock_embedder(mocker, dim=768)
    with pytest.raises(ValueError, match="768"):
        warm_up()
