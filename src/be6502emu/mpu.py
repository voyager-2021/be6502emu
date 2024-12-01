from py65.utils.conversions import itoa


def make_instruction_decorator(instruct, disasm, allcycles, allextras):
    def instruction(name, mode, cycles, extracycles=0):
        def decorate(f):
            opcode = int(f.__name__.split("_")[-1], 16)
            instruct[opcode] = f
            disasm[opcode] = (name, mode)
            allcycles[opcode] = cycles
            allextras[opcode] = extracycles
            return f  # Return the original function

        return decorate

    return instruction


class MPU:
    RESET = 0xFFFC
    NMI = 0xFFFA
    IRQ = 0xFFFE

    # processor flags
    NEGATIVE = 128
    OVERFLOW = 64
    UNUSED = 32
    BREAK = 16
    DECIMAL = 8
    INTERRUPT = 4
    ZERO = 2
    CARRY = 1

    BYTE_WIDTH = 8
    BYTE_FORMAT = "%02x"
    ADDR_WIDTH = 16
    ADDR_FORMAT = "%04x"

    def __init__(self, memory=None, pc=0x0000):
        # config
        self.name = "65C02"
        self.byteMask = (1 << self.BYTE_WIDTH) - 1
        self.addrMask = (1 << self.ADDR_WIDTH) - 1
        self.addrHighMask = self.byteMask << self.BYTE_WIDTH
        self.spBase = 1 << self.BYTE_WIDTH

        # vm status
        self.excycles = 0
        self.addcycles = False
        self.processorCycles = 0

        if memory is None:
            memory = 0x10000 * [0x00]
        self.memory = memory
        self.start_pc = pc  # if None, reset vector is used

        # registers
        self.pc = self.start_pc
        if self.pc is None:
            self.pc = self.WordAt(self.RESET)
        self.sp = self.byteMask
        self.a = 0
        self.x = 0
        self.y = 0
        self.p = self.BREAK | self.UNUSED
        self.processorCycles = 0

        # init
        self.waiting = False

    @staticmethod
    def reprformat():
        # fmt: off
        return "%s PC  AC XR YR SP NV-BDIZC\n" \
               "%s: %04x %02x %02x %02x %02x %s"
        # fmt: on

    def __repr__(self):
        flags = itoa(self.p, 2).rjust(self.BYTE_WIDTH, "0")
        indent = " " * (len(self.name) + 2)

        return self.reprformat() % (
            indent,
            self.name,
            self.pc,
            self.a,
            self.x,
            self.y,
            self.sp,
            flags,
        )

    def _step(self):
        instruct_code = self.memory[self.pc]
        self.pc = (self.pc + 1) & self.addrMask
        self.excycles = 0
        self.addcycles = self.extracycles[instruct_code]
        self.instruct[instruct_code](self)  # NOQA
        self.pc &= self.addrMask
        self.processorCycles += self.cycletime[instruct_code] + self.excycles
        return self

    def step(self):
        if self.waiting:
            self.processorCycles += 1
        else:
            self._step()
        return self

    def reset(self):
        self.pc = self.start_pc
        if self.pc is None:
            self.pc = self.WordAt(self.RESET)
        self.sp = self.byteMask
        self.a = 0
        self.x = 0
        self.y = 0
        self.p = self.BREAK | self.UNUSED
        self.processorCycles = 0

    def irq(self):
        # triggers a normal IRQ
        # this is very similar to the BRK instruction
        if self.p & self.INTERRUPT:
            return
        self.stPushWord(self.pc)
        self.p &= ~self.BREAK
        self.stPush(self.p | self.UNUSED)
        self.p |= self.INTERRUPT
        self.pc = self.WordAt(self.IRQ)
        self.processorCycles += 7

    def nmi(self):
        # triggers a NMI IRQ in the processor
        # this is very similar to the BRK instruction
        self.stPushWord(self.pc)
        self.p &= ~self.BREAK
        self.stPush(self.p | self.UNUSED)
        self.p |= self.INTERRUPT
        self.pc = self.WordAt(self.NMI)
        self.processorCycles += 7

    # Helpers for addressing modes

    def ByteAt(self, addr):
        return self.memory[addr]

    def WordAt(self, addr):
        return self.ByteAt(addr) + (self.ByteAt(addr + 1) << self.BYTE_WIDTH)

    def WrapAt(self, addr):
        wrap = lambda x: (x & self.addrHighMask) + ((x + 1) & self.byteMask)  # NOQA
        return self.ByteAt(addr) + (self.ByteAt(wrap(addr)) << self.BYTE_WIDTH)

    def ProgramCounter(self):
        return self.pc

    # Addressing modes

    def ImmediateByte(self):
        return self.ByteAt(self.pc)

    def ZeroPageAddr(self):
        return self.ByteAt(self.pc)

    def ZeroPageXAddr(self):
        return self.byteMask & (self.x + self.ByteAt(self.pc))

    def ZeroPageYAddr(self):
        return self.byteMask & (self.y + self.ByteAt(self.pc))

    def IndirectXAddr(self):
        return self.WrapAt(self.byteMask & (self.ByteAt(self.pc) + self.x))

    def IndirectYAddr(self):
        if self.addcycles:
            a1 = self.WrapAt(self.ByteAt(self.pc))
            a2 = (a1 + self.y) & self.addrMask
            if (a1 & self.addrHighMask) != (a2 & self.addrHighMask):
                self.excycles += 1
            return a2
        else:
            return (self.WrapAt(self.ByteAt(self.pc)) + self.y) & self.addrMask

    def AbsoluteAddr(self):
        return self.WordAt(self.pc)

    def AbsoluteXAddr(self):
        if self.addcycles:
            a1 = self.WordAt(self.pc)
            a2 = (a1 + self.x) & self.addrMask
            if (a1 & self.addrHighMask) != (a2 & self.addrHighMask):
                self.excycles += 1
            return a2
        else:
            return (self.WordAt(self.pc) + self.x) & self.addrMask

    def AbsoluteYAddr(self):
        if self.addcycles:
            a1 = self.WordAt(self.pc)
            a2 = (a1 + self.y) & self.addrMask
            if (a1 & self.addrHighMask) != (a2 & self.addrHighMask):
                self.excycles += 1
            return a2
        else:
            return (self.WordAt(self.pc) + self.y) & self.addrMask

    def BranchRelAddr(self):
        self.excycles += 1
        addr = self.ImmediateByte()
        self.pc += 1

        if addr & self.NEGATIVE:
            addr = self.pc - (addr ^ self.byteMask) - 1
        else:
            addr = self.pc + addr

        if (self.pc & self.addrHighMask) != (addr & self.addrHighMask):
            self.excycles += 1

        self.pc = addr & self.addrMask

    def ZeroPageIndirectAddr(self):
        return self.WordAt(255 & (self.ByteAt(self.pc)))

    def IndirectAbsXAddr(self):
        return (self.WordAt(self.pc) + self.x) & self.addrMask

    # stack

    def stPush(self, z):
        self.memory[self.sp + self.spBase] = z & self.byteMask
        self.sp -= 1
        self.sp &= self.byteMask

    def stPop(self):
        self.sp += 1
        self.sp &= self.byteMask
        return self.ByteAt(self.sp + self.spBase)

    def stPushWord(self, z):
        self.stPush((z >> self.BYTE_WIDTH) & self.byteMask)
        self.stPush(z & self.byteMask)

    def stPopWord(self):
        z = self.stPop()
        z += self.stPop() << self.BYTE_WIDTH
        return z

    def FlagsNZ(self, value):
        self.p &= ~(self.ZERO | self.NEGATIVE)
        if value == 0:
            self.p |= self.ZERO
        else:
            self.p |= value & self.NEGATIVE

    # operations

    def opORA(self, x):
        self.a |= self.ByteAt(x())
        self.FlagsNZ(self.a)

    def opASL(self, x):
        if x is None:
            tbyte = self.a
        else:
            addr = x()
            tbyte = self.ByteAt(addr)

        self.p &= ~(self.CARRY | self.NEGATIVE | self.ZERO)

        if tbyte & self.NEGATIVE:
            self.p |= self.CARRY
        tbyte = (tbyte << 1) & self.byteMask

        if tbyte:
            self.p |= tbyte & self.NEGATIVE
        else:
            self.p |= self.ZERO

        if x is None:
            self.a = tbyte
        else:
            self.memory[addr] = tbyte  # NOQA

    def opLSR(self, x):
        if x is None:
            tbyte = self.a
        else:
            addr = x()
            tbyte = self.ByteAt(addr)

        self.p &= ~(self.CARRY | self.NEGATIVE | self.ZERO)
        self.p |= tbyte & 1

        tbyte >>= 1
        if tbyte:
            pass
        else:
            self.p |= self.ZERO

        if x is None:
            self.a = tbyte
        else:
            self.memory[addr] = tbyte  # NOQA

    def opBCL(self, x):
        if self.p & x:
            self.pc += 1
        else:
            self.BranchRelAddr()

    def opBST(self, x):
        if self.p & x:
            self.BranchRelAddr()
        else:
            self.pc += 1

    def opCLR(self, x):
        self.p &= ~x

    def opSET(self, x):
        self.p |= x

    def opAND(self, x):
        self.a &= self.ByteAt(x())
        self.FlagsNZ(self.a)

    def opBIT(self, x):
        tbyte = self.ByteAt(x())
        self.p &= ~(self.ZERO | self.NEGATIVE | self.OVERFLOW)
        if (self.a & tbyte) == 0:
            self.p |= self.ZERO
        self.p |= tbyte & (self.NEGATIVE | self.OVERFLOW)

    def opROL(self, x):
        if x is None:
            tbyte = self.a
        else:
            addr = x()
            tbyte = self.ByteAt(addr)

        if self.p & self.CARRY:
            if tbyte & self.NEGATIVE:
                pass
            else:
                self.p &= ~self.CARRY
            tbyte = (tbyte << 1) | 1
        else:
            if tbyte & self.NEGATIVE:
                self.p |= self.CARRY
            tbyte <<= 1
        tbyte &= self.byteMask
        self.FlagsNZ(tbyte)

        if x is None:
            self.a = tbyte
        else:
            self.memory[addr] = tbyte  # NOQA

    def opEOR(self, x):
        self.a ^= self.ByteAt(x())
        self.FlagsNZ(self.a)

    def opADC(self, x):
        data = self.ByteAt(x())

        if self.p & self.DECIMAL:
            halfcarry = 0
            decimalcarry = 0
            adjust0 = 0
            adjust1 = 0
            nibble0 = (data & 0xF) + (self.a & 0xF) + (self.p & self.CARRY)
            if nibble0 > 9:
                adjust0 = 6
                halfcarry = 1
            nibble1 = ((data >> 4) & 0xF) + ((self.a >> 4) & 0xF) + halfcarry
            if nibble1 > 9:
                adjust1 = 6
                decimalcarry = 1

            # the ALU outputs are not decimally adjusted
            nibble0 &= 0xF
            nibble1 &= 0xF
            aluresult = (nibble1 << 4) + nibble0

            # the final A contents will be decimally adjusted
            nibble0 = (nibble0 + adjust0) & 0xF
            nibble1 = (nibble1 + adjust1) & 0xF
            self.p &= ~(self.CARRY | self.OVERFLOW | self.NEGATIVE | self.ZERO)
            if aluresult == 0:
                self.p |= self.ZERO
            else:
                self.p |= aluresult & self.NEGATIVE
            if decimalcarry == 1:
                self.p |= self.CARRY
            if (~(self.a ^ data) & (self.a ^ aluresult)) & self.NEGATIVE:
                self.p |= self.OVERFLOW
            self.a = (nibble1 << 4) + nibble0
        else:
            if self.p & self.CARRY:
                tmp = 1
            else:
                tmp = 0
            result = data + self.a + tmp
            self.p &= ~(self.CARRY | self.OVERFLOW | self.NEGATIVE | self.ZERO)
            if (~(self.a ^ data) & (self.a ^ result)) & self.NEGATIVE:
                self.p |= self.OVERFLOW
            data = result
            if data > self.byteMask:
                self.p |= self.CARRY
                data &= self.byteMask
            if data == 0:
                self.p |= self.ZERO
            else:
                self.p |= data & self.NEGATIVE
            self.a = data

    def opROR(self, x):
        if x is None:
            tbyte = self.a
        else:
            addr = x()
            tbyte = self.ByteAt(addr)

        if self.p & self.CARRY:
            if tbyte & 1:
                pass
            else:
                self.p &= ~self.CARRY
            tbyte = (tbyte >> 1) | self.NEGATIVE
        else:
            if tbyte & 1:
                self.p |= self.CARRY
            tbyte >>= 1
        self.FlagsNZ(tbyte)

        if x is None:
            self.a = tbyte
        else:
            self.memory[addr] = tbyte  # NOQA

    def opSTA(self, x):
        self.memory[x()] = self.a

    def opSTY(self, x):
        self.memory[x()] = self.y

    def opSTX(self, y):
        self.memory[y()] = self.x

    def opCMPR(self, get_address, register_value):
        tbyte = self.ByteAt(get_address())
        self.p &= ~(self.CARRY | self.ZERO | self.NEGATIVE)
        if register_value == tbyte:
            self.p |= self.CARRY | self.ZERO
        elif register_value > tbyte:
            self.p |= self.CARRY
        self.p |= (register_value - tbyte) & self.NEGATIVE

    def opSBC(self, x):
        data = self.ByteAt(x())

        if self.p & self.DECIMAL:
            halfcarry = 1
            decimalcarry = 0
            adjust0 = 0
            adjust1 = 0

            nibble0 = (self.a & 0xF) + (~data & 0xF) + (self.p & self.CARRY)
            if nibble0 <= 0xF:
                halfcarry = 0
                adjust0 = 10
            nibble1 = ((self.a >> 4) & 0xF) + ((~data >> 4) & 0xF) + halfcarry
            if nibble1 <= 0xF:
                adjust1 = 10 << 4

            # the ALU outputs are not decimally adjusted
            # fmt: off
            aluresult = self.a + (~data & self.byteMask) \
                               + (self.p & self.CARRY)
            # fmt: on

            if aluresult > self.byteMask:
                decimalcarry = 1
            aluresult &= self.byteMask

            # but the final result will be adjusted
            nibble0 = (aluresult + adjust0) & 0xF
            nibble1 = ((aluresult + adjust1) >> 4) & 0xF

            self.p &= ~(self.CARRY | self.ZERO | self.NEGATIVE | self.OVERFLOW)
            if aluresult == 0:
                self.p |= self.ZERO
            else:
                self.p |= aluresult & self.NEGATIVE
            if decimalcarry == 1:
                self.p |= self.CARRY
            if ((self.a ^ data) & (self.a ^ aluresult)) & self.NEGATIVE:
                self.p |= self.OVERFLOW
            self.a = (nibble1 << 4) + nibble0
        else:
            result = self.a + (~data & self.byteMask) + (self.p & self.CARRY)
            self.p &= ~(self.CARRY | self.ZERO | self.OVERFLOW | self.NEGATIVE)
            if ((self.a ^ data) & (self.a ^ result)) & self.NEGATIVE:
                self.p |= self.OVERFLOW
            data = result & self.byteMask
            if data == 0:
                self.p |= self.ZERO
            if result > self.byteMask:
                self.p |= self.CARRY
            self.p |= data & self.NEGATIVE
            self.a = data

    def opDECR(self, x):
        if x is None:
            tbyte = self.a
        else:
            addr = x()
            tbyte = self.ByteAt(addr)

        self.p &= ~(self.ZERO | self.NEGATIVE)
        tbyte = (tbyte - 1) & self.byteMask
        if tbyte:
            self.p |= tbyte & self.NEGATIVE
        else:
            self.p |= self.ZERO

        if x is None:
            self.a = tbyte
        else:
            self.memory[addr] = tbyte  # NOQA

    def opINCR(self, x):
        if x is None:
            tbyte = self.a
        else:
            addr = x()
            tbyte = self.ByteAt(addr)

        self.p &= ~(self.ZERO | self.NEGATIVE)
        tbyte = (tbyte + 1) & self.byteMask
        if tbyte:
            self.p |= tbyte & self.NEGATIVE
        else:
            self.p |= self.ZERO

        if x is None:
            self.a = tbyte
        else:
            self.memory[addr] = tbyte  # NOQA

    def opLDA(self, x):
        self.a = self.ByteAt(x())
        self.FlagsNZ(self.a)

    def opLDY(self, x):
        self.y = self.ByteAt(x())
        self.FlagsNZ(self.y)

    def opLDX(self, y):
        self.x = self.ByteAt(y())
        self.FlagsNZ(self.x)

    def opRMB(self, x, mask):
        address = x()
        self.memory[address] &= mask

    def opSMB(self, x, mask):
        address = x()
        self.memory[address] |= mask

    def opSTZ(self, x):
        self.memory[x()] = 0x00

    def opTSB(self, x):
        address = x()
        m = self.memory[address]
        self.p &= ~self.ZERO
        z = m & self.a
        if z == 0:
            self.p |= self.ZERO
        self.memory[address] = m | self.a

    def opTRB(self, x):
        address = x()
        m = self.memory[address]
        self.p &= ~self.ZERO
        z = m & self.a
        if z == 0:
            self.p |= self.ZERO
        self.memory[address] = m & ~self.a

    #def get_

    def inst_not_implemented(self):
        """Default behavior for unimplemented instructions."""
        print(f"Warning: Opcode not implemented at PC={self.pc:04X}")  # NOQA
        self.pc += 1

    instruct = [inst_not_implemented] * 256
    cycletime = [0] * 256
    extracycles = [0] * 256
    disassemble = [("???", "imp")] * 256

    instruction = make_instruction_decorator(
        instruct, disassemble, cycletime, extracycles
    )

    @instruction(name="BRK", mode="imp", cycles=7)
    def inst_0x00(self):
        pc = (self.pc + 1) & self.addrMask
        self.stPushWord(pc)
        self.p |= self.BREAK
        self.stPush(self.p | self.BREAK | self.UNUSED)
        self.p |= self.INTERRUPT
        self.pc = self.WordAt(self.IRQ)
        self.p &= ~self.DECIMAL

    @instruction(name="ORA", mode="inx", cycles=6)
    def inst_0x01(self):
        self.opORA(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="ORA", mode="zpg", cycles=3)
    def inst_0x05(self):
        self.opORA(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="ASL", mode="zpg", cycles=5)
    def inst_0x06(self):
        self.opASL(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="PHP", mode="imp", cycles=3)
    def inst_0x08(self):
        self.stPush(self.p | self.BREAK | self.UNUSED)

    @instruction(name="ORA", mode="imm", cycles=2)
    def inst_0x09(self):
        self.opORA(self.ProgramCounter)
        self.pc += 1

    @instruction(name="ASL", mode="acc", cycles=2)
    def inst_0x0a(self):
        self.opASL(None)

    @instruction(name="ORA", mode="abs", cycles=4)
    def inst_0x0d(self):
        self.opORA(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="ASL", mode="abs", cycles=6)
    def inst_0x0e(self):
        self.opASL(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BPL", mode="rel", cycles=2, extracycles=2)
    def inst_0x10(self):
        self.opBCL(self.NEGATIVE)

    @instruction(name="ORA", mode="iny", cycles=5, extracycles=1)
    def inst_0x11(self):
        self.opORA(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="ORA", mode="zpx", cycles=4)
    def inst_0x15(self):
        self.opORA(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="ASL", mode="zpx", cycles=6)
    def inst_0x16(self):
        self.opASL(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="CLC", mode="imp", cycles=2)
    def inst_0x18(self):
        self.opCLR(self.CARRY)

    @instruction(name="ORA", mode="aby", cycles=4, extracycles=1)
    def inst_0x19(self):
        self.opORA(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="ORA", mode="abx", cycles=4, extracycles=1)
    def inst_0x1d(self):
        self.opORA(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="ASL", mode="abx", cycles=7)
    def inst_0x1e(self):
        self.opASL(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="JSR", mode="abs", cycles=6)
    def inst_0x20(self):
        self.stPushWord((self.pc + 1) & self.addrMask)
        self.pc = self.WordAt(self.pc)

    @instruction(name="AND", mode="inx", cycles=6)
    def inst_0x21(self):
        self.opAND(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="BIT", mode="zpg", cycles=3)
    def inst_0x24(self):
        self.opBIT(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="AND", mode="zpg", cycles=3)
    def inst_0x25(self):
        self.opAND(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="ROL", mode="zpg", cycles=5)
    def inst_0x26(self):
        self.opROL(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="PLP", mode="imp", cycles=4)
    def inst_0x28(self):
        self.p = self.stPop() | self.BREAK | self.UNUSED

    @instruction(name="AND", mode="imm", cycles=2)
    def inst_0x29(self):
        self.opAND(self.ProgramCounter)
        self.pc += 1

    @instruction(name="ROL", mode="acc", cycles=2)
    def inst_0x2a(self):
        self.opROL(None)

    @instruction(name="BIT", mode="abs", cycles=4)
    def inst_0x2c(self):
        self.opBIT(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="AND", mode="abs", cycles=4)
    def inst_0x2d(self):
        self.opAND(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="ROL", mode="abs", cycles=6)
    def inst_0x2e(self):
        self.opROL(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BMI", mode="rel", cycles=2, extracycles=2)
    def inst_0x30(self):
        self.opBST(self.NEGATIVE)

    @instruction(name="AND", mode="iny", cycles=5, extracycles=1)
    def inst_0x31(self):
        self.opAND(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="AND", mode="zpx", cycles=4)
    def inst_0x35(self):
        self.opAND(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="ROL", mode="zpx", cycles=6)
    def inst_0x36(self):
        self.opROL(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="SEC", mode="imp", cycles=2)
    def inst_0x38(self):
        self.opSET(self.CARRY)

    @instruction(name="AND", mode="aby", cycles=4, extracycles=1)
    def inst_0x39(self):
        self.opAND(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="AND", mode="abx", cycles=4, extracycles=1)
    def inst_0x3d(self):
        self.opAND(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="ROL", mode="abx", cycles=7)
    def inst_0x3e(self):
        self.opROL(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="RTI", mode="imp", cycles=6)
    def inst_0x40(self):
        self.p = self.stPop() | self.BREAK | self.UNUSED
        self.pc = self.stPopWord()

    @instruction(name="EOR", mode="inx", cycles=6)
    def inst_0x41(self):
        self.opEOR(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="EOR", mode="zpg", cycles=3)
    def inst_0x45(self):
        self.opEOR(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="LSR", mode="zpg", cycles=5)
    def inst_0x46(self):
        self.opLSR(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="PHA", mode="imp", cycles=3)
    def inst_0x48(self):
        self.stPush(self.a)

    @instruction(name="EOR", mode="imm", cycles=2)
    def inst_0x49(self):
        self.opEOR(self.ProgramCounter)
        self.pc += 1

    @instruction(name="LSR", mode="acc", cycles=2)
    def inst_0x4a(self):
        self.opLSR(None)

    @instruction(name="JMP", mode="abs", cycles=3)
    def inst_0x4c(self):
        self.pc = self.WordAt(self.pc)

    @instruction(name="EOR", mode="abs", cycles=4)
    def inst_0x4d(self):
        self.opEOR(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="LSR", mode="abs", cycles=6)
    def inst_0x4e(self):
        self.opLSR(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BVC", mode="rel", cycles=2, extracycles=2)
    def inst_0x50(self):
        self.opBCL(self.OVERFLOW)

    @instruction(name="EOR", mode="iny", cycles=5, extracycles=1)
    def inst_0x51(self):
        self.opEOR(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="EOR", mode="zpx", cycles=4)
    def inst_0x55(self):
        self.opEOR(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="LSR", mode="zpx", cycles=6)
    def inst_0x56(self):
        self.opLSR(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="CLI", mode="imp", cycles=2)
    def inst_0x58(self):
        self.opCLR(self.INTERRUPT)

    @instruction(name="EOR", mode="aby", cycles=4, extracycles=1)
    def inst_0x59(self):
        self.opEOR(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="EOR", mode="abx", cycles=4, extracycles=1)
    def inst_0x5d(self):
        self.opEOR(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="LSR", mode="abx", cycles=7)
    def inst_0x5e(self):
        self.opLSR(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="RTS", mode="imp", cycles=6)
    def inst_0x60(self):
        self.pc = self.stPopWord()
        self.pc += 1

    @instruction(name="ADC", mode="inx", cycles=6)
    def inst_0x61(self):
        self.opADC(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="ADC", mode="zpg", cycles=3)
    def inst_0x65(self):
        self.opADC(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="ROR", mode="zpg", cycles=5)
    def inst_0x66(self):
        self.opROR(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="PLA", mode="imp", cycles=4)
    def inst_0x68(self):
        self.a = self.stPop()
        self.FlagsNZ(self.a)

    @instruction(name="ADC", mode="imm", cycles=2)
    def inst_0x69(self):
        self.opADC(self.ProgramCounter)
        self.pc += 1

    @instruction(name="ROR", mode="acc", cycles=2)
    def inst_0x6a(self):
        self.opROR(None)

    @instruction(name="JMP", mode="ind", cycles=5)
    def inst_0x6c(self):
        ta = self.WordAt(self.pc)
        self.pc = self.WrapAt(ta)

    @instruction(name="ADC", mode="abs", cycles=4)
    def inst_0x6d(self):
        self.opADC(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="ROR", mode="abs", cycles=6)
    def inst_0x6e(self):
        self.opROR(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BVS", mode="rel", cycles=2, extracycles=2)
    def inst_0x70(self):
        self.opBST(self.OVERFLOW)

    @instruction(name="ADC", mode="iny", cycles=5, extracycles=1)
    def inst_0x71(self):
        self.opADC(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="ADC", mode="zpx", cycles=4)
    def inst_0x75(self):
        self.opADC(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="ROR", mode="zpx", cycles=6)
    def inst_0x76(self):
        self.opROR(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="SEI", mode="imp", cycles=2)
    def inst_0x78(self):
        self.opSET(self.INTERRUPT)

    @instruction(name="ADC", mode="aby", cycles=4, extracycles=1)
    def inst_0x79(self):
        self.opADC(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="ADC", mode="abx", cycles=4, extracycles=1)
    def inst_0x7d(self):
        self.opADC(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="ROR", mode="abx", cycles=7)
    def inst_0x7e(self):
        self.opROR(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="STA", mode="inx", cycles=6)
    def inst_0x81(self):
        self.opSTA(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="STY", mode="zpg", cycles=3)
    def inst_0x84(self):
        self.opSTY(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="STA", mode="zpg", cycles=3)
    def inst_0x85(self):
        self.opSTA(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="STX", mode="zpg", cycles=3)
    def inst_0x86(self):
        self.opSTX(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="DEY", mode="imp", cycles=2)
    def inst_0x88(self):
        self.y -= 1
        self.y &= self.byteMask
        self.FlagsNZ(self.y)

    @instruction(name="TXA", mode="imp", cycles=2)
    def inst_0x8a(self):
        self.a = self.x
        self.FlagsNZ(self.a)

    @instruction(name="STY", mode="abs", cycles=4)
    def inst_0x8c(self):
        self.opSTY(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="STA", mode="abs", cycles=4)
    def inst_0x8d(self):
        self.opSTA(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="STX", mode="abs", cycles=4)
    def inst_0x8e(self):
        self.opSTX(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BCC", mode="rel", cycles=2, extracycles=2)
    def inst_0x90(self):
        self.opBCL(self.CARRY)

    @instruction(name="STA", mode="iny", cycles=6)
    def inst_0x91(self):
        self.opSTA(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="STY", mode="zpx", cycles=4)
    def inst_0x94(self):
        self.opSTY(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="STA", mode="zpx", cycles=4)
    def inst_0x95(self):
        self.opSTA(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="STX", mode="zpy", cycles=4)
    def inst_0x96(self):
        self.opSTX(self.ZeroPageYAddr)
        self.pc += 1

    @instruction(name="TYA", mode="imp", cycles=2)
    def inst_0x98(self):
        self.a = self.y
        self.FlagsNZ(self.a)

    @instruction(name="STA", mode="aby", cycles=5)
    def inst_0x99(self):
        self.opSTA(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="TXS", mode="imp", cycles=2)
    def inst_0x9a(self):
        self.sp = self.x

    @instruction(name="STA", mode="abx", cycles=5)
    def inst_0x9d(self):
        self.opSTA(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="LDY", mode="imm", cycles=2)
    def inst_0xa0(self):
        self.opLDY(self.ProgramCounter)
        self.pc += 1

    @instruction(name="LDA", mode="inx", cycles=6)
    def inst_0xa1(self):
        self.opLDA(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="LDX", mode="imm", cycles=2)
    def inst_0xa2(self):
        self.opLDX(self.ProgramCounter)
        self.pc += 1

    @instruction(name="LDY", mode="zpg", cycles=3)
    def inst_0xa4(self):
        self.opLDY(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="LDA", mode="zpg", cycles=3)
    def inst_0xa5(self):
        self.opLDA(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="LDX", mode="zpg", cycles=3)
    def inst_0xa6(self):
        self.opLDX(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="TAY", mode="imp", cycles=2)
    def inst_0xa8(self):
        self.y = self.a
        self.FlagsNZ(self.y)

    @instruction(name="LDA", mode="imm", cycles=2)
    def inst_0xa9(self):
        self.opLDA(self.ProgramCounter)
        self.pc += 1

    @instruction(name="TAX", mode="imp", cycles=2)
    def inst_0xaa(self):
        self.x = self.a
        self.FlagsNZ(self.x)

    @instruction(name="LDY", mode="abs", cycles=4)
    def inst_0xac(self):
        self.opLDY(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="LDA", mode="abs", cycles=4)
    def inst_0xad(self):
        self.opLDA(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="LDX", mode="abs", cycles=4)
    def inst_0xae(self):
        self.opLDX(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BCS", mode="rel", cycles=2, extracycles=2)
    def inst_0xb0(self):
        self.opBST(self.CARRY)

    @instruction(name="LDA", mode="iny", cycles=5, extracycles=1)
    def inst_0xb1(self):
        self.opLDA(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="LDY", mode="zpx", cycles=4)
    def inst_0xb4(self):
        self.opLDY(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="LDA", mode="zpx", cycles=4)
    def inst_0xb5(self):
        self.opLDA(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="LDX", mode="zpy", cycles=4)
    def inst_0xb6(self):
        self.opLDX(self.ZeroPageYAddr)
        self.pc += 1

    @instruction(name="CLV", mode="imp", cycles=2)
    def inst_0xb8(self):
        self.opCLR(self.OVERFLOW)

    @instruction(name="LDA", mode="aby", cycles=4, extracycles=1)
    def inst_0xb9(self):
        self.opLDA(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="TSX", mode="imp", cycles=2)
    def inst_0xba(self):
        self.x = self.sp
        self.FlagsNZ(self.x)

    @instruction(name="LDY", mode="abx", cycles=4, extracycles=1)
    def inst_0xbc(self):
        self.opLDY(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="LDA", mode="abx", cycles=4, extracycles=1)
    def inst_0xbd(self):
        self.opLDA(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="LDX", mode="aby", cycles=4, extracycles=1)
    def inst_0xbe(self):
        self.opLDX(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="CPY", mode="imm", cycles=2)
    def inst_0xc0(self):
        self.opCMPR(self.ProgramCounter, self.y)
        self.pc += 1

    @instruction(name="CMP", mode="inx", cycles=6)
    def inst_0xc1(self):
        self.opCMPR(self.IndirectXAddr, self.a)
        self.pc += 1

    @instruction(name="CPY", mode="zpg", cycles=3)
    def inst_0xc4(self):
        self.opCMPR(self.ZeroPageAddr, self.y)
        self.pc += 1

    @instruction(name="CMP", mode="zpg", cycles=3)
    def inst_0xc5(self):
        self.opCMPR(self.ZeroPageAddr, self.a)
        self.pc += 1

    @instruction(name="DEC", mode="zpg", cycles=5)
    def inst_0xc6(self):
        self.opDECR(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="INY", mode="imp", cycles=2)
    def inst_0xc8(self):
        self.y += 1
        self.y &= self.byteMask
        self.FlagsNZ(self.y)

    @instruction(name="CMP", mode="imm", cycles=2)
    def inst_0xc9(self):
        self.opCMPR(self.ProgramCounter, self.a)
        self.pc += 1

    @instruction(name="DEX", mode="imp", cycles=2)
    def inst_0xca(self):
        self.x -= 1
        self.x &= self.byteMask
        self.FlagsNZ(self.x)

    @instruction(name="CPY", mode="abs", cycles=4)
    def inst_0xcc(self):
        self.opCMPR(self.AbsoluteAddr, self.y)
        self.pc += 2

    @instruction(name="CMP", mode="abs", cycles=4)
    def inst_0xcd(self):
        self.opCMPR(self.AbsoluteAddr, self.a)
        self.pc += 2

    @instruction(name="DEC", mode="abs", cycles=3)
    def inst_0xce(self):
        self.opDECR(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BNE", mode="rel", cycles=2, extracycles=2)
    def inst_0xd0(self):
        self.opBCL(self.ZERO)

    @instruction(name="CMP", mode="iny", cycles=5, extracycles=1)
    def inst_0xd1(self):
        self.opCMPR(self.IndirectYAddr, self.a)
        self.pc += 1

    @instruction(name="CMP", mode="zpx", cycles=4)
    def inst_0xd5(self):
        self.opCMPR(self.ZeroPageXAddr, self.a)
        self.pc += 1

    @instruction(name="DEC", mode="zpx", cycles=6)
    def inst_0xd6(self):
        self.opDECR(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="CLD", mode="imp", cycles=2)
    def inst_0xd8(self):
        self.opCLR(self.DECIMAL)

    @instruction(name="CMP", mode="aby", cycles=4, extracycles=1)
    def inst_0xd9(self):
        self.opCMPR(self.AbsoluteYAddr, self.a)
        self.pc += 2

    @instruction(name="CMP", mode="abx", cycles=4, extracycles=1)
    def inst_0xdd(self):
        self.opCMPR(self.AbsoluteXAddr, self.a)
        self.pc += 2

    @instruction(name="DEC", mode="abx", cycles=7)
    def inst_0xde(self):
        self.opDECR(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="CPX", mode="imm", cycles=2)
    def inst_0xe0(self):
        self.opCMPR(self.ProgramCounter, self.x)
        self.pc += 1

    @instruction(name="SBC", mode="inx", cycles=6)
    def inst_0xe1(self):
        self.opSBC(self.IndirectXAddr)
        self.pc += 1

    @instruction(name="CPX", mode="zpg", cycles=3)
    def inst_0xe4(self):
        self.opCMPR(self.ZeroPageAddr, self.x)
        self.pc += 1

    @instruction(name="SBC", mode="zpg", cycles=3)
    def inst_0xe5(self):
        self.opSBC(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="INC", mode="zpg", cycles=5)
    def inst_0xe6(self):
        self.opINCR(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="INX", mode="imp", cycles=2)
    def inst_0xe8(self):
        self.x += 1
        self.x &= self.byteMask
        self.FlagsNZ(self.x)

    @instruction(name="SBC", mode="imm", cycles=2)
    def inst_0xe9(self):
        self.opSBC(self.ProgramCounter)
        self.pc += 1

    @instruction(name="NOP", mode="imp", cycles=2)
    def inst_0xea(self):
        pass

    @instruction(name="CPX", mode="abs", cycles=4)
    def inst_0xec(self):
        self.opCMPR(self.AbsoluteAddr, self.x)
        self.pc += 2

    @instruction(name="SBC", mode="abs", cycles=4)
    def inst_0xed(self):
        self.opSBC(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="INC", mode="abs", cycles=6)
    def inst_0xee(self):
        self.opINCR(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="BEQ", mode="rel", cycles=2, extracycles=2)
    def inst_0xf0(self):
        self.opBST(self.ZERO)

    @instruction(name="SBC", mode="iny", cycles=5, extracycles=1)
    def inst_0xf1(self):
        self.opSBC(self.IndirectYAddr)
        self.pc += 1

    @instruction(name="SBC", mode="zpx", cycles=4)
    def inst_0xf5(self):
        self.opSBC(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="INC", mode="zpx", cycles=6)
    def inst_0xf6(self):
        self.opINCR(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="SED", mode="imp", cycles=2)
    def inst_0xf8(self):
        self.opSET(self.DECIMAL)

    @instruction(name="SBC", mode="aby", cycles=4, extracycles=1)
    def inst_0xf9(self):
        self.opSBC(self.AbsoluteYAddr)
        self.pc += 2

    @instruction(name="SBC", mode="abx", cycles=4, extracycles=1)
    def inst_0xfd(self):
        self.opSBC(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="INC", mode="abx", cycles=7)
    def inst_0xfe(self):
        self.opINCR(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="TSB", mode="zpg", cycles=5)
    def inst_0x04(self):
        self.opTSB(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="RMB0", mode="zpg", cycles=5)
    def inst_0x07(self):
        self.opRMB(self.ZeroPageAddr, 0xFE)
        self.pc += 1

    @instruction(name="TSB", mode="abs", cycles=6)
    def inst_0x0c(self):
        self.opTSB(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="ORA", mode="zpi", cycles=5)
    def inst_0x12(self):
        self.opORA(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="TRB", mode="zpg", cycles=5)
    def inst_0x14(self):
        self.opTRB(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="RMB1", mode="zpg", cycles=5)
    def inst_0x17(self):
        self.opRMB(self.ZeroPageAddr, 0xFD)
        self.pc += 1

    @instruction(name="INC", mode="acc", cycles=2)
    def inst_0x1a(self):
        self.opINCR(None)

    @instruction(name="TRB", mode="abs", cycles=6)
    def inst_0x1c(self):
        self.opTRB(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="RMB2", mode="zpg", cycles=5)
    def inst_0x27(self):
        self.opRMB(self.ZeroPageAddr, 0xFB)
        self.pc += 1

    @instruction(name="AND", mode="zpi", cycles=5)
    def inst_0x32(self):
        self.opAND(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="BIT", mode="zpx", cycles=4)
    def inst_0x34(self):
        self.opBIT(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="RMB3", mode="zpg", cycles=5)
    def inst_0x37(self):
        self.opRMB(self.ZeroPageAddr, 0xF7)
        self.pc += 1

    @instruction(name="DEC", mode="acc", cycles=2)
    def inst_0x3a(self):
        self.opDECR(None)

    @instruction(name="BIT", mode="abx", cycles=4)
    def inst_0x3c(self):
        self.opBIT(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="RMB4", mode="zpg", cycles=5)
    def inst_0x47(self):
        self.opRMB(self.ZeroPageAddr, 0xEF)
        self.pc += 1

    @instruction(name="EOR", mode="zpi", cycles=5)
    def inst_0x52(self):
        self.opEOR(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="RMB5", mode="zpg", cycles=5)
    def inst_0x57(self):
        self.opRMB(self.ZeroPageAddr, 0xDF)
        self.pc += 1

    @instruction(name="PHY", mode="imp", cycles=3)
    def inst_0x5a(self):
        self.stPush(self.y)

    @instruction(name="STZ", mode="zpg", cycles=3)
    def inst_0x64(self):
        self.opSTZ(self.ZeroPageAddr)
        self.pc += 1

    @instruction(name="RMB6", mode="zpg", cycles=5)
    def inst_0x67(self):
        self.opRMB(self.ZeroPageAddr, 0xBF)
        self.pc += 1

    @instruction(name="JMP", mode="ind", cycles=6)
    def inst_0x6c(self):
        ta = self.WordAt(self.pc)
        self.pc = self.WordAt(ta)

    @instruction(name="ADC", mode="zpi", cycles=5)
    def inst_0x72(self):
        self.opADC(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="STZ", mode="zpx", cycles=4)
    def inst_0x74(self):
        self.opSTZ(self.ZeroPageXAddr)
        self.pc += 1

    @instruction(name="RMB7", mode="zpg", cycles=5)
    def inst_0x77(self):
        self.opRMB(self.ZeroPageAddr, 0x7F)
        self.pc += 1

    @instruction(name="PLY", mode="imp", cycles=4)
    def inst_0x7a(self):
        self.y = self.stPop()
        self.FlagsNZ(self.y)

    @instruction(name="JMP", mode="iax", cycles=6)
    def inst_0x7c(self):
        self.pc = self.WordAt(self.IndirectAbsXAddr())

    @instruction(name="BRA", mode="rel", cycles=1, extracycles=1)
    def inst_0x80(self):
        self.BranchRelAddr()

    @instruction(name="SMB0", mode="zpg", cycles=5)
    def inst_0x87(self):
        self.opSMB(self.ZeroPageAddr, 0x01)
        self.pc += 1

    @instruction(name="BIT", mode="imm", cycles=2)
    def inst_0x89(self):
        # This instruction (BIT #$12) does not use opBIT because in the
        # immediate mode, BIT only affects the Z flag.
        tbyte = self.ImmediateByte()
        self.p &= ~(self.ZERO)  # NOQA
        if (self.a & tbyte) == 0:
            self.p |= self.ZERO
        self.pc += 1

    @instruction(name="STA", mode="zpi", cycles=5)
    def inst_0x92(self):
        self.opSTA(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="SMB1", mode="zpg", cycles=5)
    def inst_0x97(self):
        self.opSMB(self.ZeroPageAddr, 0x02)
        self.pc += 1

    @instruction(name="STZ", mode="abs", cycles=4)
    def inst_0x9c(self):
        self.opSTZ(self.AbsoluteAddr)
        self.pc += 2

    @instruction(name="STZ", mode="abx", cycles=5)
    def inst_0x9e(self):
        self.opSTZ(self.AbsoluteXAddr)
        self.pc += 2

    @instruction(name="SMB2", mode="zpg", cycles=5)
    def inst_0xa7(self):
        self.opSMB(self.ZeroPageAddr, 0x04)
        self.pc += 1

    @instruction(name="LDA", mode="zpi", cycles=5)
    def inst_0xb2(self):
        self.opLDA(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="SMB3", mode="zpg", cycles=5)
    def inst_0xb7(self):
        self.opSMB(self.ZeroPageAddr, 0x08)
        self.pc += 1

    @instruction(name="SMB4", mode="zpg", cycles=5)
    def inst_0xc7(self):
        self.opSMB(self.ZeroPageAddr, 0x10)
        self.pc += 1

    @instruction(name="WAI", mode='imp', cycles=3)
    def inst_0xcb(self):
        self.waiting = True

    @instruction(name="CMP", mode='zpi', cycles=5)
    def inst_0xd2(self):
        self.opCMPR(self.ZeroPageIndirectAddr, self.a)
        self.pc += 1

    @instruction(name="SMB5", mode="zpg", cycles=5)
    def inst_0xd7(self):
        self.opSMB(self.ZeroPageAddr, 0x20)
        self.pc += 1

    @instruction(name="PHX", mode="imp", cycles=3)
    def inst_0xda(self):
        self.stPush(self.x)

    @instruction(name="SMB6", mode="zpg", cycles=5)
    def inst_0xe7(self):
        self.opSMB(self.ZeroPageAddr, 0x40)
        self.pc += 1

    @instruction(name="SBC", mode="zpi", cycles=5)
    def inst_0xf2(self):
        self.opSBC(self.ZeroPageIndirectAddr)
        self.pc += 1

    @instruction(name="SMB7", mode="zpg", cycles=5)
    def inst_0xf7(self):
        self.opSMB(self.ZeroPageAddr, 0x80)
        self.pc += 1

    @instruction(name="PLX", mode="imp", cycles=4)
    def inst_0xfa(self):
        self.x = self.stPop()
        self.FlagsNZ(self.x)
