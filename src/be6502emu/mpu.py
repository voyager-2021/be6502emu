from py65.utils.conversions import itoa


def make_instruction_decorator(instruct, disasm, allcycles, allextras):
    def instruction(name, mode, cycles, extracycles=0):
        def decorate(f):
            opcode = int(f.__name__.split('_')[-1], 16)
            instruct[opcode] = f
            disasm[opcode] = (name, mode)
            allcycles[opcode] = cycles
            allextras[opcode] = extracycles
            return f  # Return the original function
        return decorate
    return instruction


class MPU:
    RESET = 0xfffc
    NMI = 0xfffa
    IRQ = 0xfffe

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
        self.name = '65C02'
        self.byteMask = ((1 << self.BYTE_WIDTH) - 1)
        self.addrMask = ((1 << self.ADDR_WIDTH) - 1)
        self.addrHighMask = (self.byteMask << self.BYTE_WIDTH)
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
        return ("%s PC  AC XR YR SP NV-BDIZC\n"
                "%s: %04x %02x %02x %02x %02x %s")

    def __repr__(self):
        flags = itoa(self.p, 2).rjust(self.BYTE_WIDTH, '0')
        indent = ' ' * (len(self.name) + 2)

        return self.reprformat() % (indent, self.name, self.pc, self.a,
                                    self.x, self.y, self.sp, flags)

    def _step(self):
        instruct_code = self.memory[self.pc]
        self.pc = (self.pc + 1) & self.addrMask
        self.excycles = 0
        self.addcycles = self.extracycles[instruct_code]
        self.instruct[instruct_code](self) # NOQA
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
        wrap = lambda x: (x & self.addrHighMask) + ((x + 1) & self.byteMask) # NOQA
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
            self.memory[addr] = tbyte # NOQA

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
            self.memory[addr] = tbyte # NOQA

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
            self.memory[addr] = tbyte # NOQA

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
            nibble0 = (data & 0xf) + (self.a & 0xf) + (self.p & self.CARRY)
            if nibble0 > 9:
                adjust0 = 6
                halfcarry = 1
            nibble1 = ((data >> 4) & 0xf) + ((self.a >> 4) & 0xf) + halfcarry
            if nibble1 > 9:
                adjust1 = 6
                decimalcarry = 1

            # the ALU outputs are not decimally adjusted
            nibble0 &= 0xf
            nibble1 &= 0xf
            aluresult = (nibble1 << 4) + nibble0

            # the final A contents will be decimally adjusted
            nibble0 = (nibble0 + adjust0) & 0xf
            nibble1 = (nibble1 + adjust1) & 0xf
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
            self.memory[addr] = tbyte # NOQA

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

            nibble0 = (self.a & 0xf) + (~data & 0xf) + (self.p & self.CARRY)
            if nibble0 <= 0xf:
                halfcarry = 0
                adjust0 = 10
            nibble1 = ((self.a >> 4) & 0xf) + ((~data >> 4) & 0xf) + halfcarry
            if nibble1 <= 0xf:
                adjust1 = 10 << 4

            # the ALU outputs are not decimally adjusted
            aluresult = self.a + (~data & self.byteMask) + \
                (self.p & self.CARRY)

            if aluresult > self.byteMask:
                decimalcarry = 1
            aluresult &= self.byteMask

            # but the final result will be adjusted
            nibble0 = (aluresult + adjust0) & 0xf
            nibble1 = ((aluresult + adjust1) >> 4) & 0xf

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
            self.memory[addr] = tbyte # NOQA

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
            self.memory[addr] = tbyte # NOQA

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

    def inst_not_implemented(self):
        """Default behavior for unimplemented instructions."""
        print(f"Warning: Opcode not implemented at PC={self.pc:04X}") # NOQA
        self.pc += 1

    instruct = [inst_not_implemented] * 256
    cycletime = [0] * 256
    extracycles = [0] * 256
    disassemble = [('???', 'imp')] * 256

    instruction = make_instruction_decorator(instruct, disassemble,
                                             cycletime, extracycles)

    @instruction(name="BRK", mode="imp", cycles=7)
    def inst_0x00(self):
        # pc has already been increased one
        pc = (self.pc + 1) & self.addrMask
        self.stPushWord(pc)

        self.p |= self.BREAK
        self.stPush(self.p | self.BREAK | self.UNUSED)

        self.p |= self.INTERRUPT
        self.pc = self.WordAt(self.IRQ)

        # 65C02 clears decimal flag, NMOS 6502 does not
        self.p &= ~self.DECIMAL

    @instruction(name="LDA", mode="imm", cycles=2)
    def inst_0xa9(self):
        self.opLDA(self.ProgramCounter)
        self.pc += 1
