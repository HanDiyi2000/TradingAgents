# Coding-agent tool manifest

| Tool | Allowed role | Scope | Enforcement |
| --- | --- | --- | --- |
| File reader | Plan, Build, Test author, Verify | Files explicitly listed for that role | Default deny; read scope does not confer write rights. |
| File editor | Build, Test author | Named implementation files or pre-approval test files respectively | Disallow writing approved tests, human rules, approval records and credentials. |
| Shell / test runner | Human or CI | Checked-out revision; approved regression, structural and behavioural commands | No unrestricted model shell. Attach command, exit status and relevant output to the actual review. |
| Remote MCP, network search, Git push, hosted repository settings | None of the coding roles by default | No automatic remote effects | Human maintainer performs explicitly authorized remote operations. |

Application data-provider calls are runtime services. They do not authorize a development agent to read provider keys, change GitHub settings or invoke an unlisted MCP tool.
