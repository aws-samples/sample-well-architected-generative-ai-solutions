# Sample Well-Architected Generative AI Solutions

This repository contains sample implementations and reference architectures for building well-architected generative AI solutions on AWS.

## Repository Structure

```
.
├── mcp-servers/                                            # MCP (Model Context Protocol) server implementations
│   └── aws-api-mcp-server-with-iamrole-support/            # Forked AWS API MCP server with cross-account IAM AssumeRole support
│       ├── awslabs/                                         # Source package
│       │   └── aws_api_mcp_server/                          # Main MCP server module
│       │       ├── core/                                    # Core library code
│       │       │   ├── agent_scripts/                       # Pre-built agent troubleshooting scripts
│       │       │   │   └── registry/                        # Script registry with ready-to-use operational scripts
│       │       │   ├── aws/                                 # AWS API driver, pagination, region and service handling
│       │       │   ├── common/                              # Shared utilities — config, credentials, errors, file ops, models
│       │       │   ├── data/                                # Static data files (API metadata JSON)
│       │       │   ├── metadata/                            # API metadata helpers (read-only operations list)
│       │       │   ├── parser/                              # Command parser, lexer, and custom validators (EC2, SSM, botocore)
│       │       │   └── security/                            # Security policy and API customization rules
│       │       └── server.py                                # MCP server entry point
│       ├── tests/                                           # Test suite
│       │   ├── agent_scripts/                               # Tests for agent script manager
│       │   ├── aws/                                         # Tests for AWS driver, pagination, and service layer
│       │   ├── common/                                      # Tests for shared utilities
│       │   ├── metadata/                                    # Tests for metadata helpers
│       │   └── parser/                                      # Tests for command parser
│       ├── Dockerfile                                       # Container build definition
│       ├── pyproject.toml                                   # Python project configuration and dependencies
│       ├── CHANGELOG.md                                     # Version history
│       ├── CONTRIBUTING.md                                  # Contribution guidelines
│       └── LICENSE                                          # Apache-style license
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
