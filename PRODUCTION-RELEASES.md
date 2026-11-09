# Production release metadata

Keep publishing firmware through GitHub Releases. This automation adds checksums
and machine-readable links for the AuraPT order app. It does not compile firmware,
merge bootloaders, generate SEGGER DAT files or write to SharePoint.

## Publishing a version

1. Create a draft release with a tag such as `v3.4`.
2. Attach the matching `apt-3-4.dat` and `pt.cfg` produced by your existing process.
   Optionally attach its `.jflash` project. Preserve the actual production files.
3. Publish the release as a normal release, not a prerelease.
4. The **Production firmware manifest** action hashes those downloads and attaches
   `production-manifest.json` and `SHA256SUMS.txt` to the same release.

The workflow must first be merged into the default branch and Actions permitted
by the repository/organisation. For an existing release, or if assets were added
after publishing, use Actions → Production firmware manifest → Run workflow,
select the default branch and enter the release tag. Missing DAT/config files
fail explicitly; a UF2 or an archive is not silently treated as the DAT.

`v3.10` maps to `apt-3-10.dat`, not `apt-3-1.dat`. Version strings are never decimals.
Other supported examples: `3.4` and `v3.4.1`.

## App integration: next step

A SharePoint sync flow can consume `production-manifest.json` into a firmware
catalogue keyed by repository + release ID, with version, asset IDs, links and
SHA-256 values. That flow and the Power Apps version picker are not installed by
this change. New orders may select a release; existing orders must retain their
pinned asset IDs and hashes when newer releases arrive. Verify downloaded bytes
against the pinned hash before production use.

The release repository stores distribution files. Its tag/commit is not proof of
the firmware source revision. `firmware_source_commit` and `hardware_profile`
remain null until supplied and verified separately. `engineering_approved` is
false: successful hashing does not constitute engineering approval. Checksums
detect byte changes; they do not validate firmware behaviour, hardware compatibility
or prove that a supplied CFG matches a DAT.

Reruns accept identical metadata and recover a partially uploaded metadata pair.
Different metadata is never overwritten automatically. Do not replace firmware
assets in a release already assigned to an order: publish a new version instead.
Existing historical releases and source files are not modified by merging this PR.

## Local validation

Run `python3 -m unittest discover -s tests -v` (Python 3.9+).
The workflow uses GitHub's `gh` CLI and its short-lived repository token; no
Microsoft credentials or external service secrets are required for this stage.
