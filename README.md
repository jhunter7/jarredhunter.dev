# JarredHunter.dev

**Personal Developer Landing Page & CI/CD Pipeline**

A containerized static site hosted in a K3s cluster, with an automated GitHub Actions workflow that:

1. Bumps a semantic version tag on each merge to **main**
2. Pushes two Docker image tags: `vX.Y.Z` and `latest`
3. SSHes into your K3s server to perform a rolling update of the `jhdev-website` Deployment

## Getting Started

### Prerequisites

- Docker Hub account (for image registry)
- K3s cluster accessible via SSH
- GitHub repository with Actions enabled

### Local Preview

You can serve the static files locally, e.g.:

```bash
# using a simple live server
npm install -g serve
serve .
Open your browser at http://localhost:5000 (default port).
```
## CI/CD Workflow: `ci-deploy.yml`

### Trigger

- **Automatically** on every push to the `main` branch
- **Manually** via the Actions tab (`workflow_dispatch`) if needed

---

### Pipeline Steps

#### Version Job

- Runs `git describe --tags` to find or default to `v0.0.0`
- Increments the patch component (e.g. `v1.2.3` → `v1.2.4`)
- Pushes the new Git tag back to GitHub

#### Build Job

- Logs in to Docker Hub
- Builds the site container with Docker Buildx
- Pushes two tags:
  - `jhunter7/jhdev:vX.Y.Z` (new semantic version)
  - `jhunter7/jhdev:latest`

#### Deploy Job

- SSHes into your K3s host
- Runs `kubectl set image` to update the `jhdev-website` Deployment to `vX.Y.Z`
- Waits for the rollout to complete

---

### Configuration & Secrets

Go to **Settings → Secrets and variables → Actions** in your GitHub repository and add:

| Secret Name         | Description                              |
|---------------------|------------------------------------------|
| `DOCKER_USERNAME`   | Docker Hub username                      |
| `DOCKER_PASSWORD`   | Docker Hub password or access token       |
| `K3S_SERVER_IP`     | Public IP or DNS of your K3s server      |
| `K3S_SERVER_USER`   | SSH user on your K3s host (e.g. ubuntu)  |
| `K3S_SSH_PRIVATE_KEY` | SSH private key (PEM format)           |

> **Note:**  
> Also ensure your SSH public key is in `~/.ssh/authorized_keys` on the K3s server for the `K3S_SERVER_USER`.

---

### Bumping Versions

- Version info lives in the `VERSION` file.
- `.bumpversion.cfg` configures `bump2version` to:
  - Read `VERSION`
  - Increment patch/minor/major on each run
  - Commit the change and tag `vX.Y.Z`
- This is invoked automatically by the version job on merge to `main`.

---

### Deployment Details

- **Deployment name:** `jhdev-website`
- **Kubernetes namespace:** `jhdev`
- **Container image:** `jhunter7/jhdev:<tag>`

The GitHub Actions runner SSHes in and runs:

```bash
kubectl set image deployment/jhdev-website \
  jhdev-website=jhunter7/jhdev:${{ new_version }} \
  -n jhdev

kubectl rollout status deployment/jhdev-website -n jhdev
```

---

### Manual Deployment

If you ever need to deploy a specific existing tag without bumping, you can:

```bash
gh workflow run ci-deploy.yml \
  --field ref=refs/tags/v1.2.3
```

Or trigger it via the Actions UI by selecting the **CI • Build & Deploy on main** workflow and choosing an existing tag in the “Use workflow from” dropdown.