
# Contributing to be6502emu

Welcome to the ~~best~~ i meant mid af project ever! 🎉

Please follow these guidelines carefully to ensure a smooth collaboration.

## Workflow

1. **Fork the Repository**:  
   Start by forking the repository to your GitHub account.

2. **Create a New Branch**:  
   The `master` branch is locked. Please create a new branch for your changes.  
   Use a meaningful branch name like `feature/add-new-feature` or `bugfix/fix-issue`.

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Run Tests Locally**:  
   Before committing your changes, ensure you run the full test suite using `tox`:

   ```bash
   tox
   ```

4. **Code Quality Checks**:  
   Ensure your code adheres to the project's style guide by running the following checks:
   - **Mypy** for static type checking:
     ```bash
     mypy your_module.py
     ```
   - **Flake8** for linting:
     ```bash
     flake8 your_module.py
     ```

5. **Commit Your Changes**:  
   Write clear and concise commit messages that describe your changes. For example:
   ```bash
   git commit -m "Added feature: Early MOS 6502 ROR bug emulation"
   ```

6. **Push and Open a Pull Request**:  
   Push your branch to your fork and open a Pull Request (PR) to the `master` branch of the main repository.

   ```bash
   git push origin feature/your-feature-name
   ```

   When opening the PR, ensure the following:
   - Provide a clear description of your changes.
   - Link to any relevant issues (if applicable).
   - Mention that you’ve run all tests and checks.

## Additional Guidelines

- **Consistency**: Follow the coding style and conventions used in the project.
- **Documentation**: Update documentation or comments if your changes affect existing functionality.
- **Dependencies**: Avoid introducing unnecessary dependencies.
- **Pull Request Reviews**: Be open to feedback and ready to make adjustments based on reviewer comments.

Thank you for helping to improve **be6502emu**!
