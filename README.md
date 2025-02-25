# Channel Digest Integration

## Overview

The **Channel Digest Service** is a FastAPI application that fetches channel statistics from an external API and sends a digest summary to a specified webhook endpoint.

## Screenshots

- Description of Channel Digest Integration

![Description of Channel Digest Integration](https://github.com/user-attachments/assets/86d56629-eaca-44c0-8e05-b4cc59f7eaf3)

- Channel Digest on Telex Channel
  
![Channel Digest on Telex Channel](https://github.com/user-attachments/assets/3291b63d-b889-4121-a88d-a02b842131f7)

## Features

- Fetches channel details from an external API.
- Constructs a digest containing message count, active users, and trending keywords.
- Sends the digest to a configured webhook.
- Includes error handling for missing or incorrect API responses.

## Project Structure

```
channel-digest/
├── api/
│ ├── db/
│ │ ├── __init__.py
│ │ └── schemas.py           # Data models
│ ├── routes/
│ │ ├── __init__.py
│ │ └── channel_digest.py    # Channel Digest route handlers
│ └── router.py              # API router configuration
├── core/
│ ├── __init__.py
│ └── config.py              # Application settings
├── tests/
│ ├── __init__.py
│ └── test_channel_digest.py # API endpoint tests
├── main.py                  # Application entry point
├── requirements.txt         # Project dependencies
└── README.md
```

## Technologies Used

- Python 3.11+
- FastAPI
- Pydantic
- pytest
- uvicorn
- httpx

## Installation

1. Clone the repository:

```shell
git clone <repository_url>
cd channel_digest
```

2. Create a virtual environment:

```shell
python -m venv .venv
source .venv/bin/activate # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```shell
pip install -r requirements.txt
```

## Running the Application

1. Start the server:

```shell
uvicorn main:app
```

2. Access the API documentation:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## API Endpoints

### Integration Metadata

- `GET /integration.json` \- Returns the integration metadata required by Telex.

### Tick Endpoint

- `POST /tick` - Triggers generation of channel aggregate statistics.

## Tick Payload Schema

```json
{
  "channel_id": "string",
  "return_url": "string",
  "organisation_id": "string",
  "settings": [
    {
      "label": "interval",
      "type": "text",
      "required": true,
      "default": "* * * * *"
    }
  ]
}
```

## Running Tests

```shell
pytest
```

## Error Handling

The API handles errors gracefully and provides appropriate responses.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -m 'feat: add new-feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/droffilc1/channel-digest/blob/main/LICENSE) file for details.

## Support

For support, please open an issue in the GitHub repository.
