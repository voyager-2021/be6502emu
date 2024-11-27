from be6502emu.mpu import MPU
import pytest


def _write(memory, start_address, bytes): # NOQA
    memory[start_address:start_address + len(bytes)] = bytes


def test_brk_clears_decimal_flag():
    mpu = MPU()
    mpu.p = mpu.DECIMAL
    mpu.memory[0xC000] = 0x00
    mpu.pc = 0xC000
    mpu.step()
    assert mpu.BREAK == mpu.p & mpu.BREAK
    assert 0 == mpu.p & mpu.DECIMAL


@pytest.mark.xfail
def test_lda_zp_ind_loads_a_sets_n_flag():
    mpu = MPU()
    mpu.a = 0x00
    # $0000 LDA ($0010)
    # $0010 Vector to $ABCD
    _write(mpu.memory, 0x0000, (0xB2, 0x10))
    _write(mpu.memory, 0x0010, (0xCD, 0xAB))
    mpu.memory[0xABCD] = 0x80
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 5 == mpu.processorCycles
    assert 0x80 == mpu.a
    assert mpu.NEGATIVE == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.ZERO


@pytest.mark.xfail
def test_lda_zp_ind_loads_a_sets_z_flag():
    mpu = MPU()
    mpu.a = 0x00
    # $0000 LDA ($0010)
    # $0010 Vector to $ABCD
    _write(mpu.memory, 0x0000, (0xB2, 0x10))
    _write(mpu.memory, 0x0010, (0xCD, 0xAB))
    mpu.memory[0xABCD] = 0x00
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 5 == mpu.processorCycles
    assert 0x00 == mpu.a
    assert mpu.ZERO == mpu.p & mpu.ZERO
    assert 0 == mpu.p & mpu.NEGATIVE


def test_lda_immediate_loads_a_sets_n_flag():
    mpu = MPU()
    mpu.a = 0x00
    # $0000 LDA #$80
    _write(mpu.memory, 0x0000, (0xA9, 0x80))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x80 == mpu.a
    assert mpu.NEGATIVE == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.ZERO


def test_lda_immediate_loads_a_sets_z_flag():
    mpu = MPU()
    mpu.a = 0xFF
    # $0000 LDA #$00
    _write(mpu.memory, 0x0000, (0xA9, 0x00))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x00 == mpu.a
    assert mpu.ZERO == mpu.p & mpu.ZERO
    assert 0 == mpu.p & mpu.NEGATIVE

@pytest.mark.xfail
def test_adc_bcd_off_immediate_carry_clear_in_accumulator_zeroes():
    mpu = MPU()
    mpu.a = 0
    # $0000 ADC #$00
    _write(mpu.memory, 0x0000, (0x69, 0x00))
    mpu.step()
    assert 0x0002, mpu.pc
    assert 0x00 == mpu.a
    assert 0 == mpu.p & mpu.CARRY
    assert 0 == mpu.p & mpu.NEGATIVE
    assert mpu.ZERO == mpu.p & mpu.ZERO
