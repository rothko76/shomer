# ADR-0002: How CI updates image tags in the GitOps tree

- Status: Accepted
- Date: 2026-10-20

## Context
ArgoCD pulls from this repo, and CI also writes to it: after building and signing an image, CI
records the new image in `platform/gitops/`. In one repo, that write could trigger CI again and
loop. It also has to get past branch protection on `master` (PRs required). CI must never get
credentials to reach the cluster.

## Decision
- **kind (v1): direct commit by a bot.** After `app-ci` pushes and signs an image, it commits
  `image.tag` (git short SHA) and `image.digest` to
  `platform/gitops/components/shomer/overlays/kind/values.yaml`. The commit is made with a
  GitHub App token (`shomer-bot`), which is on the branch-protection bypass list.
- **Loop prevention, in layers:**
  1. The bump commit only touches `platform/gitops/**`. `app-ci` triggers on `app/**` only.
  2. `app-ci` skips commits authored by `shomer-bot[bot]`.
  3. Runs use `concurrency: app-ci-${{ github.ref }}`, so a late run can't overwrite a newer tag
     (the bump job also rebases and retries on push conflicts).
- Tags are immutable (`sha-<short>`, never `latest`). The digest is pinned so Kyverno and
  cosign can verify exactly what runs.
- **EKS (later): promotion by PR.** Promoting to `overlays/eks` copies the kind tag in a PR
  that a human approves. The PR is opened with the App token, because PRs opened with
  `GITHUB_TOKEN` don't trigger workflows, so required checks would never run.

## Alternatives considered
- **Argo CD Image Updater (git write-back):** this moves the write into the cluster, which then
  needs a Git token. It hits the same branch-protection problem and is one more component to run
  on kind. Revisit if the number of images grows.
- **A PR for every kind deploy:** easier to audit, but it adds a PR to review on every merge
  for a throwaway local environment. Kept for EKS instead.
- **A separate config repo:** this is the usual way to avoid the loop, but it undoes ADR-0001.

## Consequences
- This needs a GitHub App (`shomer-bot`) with `contents: write`, with its key stored as an
  Actions secret. That is the only credential CI holds, and it can't reach any cluster.
- Every kind deploy is a visible commit in `git log -- platform/gitops`, so rolling back is a
  `git revert`.
