from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DW1RNG:
    rng_lb: int = 0
    rng_ub: int = 0

    def __post_init__(self) -> None:
        self.rng_lb &= 0xFF
        self.rng_ub &= 0xFF

    # SOURCE: Bank03.asm UpdateRandNum @ LC55B
    def tick(self) -> int:
        original_ub = self.rng_ub
        original_lb = self.rng_lb

        carry = (self.rng_lb >> 7) & 0x01
        self.rng_lb = (self.rng_lb << 1) & 0xFF
        self.rng_ub = ((self.rng_ub << 1) | carry) & 0xFF

        total = self.rng_lb + original_lb
        self.rng_lb = total & 0xFF
        carry = 1 if total > 0xFF else 0

        total = self.rng_ub + original_ub + carry
        self.rng_ub = total & 0xFF

        self.rng_ub = (self.rng_lb + self.rng_ub) & 0xFF

        total = self.rng_lb + 0x81
        self.rng_lb = total & 0xFF
        carry = 1 if total > 0xFF else 0

        self.rng_ub = (self.rng_ub + carry) & 0xFF
        return self.rng_lb

    # SOURCE: Bank03 call pattern after UpdateRandNum (RandNumUB modulo use)
    def range(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be > 0")
        self.tick()
        return self.rng_ub % n
