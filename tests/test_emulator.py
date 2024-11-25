def test_import():
    import src.be6502emu.core as core
    assert core._is_imported == True

def test_main():
    import src.be6502emu.core as core
    failled = core.main()
    assert failled == False