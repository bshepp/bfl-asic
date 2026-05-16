# bfl_asic/ml/models.py
"""PyTorch models for the learnability instrument.

Two models on purpose:
* TinyCNN  -- the headline 2-D conv distinguisher.
* LinearProbe -- logistic regression; a lower bound on detectable
  advantage and the rigor baseline for the "no structure" claim.
"""
from __future__ import annotations

import torch
from torch import nn


class TinyCNN(nn.Module):
    """Small 16x16x1 -> N-class CNN. Deliberately tiny for fast CI."""

    def __init__(self, channels: int = 16, num_classes: int = 2) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class LinearProbe(nn.Module):
    """Flatten 16x16 -> logistic regression (256 -> 2)."""

    def __init__(self) -> None:
        super().__init__()
        self.flatten = nn.Flatten()
        self.linear = nn.Linear(256, 2)  # 256 == 16 * 16 flattened

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(self.flatten(x))


MODELS: dict[str, type[nn.Module]] = {
    "tiny_cnn": TinyCNN,
    "linear_probe": LinearProbe,
}


def build_model(name: str, **kwargs) -> nn.Module:
    """Instantiate a registered model by name."""
    if name not in MODELS:
        raise KeyError(f"unknown model {name!r}; choices: {sorted(MODELS)}")
    return MODELS[name](**kwargs)
