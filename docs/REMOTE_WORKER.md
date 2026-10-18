# Remote worker protocol v1

`maxkompilator worker --workspace /srv/builds` speaks UTF-8 JSON lines on stdio.
The operator provisions trusted projects and tools in this existing workspace.
`maxkompilator remote builder /srv/builds` reports capabilities using SSH with
batch authentication and mandatory known-host verification. The POSIX worker must
have `python3 -m maxkompilator` installed. Existing SSH configuration supplies the
identity; Maxkompilator does not collect passwords, generate keys or change SSH
settings. No unauthenticated network listener is exposed.

For an existing project:

```sh
maxkompilator remote builder /srv/builds --project example --format executable --smoke-test --output ./download
```

Each request carries `protocol: 1`, a unique 32-character hexadecimal `id` and
`operation`. Responses repeat the version and ID and use `event` of `log`, `result`
or `error`. Operations:

| Operation | Fields | Result |
| --- | --- | --- |
| capabilities | none | version, OS/native target, adapter API/kinds, operations, chunk limit, tool paths |
| build | project, optional kind/entry/target/format/smoke_test/timeout | job_id, status, error, smoke_status, artifacts |
| cancel | job_id | cancellation_requested; build emits final cancelled result |
| fetch | job_id, artifact_id, offset, size | offset, base64 data |

Capabilities report executable discovery, not successful tool probes. Each build
performs its normal environment checks. The workspace/project path is confined;
absolute and traversal paths are rejected. Requests cannot supply arbitrary shell
commands. Builds execute trusted project code with worker account permissions;
operators must isolate untrusted projects with an OS/container boundary.

One connection runs one job at a time, with at most 64 completed jobs and 100,000
requests. Requests are capped at 64 KiB; fetch chunks at 256 KiB; each build stage
has a maximum requested timeout of 3600 seconds. Disconnect cancels an active job.
Only successful-job files in its manifest can be fetched. The client uses a new
destination, validates paths and sizes, writes temporary files, verifies SHA-256,
and then renames them. A partially failed download must not be treated as a
complete distribution. Operator-managed job storage is `.maxkompilator-remote/`;
automatic deletion, source upload, queues and deployment are outside v1.
POSIX execute bits are preserved without special/world-writable modes. Internal
file symlinks are transferred as regular file contents; directory-symlink layouts
and signed macOS application bundles are not a qualified remote distribution path.

`WorkerClient` also accepts an explicit argv for local pipes or a caller-managed
authenticated transport. Integration tests start real independent workers, build
and run a resource-bearing PYZ, download and hash it, cancel a running application,
reuse the connection, and reject malformed paths, protocol versions and corrupt
downloads. Local transport tests qualify the protocol; they do not claim a
production remote server has been deployed.
