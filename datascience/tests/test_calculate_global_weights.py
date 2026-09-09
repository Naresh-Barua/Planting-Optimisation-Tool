import pandas as pd

from scripts import calculate_global_weights as cgw


def test_bootstrap_skips_zero_coefficient_model_and_continues(monkeypatch):
    calls = {"count": 0}

    def fake_fit_elastic_net_weights(df, config):
        calls["count"] += 1

        if calls["count"] == 1:
            raise ValueError("Elastic Net importance sum is zero. Coefficients are all null.")

        return pd.Series(
            [0.6, 0.4],
            index=config.env_cols,
            name="elastic_net_weight",
        )

    monkeypatch.setattr(
        cgw,
        "fit_elastic_net_weights",
        fake_fit_elastic_net_weights,
    )

    df = pd.DataFrame(
        {
            "farm_id": [1, 1, 2, 2],
            "env_1": [0.1, 0.2, 0.3, 0.4],
            "env_2": [0.4, 0.3, 0.2, 0.1],
        }
    )

    config = cgw.MCDAConfig(
        env_cols=["env_1", "env_2"],
    )

    boot, early_stop, _ = cgw.bootstrap_global_weights_early_stop(
        df,
        config,
        method="elastic_net",
        max_boot=2,
    )

    assert calls["count"] == 2
    assert len(boot) == 1
    assert early_stop is False
