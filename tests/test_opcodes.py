from be6502emu.mpu import MPU
# import pytest


def _write(memory, start_address, bytes):  # NOQA
    # fmt: off
    memory[start_address: start_address + len(bytes)] = bytes
    # fmt: on


def test_brk_preserves_decimal_flag_when_it_is_set():
    mpu = MPU()
    mpu.p = mpu.DECIMAL
    # $C000 BRK
    mpu.memory[0xC000] = 0x00
    mpu.pc = 0xC000
    mpu.step()
    assert mpu.BREAK == mpu.p & mpu.BREAK
    assert mpu.DECIMAL == mpu.p & mpu.DECIMAL


def test_lda_zp_loads_a_sets_n_flag():
    mpu = MPU()
    mpu.a = 0x00
    # $0000 LDA $0010
    _write(mpu.memory, 0x0000, (0xA5, 0x10))
    mpu.memory[0x0010] = 0x80
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x80 == mpu.a
    assert mpu.NEGATIVE == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.ZERO


def test_lda_zp_loads_a_sets_z_flag():
    mpu = MPU()
    mpu.a = 0xFF
    # $0000 LDA $0010
    _write(mpu.memory, 0x0000, (0xA5, 0x10))
    mpu.memory[0x0010] = 0x00
    mpu.step()
    assert 0x0002 == mpu.pc
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


def test_adc_bcd_off_immediate_carry_set_in_accumulator_zero():
    mpu = MPU()
    mpu.a = 0
    mpu.p |= mpu.CARRY
    # $0000 ADC #$00
    _write(mpu.memory, 0x0000, (0x69, 0x00))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x01 == mpu.a
    assert 0 == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.ZERO
    assert mpu.CARRY != mpu.p & mpu.CARRY


def test_adc_bcd_off_immediate_carry_clear_in_no_carry_clear_out():
    mpu = MPU()
    mpu.a = 0x01
    # $0000 ADC #$FE
    _write(mpu.memory, 0x0000, (0x69, 0xFE))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0xFF == mpu.a
    assert mpu.NEGATIVE == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.CARRY
    assert 0 == mpu.p & mpu.ZERO


def test_adc_bcd_off_immediate_carry_clear_in_carry_set_out():
    mpu = MPU()
    mpu.a = 0x02
    # $0000 ADC #$FF
    _write(mpu.memory, 0x0000, (0x69, 0xFF))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x01 == mpu.a
    assert mpu.CARRY == mpu.p & mpu.CARRY
    assert 0 == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.ZERO


def test_adc_bcd_off_immediate_overflow_clr_no_carry_01_plus_01():
    mpu = MPU()
    mpu.p &= ~(mpu.CARRY)
    mpu.a = 0x01
    # $0000 ADC #$01
    _write(mpu.memory, 0x000, (0x69, 0x01))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x02 == mpu.a
    assert 0 == mpu.p & mpu.OVERFLOW


def test_adc_bcd_off_immediate_overflow_clr_no_carry_01_plus_ff():
    mpu = MPU()
    mpu.p &= ~(mpu.CARRY)
    mpu.a = 0x01
    # $0000 ADC #$FF
    _write(mpu.memory, 0x000, (0x69, 0xFF))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x00 == mpu.a
    assert 0 == mpu.p & mpu.OVERFLOW


def test_adc_bcd_off_immediate_overflow_set_no_carry_7f_plus_01():
    mpu = MPU()
    mpu.p &= ~(mpu.CARRY)
    mpu.a = 0x7F
    # $0000 ADC #$01
    _write(mpu.memory, 0x000, (0x69, 0x01))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x80 == mpu.a
    assert mpu.OVERFLOW == mpu.p & mpu.OVERFLOW


def test_adc_bcd_off_immediate_overflow_set_no_carry_80_plus_ff():
    mpu = MPU()
    mpu.p &= ~(mpu.CARRY)
    mpu.a = 0x80
    # $0000 ADC #$FF
    _write(mpu.memory, 0x000, (0x69, 0xFF))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x7F == mpu.a
    assert mpu.OVERFLOW == mpu.p & mpu.OVERFLOW


def test_adc_bcd_off_immediate_overflow_set_on_40_plus_40():
    mpu = MPU()
    mpu.a = 0x40
    # $0000 ADC #$40
    _write(mpu.memory, 0x0000, (0x69, 0x40))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x80 == mpu.a
    assert mpu.NEGATIVE == mpu.p & mpu.NEGATIVE
    assert mpu.OVERFLOW == mpu.p & mpu.OVERFLOW
    assert 0 == mpu.p & mpu.ZERO


def test_adc_bcd_on_immediate_79_plus_00_carry_set():
    mpu = MPU()
    mpu.p |= mpu.DECIMAL
    mpu.p |= mpu.CARRY
    mpu.a = 0x79
    # $0000 ADC #$00
    _write(mpu.memory, 0x0000, (0x69, 0x00))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x80 == mpu.a
    assert mpu.NEGATIVE == mpu.p & mpu.NEGATIVE
    assert mpu.OVERFLOW == mpu.p & mpu.OVERFLOW
    assert 0 == mpu.p & mpu.ZERO
    assert 0 == mpu.p & mpu.CARRY


def test_adc_bcd_on_immediate_6f_plus_00_carry_set():
    mpu = MPU()
    mpu.p |= mpu.DECIMAL
    mpu.p |= mpu.CARRY
    mpu.a = 0x6F
    # $0000 ADC #$00
    _write(mpu.memory, 0x0000, (0x69, 0x00))
    mpu.step()
    assert 0x0002 == mpu.pc
    assert 0x76 == mpu.a
    assert 0 == mpu.p & mpu.NEGATIVE
    assert 0 == mpu.p & mpu.OVERFLOW
    assert 0 == mpu.p & mpu.ZERO
    assert 0 == mpu.p & mpu.CARRY


def test_adc_bcd_on_immediate_9c_plus_9d():
    mpu = MPU()
    mpu.p |= mpu.DECIMAL
    mpu.p &= ~(mpu.CARRY)
    mpu.a = 0x9C
    # $0000 ADC #$9d
    # $0002 ADC #$9d
    _write(mpu.memory, 0x0000, (0x69, 0x9D))
    _write(mpu.memory, 0x0002, (0x69, 0x9D))
    mpu.step()
    assert 0x9F == mpu.a
    assert mpu.CARRY == mpu.p & mpu.CARRY
    mpu.step()
    assert 0x0004 == mpu.pc
    assert 0x93 == mpu.a
    assert 0 == mpu.p & mpu.NEGATIVE
    assert mpu.OVERFLOW == mpu.p & mpu.OVERFLOW
    assert 0 == mpu.p & mpu.ZERO
    assert mpu.CARRY == mpu.p & mpu.CARRY
