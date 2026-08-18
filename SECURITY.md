# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities — especially anything involving the package
signing key or a package that may have been tampered with — privately via
[GitHub Security Advisories](https://github.com/metal3-community/ironic-packages/security/advisories/new)
rather than a public issue. Please do not disclose publicly until a fix and,
if needed, a key rotation have shipped.

## Package signing model

This repository publishes an APK package repository to GitHub Pages
(`https://metal3-community.github.io/ironic-packages/`). Packages and the
`APKINDEX.tar.gz` for each `distro/arch` are signed with a melange RSA key.
Consumers trust the repository by installing the **public** key:

```sh
wget -P /etc/apk/keys https://metal3-community.github.io/ironic-packages/melange.rsa.pub
```

Trust rules — these are enforced by CI and must never be relaxed:

- **The private key lives only in the `MELANGE_SIGNING_KEY` repository
  secret.** It is written to disk inside a job at build time and never
  leaves the runner.
- **Only the public key (`melange.rsa.pub`) is ever published** — to Pages,
  and nowhere else. The private key must never be pushed to the container
  registry, committed, or uploaded to Pages.
- Every `APKINDEX.tar.gz` is (re)signed with the current key at publish time,
  so the deployed repository always verifies against the deployed public key.
- A pre-upload guard (`Verify no private key in artifact`) fails the publish
  job if any `*.rsa`/`*.pem` file is about to be uploaded to Pages.

## 2026-08 incident

An earlier version of the publish workflow was insecure in three ways, all
since fixed:

1. **The private signing key was published.** It was pushed to the public
   `ghcr.io/metal3-community/ironic-packages:signing-keys` package and copied
   into the Pages artifact as `/melange.rsa`, both anonymously downloadable.
   Anyone could sign packages that consumers would trust.
2. **The key was regenerated on every run**, but only changed packages were
   rebuilt, so the published index ended up signed by a key that no longer
   existed — signature verification failed for all consumers.
3. **Build failures were swallowed** (`|| echo "Warning..."`), so runs went
   green while republishing broken, stale state.

Any key that existed before the rotation below is **compromised**; treat every
package that was signed by it as untrusted (the remediation rebuilds all
packages from source).

## Key rotation runbook

Run this whenever the signing key is (or may be) exposed, or on a routine
rotation schedule.

1. **Generate a new keypair** (keep the private key offline; never commit it):

   ```sh
   melange keygen melange.rsa           # produces melange.rsa + melange.rsa.pub
   ```

2. **Store the private key as a repository secret** (this is the only place it
   should live):

   ```sh
   gh secret set MELANGE_SIGNING_KEY -R metal3-community/ironic-packages < melange.rsa
   ```

3. **Delete the leaked registry artifact**, if present. This needs a token
   with `read:packages,delete:packages`
   (`gh auth refresh -s read:packages,delete:packages`), or use the GitHub UI
   (Org → Packages → `ironic-packages/signing-keys` → Manage versions →
   Delete):

   ```sh
   gh api -X DELETE \
     /orgs/metal3-community/packages/container/ironic-packages%2Fsigning-keys
   ```

4. **Rebuild and republish everything from source** with the new key. The
   force rebuild re-signs every package and index:

   ```sh
   gh workflow run build-and-publish.yaml \
     -R metal3-community/ironic-packages -f force_rebuild=true
   ```

5. **Verify** once Pages redeploys:

   ```sh
   # The private key must NOT be reachable (expect 404):
   curl -so /dev/null -w '%{http_code}\n' \
     https://metal3-community.github.io/ironic-packages/melange.rsa

   # The index must verify against the published public key. Fetch the index
   # and public key and confirm the signature, e.g. by installing the .pub
   # into /etc/apk/keys and running `apk update` against the repo.
   ```

6. **Notify consumers.** Anyone who installed the old public key or trusted
   packages during the exposure window should re-fetch `melange.rsa.pub` and
   rebuild any images that pulled from this repository. Downstream builds
   (e.g. metal-boot's apko/Dockerfile) can drop any temporary
   `--ignore-signatures` workaround once the republish completes.

## Consuming this repository securely

- Always install `melange.rsa.pub` into `/etc/apk/keys` (or the apko
  `keyring`) and let apk/apko verify signatures. Do **not** disable signature
  verification in production images.
- If you must build against this repo while a rotation is in progress, scope
  any `--ignore-signatures` / `--keyring` workaround to that build and remove
  it afterward.
