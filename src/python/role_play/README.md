# Role Play System (RPS) - Python Package

**An AI-powered, multilingual role-playing conversation platform that transforms how we practice and learn through interactive scenarios.**

## About

RPS is a comprehensive backend system designed for educational institutions, corporate training, and learning platforms that provides:

- **LLM-Powered Characters**: Sophisticated role-play scenarios with Gemini 2.0 Flash integration
- **Comprehensive Analytics**: Built-in evaluation system with detailed performance reports
- **Educational Focus**: Purpose-built for learning scenarios like medical interviews, customer service training, and job preparation

## Installation

Install from GCP Artifact Registry:

```bash
pip install role-play-system --extra-index-url https://us-central1-python.pkg.dev/YOUR_PROJECT_ID/python-packages/simple/
```

## Features

- **Multi-language Support**: Traditional Chinese and English localization
- **Real-time Audio**: WebSocket-based voice chat capabilities
- **Session Management**: Comprehensive chat logging and session handling
- **Cloud Storage**: Support for GCS, S3, and local file storage
- **Distributed Locking**: Redis-based coordination for scalability
- **FastAPI Backend**: Modern async web framework with JWT authentication

## Architecture

- **Chat Module**: ADK integration with JSONL persistence
- **Evaluation Module**: AI-powered conversation analysis
- **Voice Module**: Real-time audio streaming
- **Storage Layer**: Abstracted backend with multiple providers
- **Authentication**: Role-based access control

## Development

This package is part of the larger Role Play System project. For complete documentation, development setup, and contribution guidelines, see the [main repository](https://github.com/xCatG/RolePlaySystem).

## License

MIT License - see LICENSE file for details.