# Screenshot uploads

`patch_metadata.py --upload-screenshots DIR` uploads screenshots only to the
editable in-flight version selected by the normal resolver. It is dry-run by
default and accepts only regular PNG files with a valid PNG signature and IHDR
dimensions. It rejects symlinks, more than ten files, and files larger than
20 MiB.

Files are sorted by filename; that is their display order. Use descriptive
zero-padded names such as `01-home.png`.

The command refuses to append to an existing screenshot set unless
`--append-screenshots` is supplied. It never silently deletes or replaces
existing assets. Delete a set in App Store Connect for a clean replacement,
then run the dry-run and the explicit `--apply` command.

Upload URLs must be HTTPS and redirects are disabled so provider-supplied
upload headers are not forwarded to another host.
