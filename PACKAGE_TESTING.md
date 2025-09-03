# Package Testing Guide

This guide provides comprehensive testing instructions for the `role_play_system` Python package before publishing to GCP Artifact Registry.

## Quick Start

**Option 1: Scripts handle venv automatically**
```bash
# Test everything locally (scripts auto-activate venv)
make test-package-all

# Test GCP upload (interactive)
make test-gcp-upload
```

**Option 2: Manually activate venv first**
```bash
# Activate virtual environment first
source venv/bin/activate

# Then run tests
make test-package-all
```

**Option 3: Use the venv-aware target**
```bash
# Alternative command that ensures venv activation
make test-package-venv
```

## Testing Scripts

### 1. Build Testing (`test-build.sh`)

Tests the package build process and validates artifacts:

```bash
cd src/python
./test-build.sh
```

**What it tests:**
- Clean build process
- Artifact creation (.whl and .tar.gz)
- Package metadata validation with twine
- File contents and sizes
- Required files inclusion

### 2. Installation Testing (`test-install.sh`)

Tests package installation in a clean environment:

```bash
cd src/python
./test-install.sh
```

**What it tests:**
- Virtual environment creation
- Package installation from wheel
- Module imports
- Dependency installation
- Package metadata verification
- Clean uninstallation

### 3. Content Inspection (`inspect-package.sh`)

Detailed inspection of package contents:

```bash
cd src/python
./inspect-package.sh
```

**What it shows:**
- Detailed file listings
- Module structure
- Essential file presence
- Unwanted file detection
- Dependency information
- Comparison between wheel and tarball

### 4. GCP Upload Testing (`test-gcp-upload.sh`)

Interactive GCP Artifact Registry testing:

```bash
cd src/python
./test-gcp-upload.sh
```

**What it tests:**
- GCP CLI installation and auth
- Project access and permissions
- Artifact Registry API enablement
- Test repository creation
- Twine configuration
- Actual upload testing (optional)
- Installation from Artifact Registry

## Step-by-Step Testing Process

### Phase 1: Local Testing

1. **Build the package:**
   ```bash
   make build-package
   ```

2. **Run all local tests:**
   ```bash
   make test-package-all
   ```

3. **Inspect package contents:**
   ```bash
   make inspect-package
   ```

### Phase 2: GCP Testing

1. **Set up GCP authentication:**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Run GCP tests:**
   ```bash
   make test-gcp-upload
   ```

3. **Follow the interactive prompts to:**
   - Configure project settings
   - Create test repository
   - Perform test upload
   - Verify installation from registry

### Phase 3: GitHub Actions Testing

1. **Verify workflow syntax:**
   ```bash
   # Install act for local testing (optional)
   brew install act  # or similar for your OS
   act -n  # dry run
   ```

2. **Check required secrets are set:**
   - `GCP_PROJECT_ID`
   - `GCP_SA_KEY`
   - `GCP_REGION`
   - `GCP_ARTIFACT_REGISTRY_REPO`

3. **Test with a pre-release tag:**
   ```bash
   git tag v0.1.0-test
   git push origin v0.1.0-test
   ```

## Common Issues and Solutions

### Build Issues

**Problem:** `python3 -m build` fails
- **Solution:** Install build tools: `pip install build setuptools wheel`

**Problem:** Missing dependencies in package
- **Solution:** Check `pyproject.toml` dependencies list matches `requirements.txt`

### Installation Issues

**Problem:** Import errors after installation
- **Solution:** Verify `__init__.py` files exist in all packages

**Problem:** Missing dependencies
- **Solution:** Check dependency specification in `pyproject.toml`

### GCP Issues

**Problem:** Authentication failures
- **Solution:** Run `gcloud auth login` and `gcloud auth application-default login`

**Problem:** Repository not found
- **Solution:** Create repository: `gcloud artifacts repositories create python-packages --repository-format=python --location=us-central1`

**Problem:** Permission denied
- **Solution:** Ensure service account has `artifactregistry.writer` role

## Pre-Release Checklist

Before creating a release tag:

- [ ] `make test-package-all` passes
- [ ] Package installs and imports correctly
- [ ] All required files are included in package
- [ ] No unwanted files (cache, git, etc.) in package
- [ ] GCP authentication and permissions configured
- [ ] Test repository upload successful
- [ ] GitHub secrets configured correctly
- [ ] Version number updated in `pyproject.toml`

## Release Process

When ready to release:

1. **Update version:**
   ```bash
   # Edit src/python/role_play/pyproject.toml
   version = "0.1.1"  # or appropriate version
   ```

2. **Final testing:**
   ```bash
   make test-package-all
   ```

3. **Create and push tag:**
   ```bash
   git add .
   git commit -m "chore: bump version to 0.1.1"
   git tag v0.1.1
   git push origin main
   git push origin v0.1.1
   ```

4. **Monitor GitHub Actions:**
   - Check workflow execution in GitHub
   - Verify package appears in Artifact Registry
   - Test installation from production registry

## Cleanup

After testing, clean up temporary files:

```bash
# Remove build artifacts
cd src/python/role_play
rm -rf dist/ build/ *.egg-info

# Remove test repositories (if created)
gcloud artifacts repositories delete python-test --location=us-central1

# Remove test tags
git tag -d v0.1.0-test
git push origin --delete v0.1.0-test
```

## Getting Help

If you encounter issues:

1. Check this guide for common solutions
2. Verify all prerequisites are installed
3. Check GCP console for detailed error messages
4. Review GitHub Actions logs for workflow issues

For additional help, refer to:
- [Python Packaging Guide](https://packaging.python.org/)
- [GCP Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Twine Documentation](https://twine.readthedocs.io/)