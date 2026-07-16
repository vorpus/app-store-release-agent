# Release-validation TODO

Before relying on the new public-repo tooling for a live release:

- Push the security workflow and confirm its GitHub Actions run passes.
- Enable GitHub secret scanning and push protection; require both security jobs
  in branch protection.
- Exercise review submission and screenshot upload against a disposable
  in-flight App Store Connect version.
- Exercise Applyra with a non-sensitive private workspace and confirm its live
  response shapes.
- Run a full-history secret-scan finding review; rotate and remediate anything
  credible before public release.
