# be6502emu

![Tests](https://github.com/voyager-2021/be6502emu/actions/workflows/tests.yml/badge.svg)
![Static Badge](https://img.shields.io/badge/License-MIT-blue)
![Static Badge](https://img.shields.io/badge/Source-open-red)
![Static Badge](https://img.shields.io/badge/Contributors-welcome-orange)

**be6502emu** is an emulator for Ben Eater's 6502 computer. It aims to accurately emulate the 65C02 microprocessor, used in many classic systems and retrocomputing projects. This project is a work in progress, with a focus on implementing the full instruction set, memory management, and accurate cycle timing.

## Features (In Progress)
- Basic CPU core implementation
- Partial opcode support with semi-accurate cycle timing
- Basic memory handling

## What’s Coming Next
- Full opcode support for the 65C02 instruction set
- Decimal Mode: Accurate emulation of Binary-Coded Decimal (BCD) operations
- Interrupt handling for BRK, IRQ, and NMI
- Memory banking and mirroring enhancements
- Cycle-accurate emulation of instructions and addressing modes

## Getting Started

### Prerequisites
To build and run **be6502emu**, you'll need:
- cpython (3.10 or bigger and less than 3.14)
- pip (for installing dependencies)

### Building

1. Clone the repository:
    ```bash
    git clone https://github.com/voyager-2021/be6502emu.git
    cd be6502emu
    ```

2. Install dependencies:
    ```bash
    python -m pip install --upgrade pip
    pip install pdm
    pdm install
    ```

3. Run the tests:
    ```bash
    pdm run pytest
    ```

4. Running tox:
    ```bash
    pip install -r requirements_tests.txt
    pdm run tox
    ```

### Usage
Currently, **be6502emu** is a test based and can execute some instructions, but it is still under heavy development.

## Contributing

Contributions are welcome! Here's how you can help:
- Implement missing opcodes and instructions.
- Improve cycle timing and accuracy.
- Add support for interrupts and Decimal Mode.
- Improve memory management features (mirroring, banking, etc.).
- Write tests and documentation.

If you're interested in contributing, please open an issue or submit a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Thank you for your interest in **be6502emu**!