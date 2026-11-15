import math

from hl.bounds import ell_core, ell_full, gamma_len, log2_choose, radius
from hl.ledger import Ledger


def test_ledger_chain_verifies_and_detects_tampering():
    led = Ledger(n=1000, delta=0.05)
    for i in range(10):
        led.append(1.0, i % 2)
    assert led.verify()
    assert led.bits_in == 10.0
    bits, body, head = led.entries[3]
    led.entries[3] = (bits, body.replace("0", "1") if "0" in body else body + " ", head)
    assert not led.verify()


def test_ledger_bit_total_cannot_be_edited():
    led = Ledger(n=1000, delta=0.05)
    led.append(1.0, 1)
    led.bits_in = 0.0
    assert not led.verify()


def test_gamma_len_is_elias_gamma():
    assert [gamma_len(z) for z in (1, 2, 3, 4, 8)] == [1, 3, 3, 5, 7]


def test_log2_choose():
    assert math.isclose(log2_choose(8, 3), math.log2(56))


def test_core_is_cheaper_than_full():
    assert ell_full(3, 1, 100, 15) > ell_core(3, 100, 15)
    assert ell_full(3, 0, 100, 15) == ell_core(3, 100, 15) + gamma_len(1)


def test_radius_grows_with_bits_and_shrinks_with_n():
    assert radius(100, 20000, 0.05) > radius(10, 20000, 0.05)
    assert radius(100, 80000, 0.05) < radius(100, 20000, 0.05)
    assert radius(0, 20000, 0.05, vhat=0.01) <= radius(0, 20000, 0.05)
